# Implementation Plan — What's Left & Exactly How

Action-oriented guide for finishing the integration of `g1_inspire_neck.usd` into the Isaac Lab pipeline.
Concepts are in `PROJECT_GLOSSARY.md`; this doc is the *how-to*.

**Where things stand:** the unified USD asset is **functionally complete** — one articulation (55 DOF),
neck mounted, pan/tilt actuate in Isaac Sim, ZED `camera` placed/aimed with real intrinsics. Everything
remaining is **Isaac Lab / pipeline** work (code), not asset work.

Legend: 🔲 to do · ✅ done · ⚠️ confirm before relying on it

---

## Step 0 — Sim sanity check (5 min, do first) 🔲

Catch any regression before touching Lab code.

1. **Fully quit Isaac Sim**, then open `g1_inspire_neck_TEST.usd` (pins the pelvis so it won't fall; has
   ground + lights).
2. Press **Play** ▶ and confirm:
   - Robot holds still — no jitter / drift / explosion.
   - **Console has no NaN / physics errors.**
   - **Arms + hands actuate** — set a wrist or finger Drive `Target Position` and watch it move.
   - **Neck pan/tilt** move in range; switch the viewport camera to **`camera`** and watch the view re-aim.
   - Looking through `camera`: RGB renders, framing sane, nothing weirdly clipped.

✅ Pass = the asset is validated. Move on.
**Gotcha:** edit USD files only with Isaac closed (open sessions desync → `KeyError`/unclickable prims).

---

## Step 1 — Confirm which env/config your pipeline actually loads ⚠️ (prerequisite)

Everything below edits the robot config and the env. We must edit the *right* files. Candidate found:
`/home/g1/Project/unitree_sim_isaaclab/robots/unitree.py` → `G129_CFG_WITH_INSPIRE_HAND`, but it currently
points at a **different** inspire USD:
`assets/robots/g1-29dof-inspire-base-fix-usd/g1_29dof_with_inspire_rev_1_0.usd`.

**Do this:**
- Identify the launch command / task you use to collect data (the script you actually run).
- Trace which `ArticulationCfg` and which task/env `cfg` it imports.
- Note: (a) the robot cfg symbol, (b) its current `usd_path`, (c) the **exact joint names** that config
  expects (the inspire USD it points to may name hand joints differently than ours, e.g.
  `left_hand_index_0_joint` vs `L_index_proximal_joint`).

**Why it matters:** actuator groups match joints by name pattern (`joint_names_expr`). If the names in the
config don't match the names in `g1_inspire_neck.usd`, the actuators silently won't bind. Confirm names
line up (or plan to adjust patterns).

Verify joint names in our asset:
```bash
BPY=/snap/blender/7480/5.1/python/bin/python3.13
$BPY -c "from pxr import Usd; s=Usd.Stage.Open('/home/g1/Downloads/unifiedusd/g1_inspire_neck.usd'); \
print([p.GetName() for p in s.Traverse() if p.GetTypeName()=='PhysicsRevoluteJoint'])"
```

---

## Step 2 — Point the config at the unified USD 🔲

