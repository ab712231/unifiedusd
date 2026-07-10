import pathlib

import isaaclab.sim as sim_utils
from isaaclab.assets import ArticulationCfg
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.sensors import CameraCfg
import isaaclab.sim as _sim_utils_cam

# Directory this config lives in — the USD assets sit alongside it. Loading the
# robot USD relative to here means the sim always uses the same unifiedusd/ that
# run_isaac_sim_loop.py imports this config from AND that _fix_usd_float_scales()
# patches, instead of a hardcoded absolute path to some other copy.
_UNIFIEDUSD_DIR = pathlib.Path(__file__).resolve().parent

# Spawn a fresh ZED camera as a direct child of tilt_link (NOT under ZEDM).
#
# Why not spawn=None on tilt_link/ZEDM/camera: wrapping the authored camera makes
# Isaac Lab's Camera sensor traverse the ZEDM prim's transform stack, which
# carries a scalar-float xformOp:scale in the source USD that XformPrimView can't
# convert ("no registered converter ... from float"). Spawning under tilt_link
# instead gives a clean, freshly-authored prim and never walks through ZEDM.
#
# The offset reproduces the authored camera's forward-facing pose relative to
# tilt_link: rot (0.5, 0.5, -0.5, -0.5) puts camera forward (-Z) along robot +X
# and camera up (+Y) along robot +Z (verified). Intrinsics match the ZED Mini:
# focal 3.06mm + horizontal_aperture 5.91 → H-FOV 88°, and at 16:9 (1280x720)
# the derived vertical aperture 3.324 → V-FOV 57° (exact spec); clip 0.1–15 m.
camera_cfg = CameraCfg(
    prim_path="{ENV_REGEX_NS}/Robot/twist2_neck/tilt_link/zed_cam",
    spawn=_sim_utils_cam.PinholeCameraCfg(
        focal_length=3.06,
        horizontal_aperture=5.91,
        clipping_range=(0.1, 15.0),
    ),
    offset=CameraCfg.OffsetCfg(
        pos=(0.01403, -0.01534, 0.03088),
        rot=(0.5, 0.5, -0.5, -0.5),
        convention="opengl",
    ),
    data_types=["rgb"],
    height=720,
    width=1280,
    update_period=0.0,
)

robot_cfg=ArticulationCfg(
    prim_path="/World/Robot", #sets the prim path so child things spawn oriented correctly to it
    spawn=sim_utils.UsdFileCfg(#spawn defines how to create the prim, set to do by loading a usd from a path
        usd_path=str(_UNIFIEDUSD_DIR / "g1_inspire_neck.usd"),
        rigid_props=sim_utils.RigidBodyPropertiesCfg(disable_gravity=False), #applying base physics properties to rigid bodies. gravity acts on mass and mass is a per body thing
    
    #setting properties of the articulation as a whole
    articulation_props=sim_utils.ArticulationRootPropertiesCfg(
            fix_root_link=True, #pin the root (pelvis) to world. balances pelvis so the body doesn't fall on itself
            enabled_self_collisions = False, #Not computing collisions between robot's own body parts. uneccessary here; computationally expensive
            solver_position_iteration_count=8,#physX, has to find the set of forces/velocities at every physics step meeting cxonstraints. Its an iterative tuning process, this just defines how many iterations
            solver_velocity_iteration_count=4,#iteration count specifically for the velocity aspect of it
        ),  
    ),  
    #defining initial, spawning state

    #PD controller in this case takes in 3 55-long arrays: target, current, current velocities
    #outputs 55 toruqes

    #effort limit - max torque motor can produce no matter what
    #velocity limit - hard limit on speed joint can spin in rad/s
    #stiffness - spring constant equivalent of a motor used to calculate how much force is needed. T=stiffness*error(how much angle needs to change) - damping*currentvelocity
    #damping - shock absorber of the joint that resists velocity
    #armature - think of as rotational inertia of the motor itself
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0,0.0,1.0),
        joint_pos={".*":0.0}, #sets default position of all joints to 0 radians (neutral)
        joint_vel={".*":0.0},# starts joints at zero velocity
    ),
    actuators={
        "legs": ImplicitActuatorCfg( #actuator model - term for whole simulated motor combining limits+inertia+controller
        joint_names_expr=[".*_hip_yaw_joint",".*_hip_roll_joint",".*_hip_pitch_joint",".*_knee_joint"],
        effort_limit=200.0, velocity_limit=30.0,stiffness={".*_hip_.*": 100.0,".*_knee_joint": 200.0},damping={".*_hip_.*": 2.5, ".*_knee_joint":5.0},armature=0.03,
    ),
    "feet": ImplicitActuatorCfg(
        joint_names_expr=[".*_ankle_pitch_joint",".*_ankle_roll_joint"],
        effort_limit=50.0, velocity_limit=37.0,stiffness=20.0, damping=0.2, armature=0.03,
    ),
    "waist": ImplicitActuatorCfg(
        joint_names_expr=["waist_.*_joint"],
        effort_limit=88.0, velocity_limit=37.0,stiffness=5000.0, damping=5.0, armature=0.001,
    ),
    "arms": ImplicitActuatorCfg(
        joint_names_expr=[".*_shoulder_pitch_joint",".*_shoulder_roll_joint",".*_shoulder_yaw_joint",".*_elbow_joint", ".*_wrist_.*_joint"],
        effort_limit=300.0, velocity_limit=100.0,stiffness=3000.0, damping=100.0,armature=0.001,
    ),
    "hands": ImplicitActuatorCfg(
        joint_names_expr=[".*_index_.*",".*_middle_.*", ".*_ring_.*",".*_pinky_.*",".*_thumb_.*"],
        effort_limit=30.0, velocity_limit=10.0,stiffness=10.0, damping=0.2, armature=0.001,
    ),
    "neck": ImplicitActuatorCfg(
        joint_names_expr=["neck_pan", "neck_tilt"],
        effort_limit=5.0, velocity_limit=6.0,stiffness=100.0, damping=10.0, armature=0.01,
    ),
    },


)