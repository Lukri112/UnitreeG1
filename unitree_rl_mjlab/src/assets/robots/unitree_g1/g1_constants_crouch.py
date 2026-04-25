"""
Unitree G1 constants  ALWAYS-CROUCH variant.

This config is identical to g1_constants.py except that the robot
initializes in a deeper crouched (knees-bent) nominal pose.

Intended use:
- RL training of ALWAYS-CROUCH walking policies
- clean separation from standard flat-walking configs
"""

from pathlib import Path

import mujoco

from src import SRC_PATH
from mjlab.actuator import BuiltinPositionActuatorCfg
from mjlab.entity import EntityArticulationInfoCfg, EntityCfg
from mjlab.utils.actuator import (
    ElectricActuator,
    reflected_inertia_from_two_stage_planetary,
)
from mjlab.utils.os import update_assets
from mjlab.utils.spec_config import CollisionCfg


# ---------------------------------------------------------------------
# MJCF and assets
# ---------------------------------------------------------------------

G1_XML: Path = (
    SRC_PATH / "assets" / "robots" / "unitree_g1" / "xmls" / "g1.xml"
)
assert G1_XML.exists()


def get_assets(meshdir: str) -> dict[str, bytes]:
    assets: dict[str, bytes] = {}
    update_assets(assets, G1_XML.parent / "assets", meshdir)
    return assets


def get_spec() -> mujoco.MjSpec:
    spec = mujoco.MjSpec.from_file(str(G1_XML))
    spec.assets = get_assets(spec.meshdir)
    return spec


# ---------------------------------------------------------------------
# Actuator config (UNCHANGED)
# ---------------------------------------------------------------------

ROTOR_INERTIAS_5020 = (0.139e-4, 0.017e-4, 0.169e-4)
GEARS_5020 = (1, 1 + (46 / 18), 1 + (56 / 16))
ARMATURE_5020 = reflected_inertia_from_two_stage_planetary(
    ROTOR_INERTIAS_5020, GEARS_5020
)

ROTOR_INERTIAS_7520_14 = (0.489e-4, 0.098e-4, 0.533e-4)
GEARS_7520_14 = (1, 4.5, 1 + (48 / 22))
ARMATURE_7520_14 = reflected_inertia_from_two_stage_planetary(
    ROTOR_INERTIAS_7520_14, GEARS_7520_14
)

ROTOR_INERTIAS_7520_22 = (0.489e-4, 0.109e-4, 0.738e-4)
GEARS_7520_22 = (1, 4.5, 5)
ARMATURE_7520_22 = reflected_inertia_from_two_stage_planetary(
    ROTOR_INERTIAS_7520_22, GEARS_7520_22
)

ROTOR_INERTIAS_4010 = (0.068e-4, 0.0, 0.0)
GEARS_4010 = (1, 5, 5)
ARMATURE_4010 = reflected_inertia_from_two_stage_planetary(
    ROTOR_INERTIAS_4010, GEARS_4010
)

ACTUATOR_5020 = ElectricActuator(ARMATURE_5020, 37.0, 25.0)
ACTUATOR_7520_14 = ElectricActuator(ARMATURE_7520_14, 32.0, 88.0)
ACTUATOR_7520_22 = ElectricActuator(ARMATURE_7520_22, 20.0, 139.0)
ACTUATOR_4010 = ElectricActuator(ARMATURE_4010, 22.0, 5.0)

NATURAL_FREQ = 10 * 2.0 * 3.1415926535
DAMPING_RATIO = 2.0

def _stiffness(a): return a * NATURAL_FREQ**2
def _damping(a): return 2.0 * DAMPING_RATIO * a * NATURAL_FREQ

G1_ACTUATOR_5020 = BuiltinPositionActuatorCfg(
    target_names_expr=(
        ".*_elbow_joint",
        ".*_shoulder_pitch_joint",
        ".*_shoulder_roll_joint",
        ".*_shoulder_yaw_joint",
        ".*_wrist_roll_joint",
    ),
    stiffness=_stiffness(ARMATURE_5020),
    damping=_damping(ARMATURE_5020),
    effort_limit=ACTUATOR_5020.effort_limit,
    armature=ACTUATOR_5020.reflected_inertia,
)

G1_ACTUATOR_7520_14 = BuiltinPositionActuatorCfg(
    target_names_expr=(".*_hip_pitch_joint", ".*_hip_yaw_joint", "waist_yaw_joint"),
    stiffness=_stiffness(ARMATURE_7520_14),
    damping=_damping(ARMATURE_7520_14),
    effort_limit=ACTUATOR_7520_14.effort_limit,
    armature=ACTUATOR_7520_14.reflected_inertia,
)