In the confirmed robot cfg:
```python
spawn=sim_utils.UsdFileCfg(
    usd_path="/home/g1/Downloads/unifiedusd/g1_inspire_neck.usd",   # was the old inspire USD
    ...
)
```
(Or copy the asset into the repo's `assets/robots/` and use the `{project_root}/...` style they use.)

**Verify:** the env loads the new USD and reports **55 DOF** (not the old count). If DOF is wrong, the
wrong file is loading.

---

## Step 3 — Add the neck to init state + actuators 🔲

In the same `ArticulationCfg`:

**3a. Initial joint positions** (start centered → camera forward, level):
```python
init_state=ArticulationCfg.InitialStateCfg(
    joint_pos={
        ... existing entries ...,
        "neck_pan": 0.0,
        "neck_tilt": 0.0,
    },
),
```

**3b. Neck actuator group** (add alongside legs/waist/arms/hands). Includes **armature** (only lives here,
not in the USD):
```python
from isaaclab.actuators import ImplicitActuatorCfg

"neck": ImplicitActuatorCfg(
    joint_names_expr=["neck_pan", "neck_tilt"],
    effort_limit=5.0,     # cap; real XC330 ~0.9 N·m — tune
    velocity_limit=6.0,   # rad/s
    stiffness=100.0,      # Lab-scale (NOT the USD's 0.146) — tune
    damping=10.0,         # ~0.1 × stiffness — tune
    armature=0.01,        # geared servo; your configs use 0.0–0.1
),
```

**Notes**
- Lab gains are a **different scale** than USD drive values — do not copy `0.146` from the USD.
- Tuning: head sags → raise `stiffness`; jitters/oscillates → raise `damping`.
- Later, for tighter sim-to-real of the servo dynamics, swap this group to `DCMotorCfg`.

**Verify:** after load, `robot.data.joint_names` includes `neck_pan`, `neck_tilt`; commanding their targets
moves the neck and the camera re-aims; no NaN at reset.

---

## Step 4 — Register the ZED `camera` as a sensor (RGB + depth) 🔲

Add a camera sensor to the env scene cfg, pointing at the prim, requesting both channels:
```python
from isaaclab.sensors import CameraCfg
import isaaclab.sim as sim_utils

zed_camera = CameraCfg(
    prim_path="{ENV_REGEX_NS}/Robot/twist2_neck/tilt_link/ZEDM/camera",  # adjust NS to your scene
    update_period=0.0,                 # every step; or match your control dt
    height=480, width=848,             # pick a ZED output size (e.g. 1280x720, 848x480)
    data_types=["rgb", "distance_to_image_plane"],   # RGB + ground-truth depth
    spawn=None,                        # IMPORTANT: camera already exists in the USD — don't spawn a new one
)
```

**Notes**
- `spawn=None` reuses the existing camera prim (with the intrinsics we baked: focal 3.06, ~88°×57° FOV,
  clip 0.1–15). If you let it spawn, it overwrites those — keep `spawn=None`.
- `distance_to_image_plane` = ground-truth depth (recommended over simulating stereo).
- Resolution/rate are sim choices (not in the USD). Match what your policy/real ZED uses.
- The prim path namespace depends on how the robot is added (e.g. `{ENV_REGEX_NS}/Robot/...`). Confirm the
  robot's prim root name in the scene cfg and prepend correctly.

**Verify:** sensor initializes; `camera.data.output["rgb"]` and `["distance_to_image_plane"]` have the right
shape; preview shows the head view; depth values are sane (≈0.1–15 m range).

---

## Step 5 — Wire neck into actions & camera into observations 🔲

- **Action space:** add `neck_pan`, `neck_tilt` to the joint-position action term so the policy/teleop can
  command the head. Match the order your real-robot action vector expects.
- **Observations / recorder:** add the camera `rgb` (and `depth` if used) and the neck joint states to what
  gets recorded each step, so demos contain head view + head motion.

**Verify:** an episode records synchronized {camera image(s), all joint states incl. neck, actions incl.
neck} with no shape/length mismatches.

---

## Step 6 — Validate the full env (1 environment) 🔲

Run a single-env smoke test:
- Loads one articulation, **55 DOF**, no warnings about unbound joints.
- Actuators bind: legs/waist/arms/hands/**neck** all present in actuator groups.
- Camera renders RGB + depth each step.
- Step the env with zero/neutral actions for a few hundred steps → **no NaN, no explosion**, robot stable.
- Command a neck sweep → head turns, camera view changes in the recorded frames.

Only scale to many parallel envs after the single-env test passes.

---

## Step 7 — Collect data 🔲

- Run your teleop/scripted collection task with the updated env.
- Record episodes (camera + joint states + actions, incl. the neck).
- Sanity-check a few episodes: images look right, neck moves are captured, timestamps aligned.

---

## Step 8 — Convert to LeRobot format 🔲

- Use `/home/g1/Documents/convert_twist2_to_lerobot.py` (or your current converter).
- ⚠️ Update it for the **new modalities/dims**: the action/observation vectors now include the **neck
  (2 extra DOF)** and the **ZED camera (RGB + depth)**. Make sure the converter maps these correctly and
  the resulting dataset schema matches what GR00T expects.

**Verify:** dataset loads in LeRobot tooling; feature keys/shapes correct (image(s), state, action with the
neck included).

---

## Step 9 — Fine-tune GR00T 🔲

- Train in the `Isaac-GR00T` repo (`Isaac-GR00T-n1d7` / `-n1d6`) on the LeRobot dataset. (This is a GPU
  training run, **outside** Isaac Lab.)
- Ensure the model's input/output spec matches your data: camera image(s) in, action vector (incl. neck)
  out.

**Verify:** training converges; eval on held-out episodes looks reasonable.

---

## Step 10 — (Optional) Evaluate in sim, then deploy 🔲

- Optionally load the fine-tuned policy back into the Isaac Lab env to sanity-check before hardware.
- **Deploy** with `lerobot_twist2_deploy`: on the robot's compute (likely a Jetson/external GPU), read the
  **real ZED** (RGB + depth) + joint encoders → GR00T → joint targets (incl. neck) → real motors.

**Verify:** observation/action interface matches sim exactly (same image format, same joint order incl.
neck). Mismatches here are the usual cause of sim-to-real failure.

---

## Critical cross-checks (the things that quietly break)

1. **Joint names match** between the config's `joint_names_expr` and the USD (Step 1). Unbound = silent.
2. **Action/observation vector order** is identical in sim and on the real robot (incl. where the neck sits
   in the vector).
3. **Camera `spawn=None`** so the baked intrinsics survive (Step 4).
4. **Lab gains, not USD gains** (Step 3) — different scale.
5. **Converter updated** for the new neck DOFs + camera channels (Step 8).
6. **Edit USD only with Isaac closed** (Step 0 gotcha).

---

## Quick status board

| Step | What | Status |
|---|---|---|
| 0 | Sim sanity check | 🔲 do first |
| 1 | Confirm env/config loaded | 🔲 ⚠️ prerequisite |
| 2 | Point `usd_path` → unified USD | 🔲 |
| 3 | Neck init state + actuator group (+armature) | 🔲 |
| 4 | Register ZED camera sensor (RGB+depth) | 🔲 |
| 5 | Neck→actions, camera→observations/recorder | 🔲 |
| 6 | Validate single env (55 DOF, renders, stable) | 🔲 |
| 7 | Collect data | 🔲 |
| 8 | Convert to LeRobot (update for neck+camera) | 🔲 |
| 9 | Fine-tune GR00T | 🔲 |
| 10 | Evaluate in sim → deploy on real G1 | 🔲 |
