#!/usr/bin/env python3
from __future__ import annotations
"""
Conservative Unitree G1 standing test for unitree_mujoco/simulate_python.

Design goals
------------
- Be safer and easier to debug than a full-body policy rollout.
- Keep waist and arms fixed by default.
- Let the policy affect only the 12 leg joints by default.
- Use small action scaling and target slew limiting.
- Use startup pose as the observation nominal pose by default, because that is the
  least destructive fallback when the exact mjlab reset pose is unknown.

Notes
-----
This is still a best-effort bridge. If the policy stood in mjlab but not here,
the remaining likely causes are: joint-order mismatch, observation mismatch,
action scaling mismatch, or IMU quaternion convention mismatch.
"""

import argparse
import signal
import sys
import time
from dataclasses import dataclass
from threading import Lock, Thread
import select
import termios
import tty
from typing import Optional, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
except Exception:
    torch = None
    nn = None

try:
    import onnxruntime as ort
except Exception:
    ort = None

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import IMUState_ as HGIMUState
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_ as HGLowCmd
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_ as HGLowState
from unitree_sdk2py.utils.crc import CRC


NUM_ACTUATED = 29
NUM_MOTORS_MSG = 35
OBS_DIM = 96
ACT_DIM = 29
LOWCMD_TOPIC = "rt/lowcmd"
LOWSTATE_TOPIC = "rt/lowstate"
SECONDARY_IMU_TOPIC = "rt/secondary"

LEG_IDXS = list(range(12))
WAIST_IDXS = [12, 13, 14]
ARM_IDXS = list(range(15, 29))

G1_29_JOINT_NAMES = [
    "left_hip_pitch",
    "left_hip_roll",
    "left_hip_yaw",
    "left_knee",
    "left_ankle_pitch",
    "left_ankle_roll",
    "right_hip_pitch",
    "right_hip_roll",
    "right_hip_yaw",
    "right_knee",
    "right_ankle_pitch",
    "right_ankle_roll",
    "waist_yaw",
    "waist_roll",
    "waist_pitch",
    "left_shoulder_pitch",
    "left_shoulder_roll",
    "left_shoulder_yaw",
    "left_elbow",
    "left_wrist_roll",
    "left_wrist_pitch",
    "left_wrist_yaw",
    "right_shoulder_pitch",
    "right_shoulder_roll",
    "right_shoulder_yaw",
    "right_elbow",
    "right_wrist_roll",
    "right_wrist_pitch",
    "right_wrist_yaw",
]

# More conservative gains than the previous script.
KP_LEGS = 55.0
KD_LEGS = 3.0
KP_WAIST = 35.0
KD_WAIST = 2.0
KP_ARMS = 25.0
KD_ARMS = 1.5


@dataclass
class ControlConfig:
    domain_id: int = 1
    interface: str = "lo"
    control_dt: float = 0.005
    warmup_sec: float = 1.0
    settle_sec: float = 1.5
    action_scale: float = 0.03
    max_action_abs: float = 5.0
    max_delta_q: float = 0.10
    max_dq_abs: float = 20.0
    target_slew_step: float = 0.012
    cmd_vx: float = 0.0
    cmd_vy: float = 0.0
    cmd_wz: float = 0.0
    quat_format: str = "wxyz"
    log_every_sec: float = 1.0
    policy_backend: str = "pt"
    dry_run_hold_only: bool = False
    policy_legs_only: bool = True
    freeze_waist: bool = True
    freeze_arms: bool = True
    use_manual_leg_pose: bool = False
    start_mode: str = "pause"


class SharedBuffer:
    def __init__(self):
        self._lock = Lock()
        self._msg = None
        self._stamp = 0.0

    def set(self, msg):
        with self._lock:
            self._msg = msg
            self._stamp = time.time()

    def get(self):
        with self._lock:
            return self._msg, self._stamp


if nn is not None:
    class ActorPT(nn.Module):
        def __init__(self):
            super().__init__()
            self.mlp = nn.Sequential(
                nn.Linear(OBS_DIM, 512),
                nn.ELU(),
                nn.Linear(512, 256),
                nn.ELU(),
                nn.Linear(256, 128),
                nn.ELU(),
                nn.Linear(128, ACT_DIM),
            )

        def forward(self, x):
            return self.mlp(x)
