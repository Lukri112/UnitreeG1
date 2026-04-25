from mjlab.tasks.registry import register_mjlab_task
from src.tasks.velocity.rl import VelocityOnPolicyRunner

from .env_cfgs import (
  unitree_g1_flat_env_cfg,
  unitree_g1_rough_env_cfg,
)
from .env_cfgs_crouch import unitree_g1_flat_crouch_deploy_env_cfg
from .env_cfgs_deploy98 import unitree_g1_flat_deploy98_env_cfg
from .rl_cfg import unitree_g1_ppo_runner_cfg

register_mjlab_task(
  task_id="Unitree-G1-Rough",
  env_cfg=unitree_g1_rough_env_cfg(),
  play_env_cfg=unitree_g1_rough_env_cfg(play=True),
  rl_cfg=unitree_g1_ppo_runner_cfg(),
  runner_cls=VelocityOnPolicyRunner,
)

register_mjlab_task(
  task_id="Unitree-G1-Flat",
  env_cfg=unitree_g1_flat_env_cfg(),
  play_env_cfg=unitree_g1_flat_env_cfg(play=True),
  rl_cfg=unitree_g1_ppo_runner_cfg(),
  runner_cls=VelocityOnPolicyRunner,
)

register_mjlab_task(
  task_id="Unitree-G1-Flat-Crouch-Deploy",
  env_cfg=unitree_g1_flat_crouch_deploy_env_cfg(),
  play_env_cfg=unitree_g1_flat_crouch_deploy_env_cfg(play=True),
  rl_cfg=unitree_g1_ppo_runner_cfg(),
  runner_cls=VelocityOnPolicyRunner,
)

register_mjlab_task(
  task_id="Unitree-G1-Flat-Deploy98",
  env_cfg=unitree_g1_flat_deploy98_env_cfg(),
  play_env_cfg=unitree_g1_flat_deploy98_env_cfg(play=True),
  rl_cfg=unitree_g1_ppo_runner_cfg(),
  runner_cls=VelocityOnPolicyRunner,
)