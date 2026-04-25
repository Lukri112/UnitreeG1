"""Script to train RL agent with RSL-RL."""

import importlib
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import tyro
import mjlab  # ? IMPORTANT: required for mjlab.TYRO_FLAGS in tyro.cli()

from mjlab.envs import ManagerBasedRlEnv, ManagerBasedRlEnvCfg
from mjlab.rl import MjlabOnPolicyRunner, RslRlOnPolicyRunnerCfg, RslRlVecEnvWrapper
from mjlab.tasks.registry import list_tasks, load_env_cfg, load_rl_cfg, load_runner_cls
from mjlab.tasks.tracking.mdp import MotionCommandCfg
from mjlab.utils.gpu import select_gpus
from mjlab.utils.os import dump_yaml, get_checkpoint_path
from mjlab.utils.torch import configure_torch_backends
from mjlab.utils.wrappers import VideoRecorder


@dataclass(frozen=True)
class TrainConfig:
  env: ManagerBasedRlEnvCfg
  agent: RslRlOnPolicyRunnerCfg
  motion_file: str | None = None
  video: bool = False
  video_length: int = 200
  video_interval: int = 2000
  enable_nan_guard: bool = False
  torchrunx_log_dir: str | None = None
  gpu_ids: list[int] | Literal["all"] | None = field(default_factory=lambda: [0])
  wandb_run_id: str | None = None

  @staticmethod
  def from_task(task_id: str) -> "TrainConfig":
    env_cfg = load_env_cfg(task_id)
    agent_cfg = load_rl_cfg(task_id)
    assert isinstance(agent_cfg, RslRlOnPolicyRunnerCfg)
    return TrainConfig(env=env_cfg, agent=agent_cfg)


def _configure_wandb_resume(log_dir: Path, explicit_run_id: str | None = None) -> None:
  """Reuse the original W&B run when resuming from an existing log directory."""
  run_id = explicit_run_id

  if run_id is None:
    wandb_dir = log_dir / "wandb"
    if wandb_dir.exists():
      candidates: list[Path] = []
      latest_run = wandb_dir / "latest-run"
      if latest_run.exists():
        candidates.append(latest_run.resolve())
      candidates.extend(sorted(wandb_dir.glob("run-*"), key=lambda p: p.stat().st_mtime, reverse=True))

      for candidate in candidates:
        name = candidate.name
        if "-" in name:
          maybe_id = name.rsplit("-", 1)[-1]
          if maybe_id:
            run_id = maybe_id
            break

  if run_id is None:
    return

  os.environ["WANDB_RUN_ID"] = run_id
  os.environ["WANDB_RESUME"] = "must"
  os.environ["WANDB_DIR"] = str(log_dir)
  print(f"[INFO] Resuming W&B run: {run_id}")


def _disable_wandb_store_config_on_resume() -> None:
  """Prevent rsl_rl from re-uploading env_cfg/train_cfg during W&B resume."""
  try:
    module = importlib.import_module("rsl_rl.utils.wandb_utils")
  except Exception as exc:
    print(f"[WARN] Could not import rsl_rl.utils.wandb_utils for resume patch: {exc}")
    return

  patched_any = False
  for attr_name in dir(module):
    attr = getattr(module, attr_name)
    if isinstance(attr, type) and hasattr(attr, "store_config"):
      original = getattr(attr, "store_config")
      if getattr(original, "_resume_skip_patch", False):
        patched_any = True
        continue

      def _store_config_noop(self, env_cfg, train_cfg):
        if os.environ.get("WANDB_RESUME"):
          print("[INFO] Skipping W&B store_config() on resume.")
          return
        return original(self, env_cfg, train_cfg)

      _store_config_noop._resume_skip_patch = True  # type: ignore[attr-defined]
      setattr(attr, "store_config", _store_config_noop)
      patched_any = True

  if not patched_any:
    print("[WARN] No store_config() method found in rsl_rl.utils.wandb_utils to patch.")