else:
    class ActorPT(object):
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyTorch is not available in this environment.")


class PolicyWrapper:
    def __init__(self, ckpt_path: Optional[str], onnx_path: Optional[str], backend: str):
        self.backend = backend
        self.obs_mean = np.zeros((1, OBS_DIM), dtype=np.float32)
        self.obs_std = np.ones((1, OBS_DIM), dtype=np.float32)
        self.session = None
        self.input_name = None
        self.output_name = None
        self.actor = None

        if backend == "pt":
            if ckpt_path is None:
                raise ValueError("--checkpoint is required for backend=pt")
            if torch is None or nn is None:
                raise RuntimeError("PyTorch is not available in this environment.")
            try:
                ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
            except TypeError:
                ckpt = torch.load(ckpt_path, map_location="cpu")
            actor_sd = ckpt["actor_state_dict"]
            self.actor = ActorPT()
            mlp_sd = {k: v for k, v in actor_sd.items() if k.startswith("mlp.")}
            self.actor.load_state_dict(mlp_sd, strict=True)
            self.actor.eval()
            self.obs_mean = actor_sd["obs_normalizer._mean"].detach().cpu().numpy().astype(np.float32)
            self.obs_std = actor_sd["obs_normalizer._std"].detach().cpu().numpy().astype(np.float32)
            self.obs_std = np.maximum(self.obs_std, 1e-6)
        elif backend == "onnx":
            if onnx_path is None:
                raise ValueError("--onnx is required for backend=onnx")
            if ort is None:
                raise RuntimeError("onnxruntime is not available in this environment.")
            self.session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
        else:
            raise ValueError("Unsupported backend: %s" % backend)

    def act(self, obs: np.ndarray) -> np.ndarray:
        obs = obs.reshape(1, OBS_DIM).astype(np.float32)
        obs_norm = (obs - self.obs_mean) / self.obs_std
        if self.backend == "pt":
            with torch.no_grad():
                out = self.actor(torch.from_numpy(obs_norm))
            act = out.detach().cpu().numpy().reshape(-1)
        else:
            out = self.session.run([self.output_name], {self.input_name: obs_norm})[0]
            act = np.asarray(out, dtype=np.float32).reshape(-1)
        if act.shape[0] != ACT_DIM:
            raise RuntimeError("Policy returned %d actions, expected %d." % (act.shape[0], ACT_DIM))
        return act.astype(np.float32)


def get_motor_q_dq(lowstate_msg) -> Tuple[np.ndarray, np.ndarray]:
    q = np.zeros((NUM_MOTORS_MSG,), dtype=np.float32)
    dq = np.zeros((NUM_MOTORS_MSG,), dtype=np.float32)
    for i in range(NUM_MOTORS_MSG):
        ms = lowstate_msg.motor_state[i]
        q[i] = float(getattr(ms, "q", 0.0))
        dq[i] = float(getattr(ms, "dq", 0.0))
    return q, dq


def extract_quat_gyro(lowstate_msg, secondary_imu_msg, quat_format: str) -> Tuple[np.ndarray, np.ndarray]:
    imu = secondary_imu_msg if secondary_imu_msg is not None else getattr(lowstate_msg, "imu_state", None)
    if imu is None:
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32), np.zeros(3, dtype=np.float32)

    quat_raw = np.asarray(getattr(imu, "quaternion", [1.0, 0.0, 0.0, 0.0]), dtype=np.float32).reshape(-1)
    gyro_raw = np.asarray(getattr(imu, "gyroscope", [0.0, 0.0, 0.0]), dtype=np.float32).reshape(-1)

    if quat_raw.shape[0] != 4:
        quat_raw = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    if gyro_raw.shape[0] != 3:
        gyro_raw = np.zeros(3, dtype=np.float32)

    norm = float(np.linalg.norm(quat_raw))
    if norm < 1e-6:
        quat_raw = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    else:
        quat_raw = quat_raw / norm

    if quat_format == "xyzw":
        x, y, z, w = quat_raw.tolist()
        quat_wxyz = np.array([w, x, y, z], dtype=np.float32)
    else:
        quat_wxyz = quat_raw.astype(np.float32)

    return quat_wxyz, gyro_raw.astype(np.float32)


