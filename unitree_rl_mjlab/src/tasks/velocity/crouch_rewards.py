"""Custom crouch rewards for Unitree G1 crouch walking."""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch

from mjlab.entity import Entity
from mjlab.managers.scene_entity_config import SceneEntityCfg
from mjlab.utils.lab_api.string import resolve_matching_names_values

if TYPE_CHECKING:
  from mjlab.envs import ManagerBasedRlEnv


_DEFAULT_ASSET_CFG = SceneEntityCfg("robot")


def crouch_joint_pose_reward(
  env: "ManagerBasedRlEnv",
  target_by_regex: dict[str, float],
  std: float,
  asset_cfg: SceneEntityCfg = _DEFAULT_ASSET_CFG,
) -> torch.Tensor:
  """Reward proximity to a crouch-oriented joint target pose."""
  asset: Entity = env.scene[asset_cfg.name]
  current_joint_pos = asset.data.joint_pos[:, asset_cfg.joint_ids]
  default_joint_pos = asset.data.default_joint_pos[:, asset_cfg.joint_ids]

  _, joint_names = asset.find_joints(asset_cfg.joint_names)

  # returns (indices, names, values)
  indices, _, values = resolve_matching_names_values(
    data=target_by_regex,
    list_of_strings=joint_names,
  )

  target_joint_pos = default_joint_pos.clone()
  if len(indices) > 0:
    target_joint_pos[:, indices] = torch.tensor(
      values, device=env.device, dtype=current_joint_pos.dtype
    ).unsqueeze(0)

  error_squared = torch.square(current_joint_pos - target_joint_pos)
  return torch.exp(-torch.mean(error_squared, dim=1) / (std**2))


def base_height_target_reward(
  env: "ManagerBasedRlEnv",
  target_height: float,
  std: float,
  asset_cfg: SceneEntityCfg = _DEFAULT_ASSET_CFG,
) -> torch.Tensor:
  """Reward a target root-link/base height."""
  asset: Entity = env.scene[asset_cfg.name]
  height = asset.data.root_link_pos_w[:, 2]
  error = torch.square(height - target_height)
  return torch.exp(-error / (std**2))


def foot_spread_penalty(
  env: "ManagerBasedRlEnv",
  target_width: float,
  std: float,
  asset_cfg: SceneEntityCfg,
) -> torch.Tensor:
  """Penalty when the horizontal distance between the feet gets too large.

  Expects asset_cfg.site_names to contain exactly two foot sites:
    (left_site, right_site)
  """
  asset: Entity = env.scene[asset_cfg.name]
  site_pos_w = asset.data.site_pos_w[:, asset_cfg.site_ids, :]
  left_xy = site_pos_w[:, 0, :2]
  right_xy = site_pos_w[:, 1, :2]
  foot_distance = torch.linalg.norm(left_xy - right_xy, dim=1)
  excess = torch.clamp(foot_distance - target_width, min=0.0)
  return 1.0 - torch.exp(-torch.square(excess) / (std**2))


def knee_ground_penalty(
  env: "ManagerBasedRlEnv",
  sensor_name: str,
) -> torch.Tensor:
  """Penalty for knee / shin contacts with the terrain.

  Returns 1 when knee contact is present and 0 otherwise.
  """
  sensor = env.scene.sensors[sensor_name]
  found = sensor.data.found
  if found.ndim > 1:
    found = torch.any(found, dim=1)
  return found.to(dtype=torch.float32)


def joint_target_penalty(
  env: "ManagerBasedRlEnv",
  target_by_regex: dict[str, float],
  std: float,
  asset_cfg: SceneEntityCfg = _DEFAULT_ASSET_CFG,
) -> torch.Tensor:
  """Penalty for joint deviations from a compact foot / leg target.

  Useful for discouraging excessive ankle roll / pitch deviations
  without rebuilding the whole pose reward.
  """
  asset: Entity = env.scene[asset_cfg.name]
  current_joint_pos = asset.data.joint_pos[:, asset_cfg.joint_ids]
  default_joint_pos = asset.data.default_joint_pos[:, asset_cfg.joint_ids]

  _, joint_names = asset.find_joints(asset_cfg.joint_names)
  indices, _, values = resolve_matching_names_values(
    data=target_by_regex,
    list_of_strings=joint_names,
  )

  target_joint_pos = default_joint_pos.clone()
  if len(indices) > 0:
    target_joint_pos[:, indices] = torch.tensor(
      values, device=env.device, dtype=current_joint_pos.dtype
    ).unsqueeze(0)

  error_squared = torch.square(current_joint_pos - target_joint_pos)
  return 1.0 - torch.exp(-torch.mean(error_squared, dim=1) / (std**2))