def run_train(task_id: str, cfg: TrainConfig, log_dir: Path) -> None:
  cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
  if cuda_visible == "":
    device = "cpu"
    seed = cfg.agent.seed
    rank = 0
  else:
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    rank = int(os.environ.get("RANK", "0"))
    os.environ["MUJOCO_EGL_DEVICE_ID"] = str(local_rank)
    device = f"cuda:{local_rank}"
    seed = cfg.agent.seed + local_rank

  configure_torch_backends()

  cfg.agent.seed = seed
  cfg.env.seed = seed

  print(f"[INFO] Training with: device={device}, seed={seed}, rank={rank}")

  is_tracking_task = "motion" in cfg.env.commands and isinstance(
    cfg.env.commands["motion"], MotionCommandCfg
  )

  if is_tracking_task:
    if not cfg.motion_file:
      raise ValueError("For tracking tasks, --motion-file must be set ...")
    motion_path = Path(cfg.motion_file).expanduser().resolve()
    if not motion_path.exists():
      raise FileNotFoundError(f"Motion file not found: {motion_path}")
    motion_cmd = cfg.env.commands["motion"]
    assert isinstance(motion_cmd, MotionCommandCfg)
    motion_cmd.motion_file = str(motion_path)
    print(f"[INFO] Using motion file: {motion_cmd.motion_file}")

    if motion_cmd.motion_file and Path(motion_cmd.motion_file).exists():
      print(f"[INFO] Using local motion file: {motion_cmd.motion_file}")

  if cfg.enable_nan_guard:
    cfg.env.sim.nan_guard.enabled = True
    print(f"[INFO] NaN guard enabled, output dir: {cfg.env.sim.nan_guard.output_dir}")

  if rank == 0:
    print(f"[INFO] Logging experiment in directory: {log_dir}")

  env = ManagerBasedRlEnv(
    cfg=cfg.env, device=device, render_mode="rgb_array" if cfg.video else None
  )

  log_root_path = log_dir.parent

  # -------------------------------------------------------------------
  # ? PATCH: load checkpoint whenever load_run is provided
  #    - resume=True  -> "resume" semantics (W&B resume etc.)
  #    - resume=False -> fine-tune from checkpoint into NEW log dir
  # -------------------------------------------------------------------
  resume_path: Path | None = None
  if cfg.agent.load_run:
    resume_path = get_checkpoint_path(
      log_root_path, cfg.agent.load_run, cfg.agent.load_checkpoint
    )
    if cfg.agent.resume:
      print(f"[INFO] Resuming checkpoint from: {resume_path}")
      _disable_wandb_store_config_on_resume()
    else:
      print(f"[INFO] Loading checkpoint (fine-tune) from: {resume_path}")

  if cfg.video and rank == 0:
    env = VideoRecorder(
      env,
      video_folder=Path(log_dir) / "videos" / "train",
      step_trigger=lambda step: step % cfg.video_interval == 0,
      video_length=cfg.video_length,
      disable_logger=True,
    )
    print("[INFO] Recording videos during training.")

  env = RslRlVecEnvWrapper(env, clip_actions=cfg.agent.clip_actions)

  agent_cfg = asdict(cfg.agent)
  env_cfg = asdict(cfg.env)

  runner_cls = load_runner_cls(task_id)
  if runner_cls is None:
    runner_cls = MjlabOnPolicyRunner

  runner = runner_cls(env, agent_cfg, str(log_dir), device)

  if resume_path is not None:
    runner.load(str(resume_path))
    loaded_iteration = int(getattr(runner, "current_learning_iteration", 0))
    print(f"[INFO] Loaded checkpoint iteration: {loaded_iteration}")
    print(f"[INFO] Target iteration: {cfg.agent.max_iterations}")
    remaining_iterations = max(int(cfg.agent.max_iterations) - loaded_iteration, 0)
    print(f"[INFO] Remaining iterations: {remaining_iterations}")
  else:
    loaded_iteration = 0
    remaining_iterations = int(cfg.agent.max_iterations)

  if rank == 0:
    dump_yaml(log_dir / "params" / "env.yaml", env_cfg)
    dump_yaml(log_dir / "params" / "agent.yaml", agent_cfg)

  if remaining_iterations <= 0:
    print("[INFO] Checkpoint already reached or exceeded target iteration. Nothing to do.")
    env.close()
    return

  runner.learn(
    num_learning_iterations=remaining_iterations, init_at_random_ep_len=True
  )

  env.close()


def launch_training(task_id: str, args: TrainConfig | None = None):
  args = args or TrainConfig.from_task(task_id)

  log_root_path = Path("logs") / "rsl_rl" / args.agent.experiment_name
  log_root_path.resolve()

  if args.agent.resume and args.agent.load_run:
    # Resume into existing run directory (W&B resume semantics)
    log_dir = log_root_path / args.agent.load_run
    _configure_wandb_resume(log_dir, args.wandb_run_id)
  else:
    # New run directory (fine-tune or fresh training)
    log_dir_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if args.agent.run_name:
      log_dir_name += f"_{args.agent.run_name}"
    log_dir = log_root_path / log_dir_name

  selected_gpus, num_gpus = select_gpus(args.gpu_ids)

  if selected_gpus is None:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
  else:
    os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, selected_gpus))
  os.environ["MUJOCO_GL"] = "egl"

  if num_gpus <= 1:
    run_train(task_id, args, log_dir)
  else:
    import torchrunx

    logging.basicConfig(level=logging.INFO)

    if "TORCHRUNX_LOG_DIR" not in os.environ:
      if args.torchrunx_log_dir is not None:
        os.environ["TORCHRUNX_LOG_DIR"] = args.torchrunx_log_dir
      else:
        os.environ["TORCHRUNX_LOG_DIR"] = str(log_dir / "torchrunx")

    print(f"[INFO] Launching training with {num_gpus} GPUs", flush=True)
    torchrunx.Launcher(
      hostnames=["localhost"],
      workers_per_host=num_gpus,
      backend=None,
      copy_env_vars=torchrunx.DEFAULT_ENV_VARS_FOR_COPY + ("MUJOCO*", "WANDB*"),
    ).run(run_train, task_id, args, log_dir)


def main():
  import mjlab.tasks  # noqa: F401
  import src.tasks

  all_tasks = list_tasks()
  chosen_task, remaining_args = tyro.cli(
    tyro.extras.literal_type_from_choices(all_tasks),
    add_help=False,
    return_unknown_args=True,
    config=mjlab.TYRO_FLAGS,
  )

  args = tyro.cli(
    TrainConfig,
    args=remaining_args,
    default=TrainConfig.from_task(chosen_task),
    prog=sys.argv[0] + f" {chosen_task}",
    config=mjlab.TYRO_FLAGS,
  )
  del remaining_args

  launch_training(task_id=chosen_task, args=args)


if __name__ == "__main__":
  main()