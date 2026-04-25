"""Deploy-compatible Unitree G1 flat velocity environment configuration.

Final robust version:
- keeps the working internal command key 'twist'
- only changes the ACTOR observation layout/names to match deploy.yaml (98-D)
- keeps the stable standard-flat reward/curriculum logic untouched
- yields 29-D action output

IMPORTANT:
Deploy compatibility depends on observation ORDER and DIMENSIONS, not on the
internal training-time command-manager key. Therefore we keep 'twist' internally
to avoid breaking reward/curriculum code, but expose the actor term as
'velocity_commands' in the correct position.

Place as:
  src/tasks/velocity/config/g1/env_cfgs_deploy98.py
"""

from __future__ import annotations

import torch

from src.assets.robots import G1_ACTION_SCALE
from mjlab.envs import ManagerBasedRlEnvCfg
from mjlab.envs.mdp.actions import JointPositionActionCfg
from mjlab.managers.observation_manager import ObservationGroupCfg, ObservationTermCfg

import src.tasks.velocity.mdp as mdp

from .env_cfgs import unitree_g1_flat_env_cfg


def gait_phase_local(
  env,
  period: float = 0.6,
  command_name: str = "twist",
) -> torch.Tensor:
  """Local gait phase observation for deploy-compatible actor layout."""
  global_phase = (env.episode_length_buf * env.step_dt) % period / period
  phase = torch.zeros(env.num_envs, 2, device=env.device)
  phase[:, 0] = torch.sin(global_phase * torch.pi * 2.0)
  phase[:, 1] = torch.cos(global_phase * torch.pi * 2.0)

  cmd = env.command_manager.get_command(command_name)
  stand_mask = torch.linalg.norm(cmd, dim=1) < 0.1
  phase = torch.where(stand_mask.unsqueeze(1), torch.zeros_like(phase), phase)
  return phase


def unitree_g1_flat_deploy98_env_cfg(play: bool = False) -> ManagerBasedRlEnvCfg:
  """Create a deploy-compatible flat G1 task with 98-D actor observation."""
  cfg = unitree_g1_flat_env_cfg(play=play)

  # Keep robot-specific action scaling.
  joint_pos_action = cfg.actions["joint_pos"]
  assert isinstance(joint_pos_action, JointPositionActionCfg)
  joint_pos_action.scale = G1_ACTION_SCALE

  # DO NOT rename the working internal command key 'twist'.
  # Standard flat rewards/curriculum depend on it.
  if "twist" not in cfg.commands:
    raise KeyError("Expected command 'twist' in base Unitree-G1-Flat config.")

  # Rebuild ONLY the actor observation to match deploy.yaml exactly:
  # 3 + 3 + 3 + 2 + 29 + 29 + 29 = 98
  #
  # The term NAME 'velocity_commands' is deploy-compatible, but internally it
  # still reads from the working command key 'twist'.
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
      "joint_pos_rel": ObservationTermCfg(
        func=mdp.joint_pos_rel,
      ),
      "joint_vel_rel": ObservationTermCfg(
        func=mdp.joint_vel_rel,
      ),
      "last_action": ObservationTermCfg(
        func=mdp.last_action,
      ),
    },
  )

  return cfg