def quat_to_rotmat_wxyz(q: np.ndarray) -> np.ndarray:
    w, x, y, z = q.tolist()
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w),     2 * (x * z + y * w)],
        [2 * (x * y + z * w),     1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w),     2 * (y * z + x * w),     1 - 2 * (x * x + y * y)],
    ], dtype=np.float32)


def projected_gravity_body(quat_wxyz: np.ndarray) -> np.ndarray:
    rot = quat_to_rotmat_wxyz(quat_wxyz)
    return (rot.T @ np.array([0.0, 0.0, -1.0], dtype=np.float32)).astype(np.float32)


def build_obs(
    q_act: np.ndarray,
    dq_act: np.ndarray,
    q_obs_nominal: np.ndarray,
    body_gravity: np.ndarray,
    body_omega: np.ndarray,
    cmd: np.ndarray,
    prev_action: np.ndarray,
    max_dq_abs: float,
) -> np.ndarray:
    q_rel = q_act - q_obs_nominal
    dq_clip = np.clip(dq_act, -max_dq_abs, max_dq_abs)
    obs = np.concatenate([
        q_rel.astype(np.float32),
        dq_clip.astype(np.float32),
        body_gravity.astype(np.float32),
        body_omega.astype(np.float32),
        cmd.astype(np.float32),
        prev_action.astype(np.float32),
    ], axis=0)
    if obs.shape[0] != OBS_DIM:
        raise RuntimeError("Built obs with dim %d, expected %d." % (obs.shape[0], OBS_DIM))
    return obs


def init_lowcmd_from_state(lowstate_msg) -> HGLowCmd:
    cmd = unitree_hg_msg_dds__LowCmd_()
    cmd.mode_pr = 0
    cmd.mode_machine = int(getattr(lowstate_msg, "mode_machine", 0))
    for i in range(NUM_MOTORS_MSG):
        cmd.motor_cmd[i].mode = 1
        cmd.motor_cmd[i].q = 0.0
        cmd.motor_cmd[i].dq = 0.0
        cmd.motor_cmd[i].kp = 0.0
        cmd.motor_cmd[i].kd = 0.0
        cmd.motor_cmd[i].tau = 0.0
    return cmd


def make_group_gains() -> Tuple[np.ndarray, np.ndarray]:
    kp = np.zeros((NUM_ACTUATED,), dtype=np.float32)
    kd = np.zeros((NUM_ACTUATED,), dtype=np.float32)
    for i in LEG_IDXS:
        kp[i] = KP_LEGS
        kd[i] = KD_LEGS
    for i in WAIST_IDXS:
        kp[i] = KP_WAIST
        kd[i] = KD_WAIST
    for i in ARM_IDXS:
        kp[i] = KP_ARMS
        kd[i] = KD_ARMS
    return kp, kd


def apply_joint_targets(cmd_msg, q_targets: np.ndarray, kp: np.ndarray, kd: np.ndarray):
    for i in range(NUM_ACTUATED):
        cmd_msg.motor_cmd[i].mode = 1
        cmd_msg.motor_cmd[i].q = float(q_targets[i])
        cmd_msg.motor_cmd[i].dq = 0.0
        cmd_msg.motor_cmd[i].kp = float(kp[i])
        cmd_msg.motor_cmd[i].kd = float(kd[i])
        cmd_msg.motor_cmd[i].tau = 0.0
    for i in range(NUM_ACTUATED, NUM_MOTORS_MSG):
        cmd_msg.motor_cmd[i].mode = 1
        cmd_msg.motor_cmd[i].q = 0.0
        cmd_msg.motor_cmd[i].dq = 0.0
        cmd_msg.motor_cmd[i].kp = 0.0
        cmd_msg.motor_cmd[i].kd = 0.0
        cmd_msg.motor_cmd[i].tau = 0.0


def format_joint_subset(values: np.ndarray, idxs) -> str:
    parts = []
    for i in idxs:
        parts.append("%s=% .3f" % (G1_29_JOINT_NAMES[i], float(values[i])))
    return ", ".join(parts)




