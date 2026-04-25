"""
Deploy-compatible Unitree G1 flat velocity environment configuration.

Final robust ALWAYS-CROUCH (DEEP SQUAT) version:
- keeps the working internal command key 'twist'
- actor observation layout matches deploy.yaml exactly (98-D)
- rewards strongly favor deep squat walking
- no new reward functions introduced
- yields 29-D joint position actions
"""

from __future__ import annotations

import torch

from src.assets.robots import G1_ACTION_SCALE
from mjlab.envs import ManagerBasedRlEnvCfg
from mjlab.envs.mdp.actions import JointPositionActionCfg
from mjlab.managers.observation_manager import (
    ObservationGroupCfg,
    ObservationTermCfg,
)

import src.tasks.velocity.mdp as mdp
from .env_cfgs import unitree_g1_flat_env_cfg


# ---------------------------------------------------------------------
# Local gait phase (deploy-compatible)
# ---------------------------------------------------------------------
def gait_phase_local(
    env,
    period: float = 0.6,
    command_name: str = "twist",
) -> torch.Tensor:
    global_phase = (env.episode_length_buf * env.step_dt) % period / period
    phase = torch.zeros(env.num_envs, 2, device=env.device)
    phase[:, 0] = torch.sin(global_phase * torch.pi * 2.0)
    phase[:, 1] = torch.cos(global_phase * torch.pi * 2.0)

    cmd = env.command_manager.get_command(command_name)
    stand_mask = torch.linalg.norm(cmd, dim=1) < 0.1
    phase = torch.where(stand_mask.unsqueeze(1), torch.zeros_like(phase), phase)
    return phase


# ---------------------------------------------------------------------
# ALWAYS-CROUCH DEEP-SQUAT deploy config
# ---------------------------------------------------------------------
def unitree_g1_flat_crouch_deploy_env_cfg(
    play: bool = False,
) -> ManagerBasedRlEnvCfg:

    cfg = unitree_g1_flat_env_cfg(play=play)

    # ------------------------------------------------------------------
    # Use crouch robot init state (CRITICAL)
    # ------------------------------------------------------------------
    from src.assets.robots.unitree_g1.g1_constants_crouch import get_g1_robot_cfg
    cfg.scene.entities = {"robot": get_g1_robot_cfg()}

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    joint_pos_action = cfg.actions["joint_pos"]
    assert isinstance(joint_pos_action, JointPositionActionCfg)
    joint_pos_action.scale = G1_ACTION_SCALE

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    if "twist" not in cfg.commands:
        raise KeyError("Expected command 'twist' in base Unitree-G1-Flat config.")

    # ------------------------------------------------------------------
    # DEEP-SQUAT reward tuning
    # ------------------------------------------------------------------

    # Velocity tracking still present, but secondary
    cfg.rewards["track_linear_velocity"].weight = 0.7
    cfg.rewards["track_angular_velocity"].weight = 0.5

    # Strong posture anchoring around deep crouch
    cfg.rewards["pose"].weight = 1.4

    # Knees MUST bend deeply, hips may follow but not compensate
    cfg.rewards["pose"].params["std_walking"].update({
        r".*hip_pitch.*": 0.65,
        r".*knee.*": 0.20,
    })

    # Upright torso stabilization if available
    if "body_orientation_l2" in cfg.rewards:
        cfg.rewards["body_orientation_l2"].weight = -2.2

    # Ground contact & smoothness (critical in deep squat)
    cfg.rewards["foot_slip"].weight = -0.45
    cfg.rewards["action_rate_l2"].weight = -0.12
    cfg.rewards["joint_acc_l2"].weight = -3e-7

    # ------------------------------------------------------------------
    # Actor observation (DEPLOY layout, 98-D)
    # ------------------------------------------------------------------
    cfg.observations["actor"] = ObservationGroupCfg(
        concatenate_terms=True,
        enable_corruption=False if play else cfg.observations["actor"].enable_corruption,
        history_length=1,
        terms={
            "base_ang_vel": ObservationTermCfg(
                func=mdp.builtin_sensor,
                params={"sensor_name": "robot/imu_ang_vel"},
            ),
            "projected_gravity": ObservationTermCfg(
                func=mdp.projected_gravity,
            ),
            "velocity_commands": ObservationTermCfg(
                func=mdp.generated_commands,
                params={"command_name": "twist"},
            ),
            "gait_phase": ObservationTermCfg(
                func=gait_phase_local,
                params={"period": 0.6, "command_name": "twist"},
            ),
            "joint_pos_rel": ObservationTermCfg(func=mdp.joint_pos_rel),
            "joint_vel_rel": ObservationTermCfg(func=mdp.joint_vel_rel),
            "last_action": ObservationTermCfg(func=mdp.last_action),
        },
    )

    return cfg
