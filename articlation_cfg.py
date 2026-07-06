import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args=parser.parse_args() #reads cli innput to create an args object with the inputted arguments

app_launcher = AppLauncher(args) #boots the simulator, including physics engine and renderer
simulation_app = app_launcher.app #handler of the running application; used to reference the application when getting status and such

import isaaclab.sim as sim_utils
#import for the toolbox that allows building of the world scene. import needs to happen after the others because its a post-boot import

#defining configuration object of the simulation. physics advances every 1/60th of a second
sim_cfg = sim_utils.SimulationCfg(dt=1.0 / 60.0)
#Instantiating the actual physics world from the configuraation above
sim = sim_utils.SimulationContext(sim_cfg)
#aiming viewport camera properly
sim.set_camera_view(eye=[2.5, 2.5, 2.0], target=[0.0, 0.0, 1.0])

#configuration object for the flat, ground plane with defaults
ground_cfg = sim_utils.GroundPlaneCfg()
#instantiating/spawning the actual world. first param is where, where the object should be in the stage tree second one tells what exactly to build
ground_cfg.func("/World/ground", ground_cfg)

#dome light config
light_cfg = sim_utils.DomeLightCfg(intensity=3000.0)
#spawning the light
light_cfg.func("/World/Light", light_cfg)

#articulation - the live object defining the 'tree' of rigid objects with states configured, physics properties, and how joints respond
from isaaclab.assets import Articulation, ArticulationCfg
from isaaclab.actuators import ImplicitActuatorCfg

#This is the articulation config for g1+inspire hands + twist2 neck, modify as needed
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
robot=Articulation(robot_cfg) #builder of this whole configuration; takes the configuration 'blueprint' and constructs into a real asset
sim.reset() #starts the actual physics, bringing actuators and joints and all that to life

# verifying everything is fine

print("num joints:", robot.num_joints)
neck_ids, neck_names = robot.find_joints(["neck_pan","neck_tilt"]) #joint data is stored in an array, just returning array-position based ID of joints and the name
print("actuator groups:", list(robot.actuators.keys())) #verifying what actuator groups actually got created
print(f"neck group drives:{robot.actuators['neck'].joint_names}")

#grabs the list of goal angles (starting one thats just 55 0's) as a seperate copy. this is starting pos
targets = robot.data.default_joint_pos.clone()

frame = 0 
while simulation_app.is_running():
    if frame==120: #checking every 2 seconds since physics is set to 60fps
        targets[:, neck_ids] = 1.0 #sets neck pan and neck tilt to rotation of 1.0 rad everything else in place
    robot.set_joint_position_target(targets)
    robot.write_data_to_sim() #Pushes the motor commands to the physics engine
    sim.step() #advances physics timestep
    robot.update(sim.get_physics_dt())

    if frame % 30 == 0:
        pan=robot.data.joint_pos[0,neck_ids[0]].item() #read back the neck pan data from the sim back into python
        tilt=robot.data.joint_pos[0,neck_ids[1]].item() #read back the neck tilt data from the sim back into python
        
        print(f"frame {frame:4d} pan={pan:+.3f} tilt={tilt:+.3f}")
    frame+=1

simulation_app.close()