class ModeState:
    PAUSE = "pause"
    HOLD = "hold"
    POLICY = "policy"


class KeyboardModeController:
    """
    Simple non-blocking terminal control:
      space / p : toggle pause <-> last active mode
      h         : hold mode
      r         : policy mode (run)
      q         : quit
      ?         : print help
    Works in a normal terminal without needing GUI focus.
    """
    def __init__(self, initial_mode: str, allow_policy: bool = True):
        self._mode = initial_mode
        self._last_active = ModeState.HOLD if initial_mode == ModeState.PAUSE else initial_mode
        self._allow_policy = allow_policy
        self._lock = Lock()
        self._running = True
        self._thread = None
        self._fd = None
        self._old_term = None

    def start(self):
        if not sys.stdin.isatty():
            print("[WARN] stdin is not a TTY; keyboard mode switching disabled")
            return
        self._fd = sys.stdin.fileno()
        self._old_term = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.print_help()
        print("[INFO] initial mode: %s" % self.mode)

    def stop(self):
        self._running = False
        try:
            if self._old_term is not None and self._fd is not None:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_term)
        except Exception:
            pass

    @property
    def mode(self):
        with self._lock:
            return self._mode

    def set_mode(self, mode: str):
        with self._lock:
            if mode == ModeState.POLICY and not self._allow_policy:
                print("[WARN] policy mode requested but no policy is loaded; staying in hold")
                mode = ModeState.HOLD
            self._mode = mode
            if mode != ModeState.PAUSE:
                self._last_active = mode
        print("[INFO] mode -> %s" % mode)

    def toggle_pause(self):
        with self._lock:
            if self._mode == ModeState.PAUSE:
                new_mode = self._last_active
            else:
                new_mode = ModeState.PAUSE
            if new_mode == ModeState.POLICY and not self._allow_policy:
                new_mode = ModeState.HOLD
            self._mode = new_mode
            if new_mode != ModeState.PAUSE:
                self._last_active = new_mode
        print("[INFO] mode -> %s" % new_mode)

    def _loop(self):
        while self._running:
            try:
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
            except Exception:
                time.sleep(0.1)
                continue
            if not r:
                continue
            ch = sys.stdin.read(1)
            if not ch:
                continue
            ch = ch.lower()
            if ch in (" ", "p"):
                self.toggle_pause()
            elif ch == "h":
                self.set_mode(ModeState.HOLD)
            elif ch == "r":
                self.set_mode(ModeState.POLICY)
            elif ch == "?":
                self.print_help()
            elif ch == "q":
                print("[INFO] quit requested from keyboard")
                self._running = False
            else:
                print("[INFO] key=%r ignored (? for help)" % ch)

    def print_help(self):
        print("[INFO] keyboard controls: [space]/p toggle pause, h hold, r run policy, q quit, ? help")


