import argparse
from isaaclab.app import AppLauncher

parser=argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
#process arguments passed when running script from cli

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app
#starting isaacsim

#Importing scene tools
import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation, ArticulationCfg
from isaaclab.sensors import Camera, CameraCfg
import torch
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from isaaclab.actuators import ImplicitActuatorCfg

#timestep of the scene, each step advances physics by 1/60th of a second
sim_cfg = sim_utils.SimulationCfg(dt=1.0/60.0)
#builds the physics renderer and engine, sim_cfg holds the actual running simulation
sim = sim_utils.SimulationContext(sim_cfg)
#aims viewport camera in the correct, default spot
sim.set_camera_view(eye=[2.5,2.5,2.0], target =[0.0,0.0,1.0])
#holds configuration of the base ground scene config
ground_cfg = sim_utils.GroundPlaneCfg()
'''
.func is a spawn method taking in the where (prim path, where this object 
lives on the usd stage, like the file path in the tree) and another argument
regarding the what so it knows what scene to build based on the config
'''
ground_cfg.func("/World/ground",ground_cfg)

#describes the light
light_cfg = sim_utils.DomeLightCfg(intensity=3000.0)
#spawns the light
light_cfg.func("/World/Light",light_cfg)


'''
spawns a physics-driven body, 3 args
1. prim path, where the robot actually goes on the stage
2. spawn, a cfg telling it how to create the prim. Usdfilecfg tells it to load the usd file from disk
'''

#This is the config for g1+inspire hands + twist2 neck, modify as needed
robot_cfg=ArticulationCfg(
    prim_path="/World/Robot", #sets the prim path so child things spawn oriented correctly to it
    spawn=sim_utils.UsdFileCfg(#spawn defines how to create the prim, set to do by loading a usd from a path
        usd_path="/home/g1/Downloads/unifiedusd/g1_inspire_neck.usd",
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
robot=Articulation(robot_cfg)
#defining the camera configuration to pass into camera method to build the camera sensor
camera_cfg = CameraCfg(
    prim_path="/World/Robot/twist2_neck/tilt_link/ZEDM/camera",
    spawn=None, # tells it to not build a new camera, bind to the optics of the ZED prim already there
    data_types=["rgb","distance_to_image_plane"], #list of buffers to captur from the renderer, rgb is rgb second one is depth sensing
    height=720,
    width=1280,
    update_period=0, #camera refresh rate; how often takes pictures. 0 means refreshes as fast as the sim itself, so 1/60 in our case
)
camera=Camera(camera_cfg)
sim.reset()
 # second half of cfg pattern; gives you camera itself
frame = 0
#loop to run script as long as the app is alive
while simulation_app.is_running():
    sim.step() #advances world and renders stuff
    camera.update(dt=sim.get_physics_dt()) #pulls latest rendered buffers (sampling rgb and dpeth data) acts as a refresher for sensor data refreshing the arrays that is in dict camera.data.output. polls every 1/60 second
    if frame == 20: #printing every 20 frames
        rgb = camera.data.output["rgb"]
        depth = camera.data.output["distance_to_image_plane"]
        print("rgb shape: ", rgb.shape,rgb.dtype) #[num cameras,h,w,color channels]
        print("depth shape:", depth.shape,depth.dtype)#[num cameras,h,w,1 channel]
        finite=depth[torch.isfinite(depth)] #filtering out pixels where camera ray hits nothing besides bg/sky
        if finite.numel() > 0:
            '''
            pulling the closest and farthest real distances the camera can see something other than just nothing (bg/sky)
            '''
            print("depth min/max (m):", finite.min().item(),finite.max().item()) 
        else:
            print("all depths non finite")
        OUTPATH="/home/g1/Downloads/unifiedusd"
        #transforms the tensor (type of array) in 3 ways drops the batch (N axis) to single image represented by 3d array, moves from gpu to cpu, and converts tensor to np array
        rgb_np = camera.data.output["rgb"][0].cpu().numpy()
        Image.fromarray(rgb_np).save(f"{OUTPATH}/zed_rgb.png")
        #flattens the image to a 2d array of distances in meters representing a grid (depth image)
        depth_np = camera.data.output["distance_to_image_plane"][0,...,0].cpu().numpy()
        # returns the depth image (2d array) but with a boolean mask (turns inf distances into value of false and otherwise value becomes true)
        finite_mask = np.isfinite(depth_np)
        #returns only elements where mask is true, as a flat 1d list now. (nearest distance)
        vmin = depth_np[finite_mask].min()
        # returns only elements where mask is true, as flat 1d list now (farthest distance)
        vmax = depth_np[finite_mask].max()
        #references the boolean 2d array to build a final, clean depth image where the infs are replaced with max depth float and ones below the max depth the float values kept as is
        depth_vis = np.where(finite_mask,depth_np,vmax)
        #references the boolean 2d array to build a final clean depth image where infs are replaced with 0.0 everything else as is kept in meters
        depth_metric = np.where(finite_mask,depth_np,0.0).astype(np.float32)
        np.save(f"{OUTPATH}/zed_depth.npy",depth_metric)
        print(f"saved zed_depth with shape {depth_metric.shape} and dtype {depth_metric.dtype}")


        #saves the 2d depth image as a colored png
        #turbo: sequenmce of colors corresponding to distance 
        plt.imsave(f"{OUTPATH}/zed_depth.png",depth_vis,cmap="turbo",vmin=vmin,vmax=vmax)
        print("saved zed_rgb.png and zed_depth.png")
        break
    frame+=1
simulation_app.close()