G1_ACTUATOR_7520_22 = BuiltinPositionActuatorCfg(
    target_names_expr=(".*_hip_roll_joint", ".*_knee_joint"),
    stiffness=_stiffness(ARMATURE_7520_22),
    damping=_damping(ARMATURE_7520_22),
    effort_limit=ACTUATOR_7520_22.effort_limit,
    armature=ACTUATOR_7520_22.reflected_inertia,
)

G1_ACTUATOR_4010 = BuiltinPositionActuatorCfg(
    target_names_expr=(".*_wrist_pitch_joint", ".*_wrist_yaw_joint"),
    stiffness=_stiffness(ARMATURE_4010),
    damping=_damping(ARMATURE_4010),
    effort_limit=ACTUATOR_4010.effort_limit,
    armature=ACTUATOR_4010.reflected_inertia,
)

G1_ACTUATOR_WAIST = BuiltinPositionActuatorCfg(
    target_names_expr=("waist_pitch_joint", "waist_roll_joint"),
    stiffness=_stiffness(ARMATURE_5020 * 2),
    damping=_damping(ARMATURE_5020 * 2),
    effort_limit=ACTUATOR_5020.effort_limit * 2,
    armature=ACTUATOR_5020.reflected_inertia * 2,
)

G1_ACTUATOR_ANKLE = BuiltinPositionActuatorCfg(
    target_names_expr=(".*_ankle_pitch_joint", ".*_ankle_roll_joint"),
    stiffness=_stiffness(ARMATURE_5020 * 2),
    damping=_damping(ARMATURE_5020 * 2),
    effort_limit=ACTUATOR_5020.effort_limit * 2,
    armature=ACTUATOR_5020.reflected_inertia * 2,
)


# ---------------------------------------------------------------------
# Keyframes (DEEPER CROUCH)
# ---------------------------------------------------------------------

KNEES_BENT_KEYFRAME = EntityCfg.InitialStateCfg(
    pos=(0, 0, 0.65),  # lower base height (was 0.78)
    joint_pos={
        ".*_hip_pitch_joint": -0.77,     # deeper hip flexion
        ".*_knee_joint": 1.32,           # more knee bend
        ".*_ankle_pitch_joint": -0.68,   # ankle compensation to keep foot flat
        ".*_elbow_joint": 0.6,
        "left_shoulder_roll_joint": 0.2,
        "left_shoulder_pitch_joint": 0.2,
        "right_shoulder_roll_joint": -0.2,
        "right_shoulder_pitch_joint": 0.2,
    },
    joint_vel={".*": 0.0},
)


# ---------------------------------------------------------------------
# Collision config
# ---------------------------------------------------------------------

FULL_COLLISION = CollisionCfg(
    geom_names_expr=(".*_collision",),
    condim={r"^(left|right)_foot[1-7]_collision$": 3, ".*_collision": 1},
    priority={r"^(left|right)_foot[1-7]_collision$": 1},
    friction={r"^(left|right)_foot[1-7]_collision$": (0.6,)},
)


# ---------------------------------------------------------------------
# Final articulation + robot config
# ---------------------------------------------------------------------

G1_ARTICULATION = EntityArticulationInfoCfg(
    actuators=(
        G1_ACTUATOR_5020,
        G1_ACTUATOR_7520_14,
        G1_ACTUATOR_7520_22,
        G1_ACTUATOR_4010,
        G1_ACTUATOR_WAIST,
        G1_ACTUATOR_ANKLE,
    ),
    soft_joint_pos_limit_factor=0.9,
)


def get_g1_robot_cfg() -> EntityCfg:
    """Get a fresh G1 robot configuration instance (ALWAYS-CROUCH)."""
    return EntityCfg(
        init_state=KNEES_BENT_KEYFRAME,
        collisions=(FULL_COLLISION,),
        spec_fn=get_spec,
        articulation=G1_ARTICULATION,
    )


# ---------------------------------------------------------------------
# Action scale (UNCHANGED)
# ---------------------------------------------------------------------

G1_ACTION_SCALE: dict[str, float] = {}
for a in G1_ARTICULATION.actuators:
    e = a.effort_limit
    s = a.stiffness
    for n in a.target_names_expr:
        G1_ACTION_SCALE[n] = 0.25 * e / s