class G1StandController:
    def __init__(self, cfg: ControlConfig, policy: Optional[PolicyWrapper]):
        self.cfg = cfg
        self.policy = policy
        self.lowstate_buf = SharedBuffer()
        self.secondary_imu_buf = SharedBuffer()
        self.crc = CRC()
        self.running = True
        self.prev_action = np.zeros((ACT_DIM,), dtype=np.float32)
        self.prev_q_target = None
        self.q_obs_nominal = None
        self.q_hold_pose = None
        self.kp, self.kd = make_group_gains()
        self.mode_ctl = KeyboardModeController(initial_mode=cfg.start_mode, allow_policy=(policy is not None and not cfg.dry_run_hold_only))

        ChannelFactoryInitialize(cfg.domain_id, cfg.interface)
        self.low_sub = ChannelSubscriber(LOWSTATE_TOPIC, HGLowState)
        self.low_sub.Init(self._on_lowstate, 10)
        self.imu_sub = ChannelSubscriber(SECONDARY_IMU_TOPIC, HGIMUState)
        self.imu_sub.Init(self._on_secondary_imu, 10)
        self.low_pub = ChannelPublisher(LOWCMD_TOPIC, HGLowCmd)
        self.low_pub.Init()

    def _on_lowstate(self, msg: HGLowState):
        self.lowstate_buf.set(msg)

    def _on_secondary_imu(self, msg: HGIMUState):
        self.secondary_imu_buf.set(msg)

    def wait_for_state(self, timeout: float = 10.0):
        start = time.time()
        while time.time() - start < timeout:
            low_msg, _ = self.lowstate_buf.get()
            if low_msg is not None:
                return low_msg
            time.sleep(0.02)
        raise TimeoutError("Timed out waiting for rt/lowstate")

    def estimate_startup_pose(self) -> np.ndarray:
        samples = []
        t_end = time.time() + self.cfg.warmup_sec
        while time.time() < t_end:
            low_msg, _ = self.lowstate_buf.get()
            if low_msg is not None:
                q, _ = get_motor_q_dq(low_msg)
                samples.append(q[:NUM_ACTUATED].copy())
            time.sleep(self.cfg.control_dt)
        if not samples:
            raise RuntimeError("No low-state samples collected during warmup.")
        return np.median(np.stack(samples, axis=0), axis=0).astype(np.float32)

    def make_manual_leg_pose(self, startup_pose: np.ndarray) -> np.ndarray:
        # Conservative small crouch around the startup pose. This avoids forcing the robot
        # into a completely guessed full-body posture.
        q = startup_pose.copy()
        # left leg
        q[0] = -0.20
        q[1] = 0.00
        q[2] = 0.00
        q[3] = 0.35
        q[4] = -0.18
        q[5] = 0.00
        # right leg
        q[6] = -0.20
        q[7] = 0.00
        q[8] = 0.00
        q[9] = 0.35
        q[10] = -0.18
        q[11] = 0.00
        # freeze waist and arms at startup pose
        return q

    def initialize_poses(self):
        startup_pose = self.estimate_startup_pose()
        self.q_obs_nominal = startup_pose.copy()
        if self.cfg.use_manual_leg_pose:
            self.q_hold_pose = self.make_manual_leg_pose(startup_pose)
        else:
            self.q_hold_pose = startup_pose.copy()
        self.prev_q_target = self.q_hold_pose.copy()

        print("[INFO] startup pose captured")
        for i, name in enumerate(G1_29_JOINT_NAMES):
            print("  %02d %22s: % .4f rad" % (i, name, startup_pose[i]))

        print("[INFO] policy-active joints: %s" % ", ".join(G1_29_JOINT_NAMES[i] for i in LEG_IDXS))
        print("[INFO] frozen waist joints: %s" % ", ".join(G1_29_JOINT_NAMES[i] for i in WAIST_IDXS))
        print("[INFO] frozen arm joints: %s" % ", ".join(G1_29_JOINT_NAMES[i] for i in ARM_IDXS))
        print("[INFO] hold leg pose: %s" % format_joint_subset(self.q_hold_pose, LEG_IDXS))

    def build_targets(self, low_msg, sec_imu_msg) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        q_all, dq_all = get_motor_q_dq(low_msg)
        q_act = q_all[:NUM_ACTUATED]
        dq_act = dq_all[:NUM_ACTUATED]

        quat_wxyz, body_omega = extract_quat_gyro(low_msg, sec_imu_msg, self.cfg.quat_format)
        body_gravity = projected_gravity_body(quat_wxyz)
        cmd = np.array([self.cfg.cmd_vx, self.cfg.cmd_vy, self.cfg.cmd_wz], dtype=np.float32)

        obs = build_obs(
            q_act=q_act,
            dq_act=dq_act,
            q_obs_nominal=self.q_obs_nominal,
            body_gravity=body_gravity,
            body_omega=body_omega,
            cmd=cmd,
            prev_action=self.prev_action,
            max_dq_abs=self.cfg.max_dq_abs,
        )

        if self.cfg.dry_run_hold_only or self.policy is None:
            action = np.zeros((ACT_DIM,), dtype=np.float32)
        else:
            action = self.policy.act(obs)
            action = np.clip(action, -self.cfg.max_action_abs, self.cfg.max_action_abs)

        delta_q = np.zeros((ACT_DIM,), dtype=np.float32)
        if self.cfg.policy_legs_only:
            delta_q[LEG_IDXS] = np.clip(
                self.cfg.action_scale * action[LEG_IDXS],
                -self.cfg.max_delta_q,
                self.cfg.max_delta_q,
            )
        else:
            delta_q = np.clip(self.cfg.action_scale * action, -self.cfg.max_delta_q, self.cfg.max_delta_q)
            if self.cfg.freeze_waist:
                delta_q[WAIST_IDXS] = 0.0
            if self.cfg.freeze_arms:
                delta_q[ARM_IDXS] = 0.0

        q_target_des = self.q_hold_pose + delta_q
        q_target = np.clip(
            q_target_des,
            self.prev_q_target - self.cfg.target_slew_step,
            self.prev_q_target + self.cfg.target_slew_step,
        )

        if self.cfg.freeze_waist:
            q_target[WAIST_IDXS] = self.q_hold_pose[WAIST_IDXS]
        if self.cfg.freeze_arms:
            q_target[ARM_IDXS] = self.q_hold_pose[ARM_IDXS]

        self.prev_q_target = q_target.astype(np.float32)

        if self.cfg.policy_legs_only:
            self.prev_action[:] = 0.0
            self.prev_action[LEG_IDXS] = action[LEG_IDXS].astype(np.float32)
        else:
            self.prev_action = action.astype(np.float32)
            if self.cfg.freeze_waist:
                self.prev_action[WAIST_IDXS] = 0.0
            if self.cfg.freeze_arms:
                self.prev_action[ARM_IDXS] = 0.0

        return q_target.astype(np.float32), q_act.astype(np.float32), dq_act.astype(np.float32), action.astype(np.float32)

    def run(self):
        low_msg = self.wait_for_state()
        print("[INFO] lowstate connected")
        self.initialize_poses()

        cmd_msg = init_lowcmd_from_state(low_msg)
        self.mode_ctl.start()
        last_log_t = 0.0
        t_start = time.time()

        while time.time() - t_start < self.cfg.settle_sec and self.running:
            low_msg, _ = self.lowstate_buf.get()
            if low_msg is None:
                time.sleep(self.cfg.control_dt)
                continue
            apply_joint_targets(cmd_msg, self.q_hold_pose, self.kp, self.kd)
            cmd_msg.crc = self.crc.Crc(cmd_msg)
            self.low_pub.Write(cmd_msg)
            time.sleep(self.cfg.control_dt)

        print("[INFO] entering conservative standing control loop")
        while self.running:
            t_loop = time.time()
            low_msg, low_stamp = self.lowstate_buf.get()
            sec_imu_msg, _ = self.secondary_imu_buf.get()
            if low_msg is None:
                time.sleep(self.cfg.control_dt)
                continue

            cmd_msg.mode_machine = int(getattr(low_msg, "mode_machine", cmd_msg.mode_machine))
            if not self.mode_ctl._running:
                self.running = False
                continue
            mode = self.mode_ctl.mode

            if mode == ModeState.PAUSE:
                q_target = q_meas = dq_meas = action = None
                apply_joint_targets(cmd_msg, self.q_hold_pose, self.kp, self.kd)
            elif mode == ModeState.HOLD:
                q_all, dq_all = get_motor_q_dq(low_msg)
                q_meas = q_all[:NUM_ACTUATED].astype(np.float32)
                dq_meas = dq_all[:NUM_ACTUATED].astype(np.float32)
                q_target = self.q_hold_pose.astype(np.float32)
                action = np.zeros((ACT_DIM,), dtype=np.float32)
                self.prev_q_target = self.q_hold_pose.copy()
                self.prev_action[:] = 0.0
                apply_joint_targets(cmd_msg, q_target, self.kp, self.kd)
            else:
                q_target, q_meas, dq_meas, action = self.build_targets(low_msg, sec_imu_msg)
                apply_joint_targets(cmd_msg, q_target, self.kp, self.kd)

            cmd_msg.crc = self.crc.Crc(cmd_msg)
            self.low_pub.Write(cmd_msg)

            if t_loop - last_log_t >= self.cfg.log_every_sec:
                if q_target is None:
                    stale_ms = 1000.0 * max(0.0, time.time() - low_stamp)
                    print("[INFO] mode=pause  publishing hold pose  state_age=%.1f ms" % stale_ms)
                else:
                    leg_q_err = float(np.max(np.abs(q_target[LEG_IDXS] - q_meas[LEG_IDXS])))
                    leg_dq = float(np.max(np.abs(dq_meas[LEG_IDXS])))
                    arm_dq = float(np.max(np.abs(dq_meas[ARM_IDXS])))
                    stale_ms = 1000.0 * max(0.0, time.time() - low_stamp)
                    leg_act = action[LEG_IDXS]
                    print(
                        "[INFO] mode=%s  leg max|q_target-q|=%.4f rad  leg max|dq|=%.4f rad/s  arm max|dq|=%.4f rad/s  max|leg_action|=%.4f  state_age=%.1f ms"
                        % (mode, leg_q_err, leg_dq, arm_dq, float(np.max(np.abs(leg_act))), stale_ms)
                    )
                last_log_t = t_loop

            sleep_time = max(0.0, self.cfg.control_dt - (time.time() - t_loop))
            time.sleep(sleep_time)

    def stop(self):
        self.running = False
        self.mode_ctl.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Conservative Unitree G1 standing test in unitree_mujoco")
    parser.add_argument("--checkpoint", type=str, default=None, help="Path to mjlab PyTorch checkpoint (.pt)")
    parser.add_argument("--onnx", type=str, default=None, help="Path to ONNX policy")
    parser.add_argument("--backend", type=str, default="pt", choices=["pt", "onnx"], help="Policy backend")
    parser.add_argument("--domain-id", type=int, default=1)
    parser.add_argument("--interface", type=str, default="lo")
    parser.add_argument("--control-dt", type=float, default=0.005)
    parser.add_argument("--warmup-sec", type=float, default=1.0)
    parser.add_argument("--settle-sec", type=float, default=1.5)
    parser.add_argument("--action-scale", type=float, default=0.03)
    parser.add_argument("--max-delta-q", type=float, default=0.10)
    parser.add_argument("--max-action-abs", type=float, default=5.0)
    parser.add_argument("--max-dq-abs", type=float, default=20.0)
    parser.add_argument("--target-slew-step", type=float, default=0.012)
    parser.add_argument("--quat-format", type=str, default="wxyz", choices=["wxyz", "xyzw"])
    parser.add_argument("--hold-only", action="store_true", help="Ignore the policy and just hold the pose")
    parser.add_argument("--full-body-policy", action="store_true", help="Allow the policy to affect all 29 joints")
    parser.add_argument("--manual-leg-pose", action="store_true", help="Use a small hand-tuned crouch for the legs instead of the startup leg pose")
    parser.add_argument("--start-mode", type=str, default="pause", choices=["pause", "hold", "policy"], help="Initial controller mode")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = ControlConfig(
        domain_id=args.domain_id,
        interface=args.interface,
        control_dt=args.control_dt,
        warmup_sec=args.warmup_sec,
        settle_sec=args.settle_sec,
        action_scale=args.action_scale,
        max_delta_q=args.max_delta_q,
        max_action_abs=args.max_action_abs,
        max_dq_abs=args.max_dq_abs,
        target_slew_step=args.target_slew_step,
        quat_format=args.quat_format,
        policy_backend=args.backend,
        dry_run_hold_only=args.hold_only,
        policy_legs_only=not args.full_body_policy,
        use_manual_leg_pose=args.manual_leg_pose,
        start_mode=args.start_mode,
    )

    policy = None
    if not args.hold_only:
        policy = PolicyWrapper(ckpt_path=args.checkpoint, onnx_path=args.onnx, backend=args.backend)
        print("[INFO] loaded policy backend=%s" % args.backend)

    controller = G1StandController(cfg, policy)

    def _handle_signal(sig, frame):
        del sig, frame
        print("\n[INFO] stopping controller ...")
        controller.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        controller.run()
    except KeyboardInterrupt:
        controller.stop()
    except Exception as exc:
        controller.stop()
        print("[ERROR] %s" % exc, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
