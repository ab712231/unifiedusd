# G1 + Neck + ZED — Project Glossary & Concepts

A plain-language reference for the key terms and ideas behind this project. Organized so you can skim
top-to-bottom or jump to a section. Everything is tied to *this* project (Unitree G1 + Inspire hands +
twist2 camera neck + ZED Mini), so the examples are real.

---

## 1. The project in one paragraph

The goal is a **single unified USD asset** = Unitree G1 robot + Inspire hands + the pan/tilt camera neck +
a ZED Mini camera, with physics preserved, for use in **NVIDIA Isaac Lab**. That asset is used to
**collect data** (camera images + joint motions), which trains a policy (e.g. GR00T), which is eventually
**deployed on the real G1** (sim-to-real). The asset file is `g1_inspire_neck.usd`.

---

## 2. The software stack: Isaac Sim vs Isaac Lab

**Isaac Sim** = the *engine*. The actual physics (PhysX) + rendering + the USD scene + the GUI. It's a
general-purpose simulator. You can do things by hand here: place a camera, drive a joint, look through a
camera. Think **the lab equipment + workbench**.

**Isaac Lab** = a *Python framework built on top of Isaac Sim* for robot learning. It gives you structured,
repeatable, scalable machinery: gym-style environments, actuator models, observation/action managers, many
parallel robots, headless runs, recorders, RL/imitation integration. Think **the experiment protocol +
automation**. Isaac Lab can't simulate anything by itself — it boots Isaac Sim underneath and *drives* it.

**The key difference:** Isaac Sim makes things physically happen (and lets you author/debug by hand). Isaac
Lab is where you systematically *run policies, collect datasets, and test* — in code, at scale,
reproducibly. Analogy: **Sim = game engine; Lab = the SDK/app you write against it.**

In this project: mounting/aiming the camera and confirming the neck rotates = **Sim (GUI)** work (done).
Collecting thousands of demos with realistic actuators and recording synchronized camera+joint data =
**Lab (code)** work (ahead).

---

## 3. USD & file concepts

- **USD (OpenUSD)** — the 3D scene/asset file format (Pixar's Universal Scene Description). Describes the
  robot's geometry, joints, physics, cameras, etc. Isaac uses it for everything.
- **USDA vs USDC** — USDA is human-readable text; USDC is compact binary. Same data. `zedm.usd` is text
  (so it's transparent/editable); the big G1 file is binary.
- **Prim** — any node in the USD scene tree (a link, a joint, a mesh, a camera…). Has a path like
  `/twist2_neck/tilt_link/ZEDM/camera`.
- **Xform** — a prim that holds a transform (translate / rotate / scale). Most structural prims are Xforms.
- **xformOp** — an individual transform operation on a prim (`xformOp:translate`, `xformOp:orient`,
  `xformOp:rotateXYZ`, `xformOp:scale`). The `xformOpOrder` lists the order they apply.
- **defaultPrim** — the "main" prim of a file, used when another file references it. Ours is the G1 root.
- **Sublayer** — stacking whole USD files on top of each other (like Photoshop layers). The unified asset
  sublayers `g1_inspire.usd` + the neck USD and adds the joint that connects them.
- **Reference** — pulling another asset in as a branch of the tree (how the ZED asset `zedm.usd` is brought
  into the robot under `tilt_link`).
- **Override (`over`)** — authoring changes to a referenced/sublayered prim in a stronger layer without
  editing the original file (how the neck mount + ZED placement are stored).
- **Instanceable / instance proxy** — a subtree marked as a reusable shared copy (saves memory). You
  **can't edit the children of an instanceable prim directly** — you must mark it non-instanceable first
  (we hit this when flipping object3/object_28 on the neck visuals).

---

## 4. Coordinate frames & units (a real source of bugs here)

- **Units** — Isaac/this asset uses **meters**. CAD/mesh files often come in **millimeters** (×1000 too
  big). The ZED STEP was already in meters; the neck visual meshes were in mm (had to be scaled ×0.001).
- **Up axis** — Isaac is **Z-up**. Many CAD/mesh exports are **Y-up**. Converting Y-up→Z-up = rotate +90°
  about X. The neck meshes needed this; it's why the "joints looked like they detached" early on (a visual
  frame bug, not a physics bug).
- **Robot forward** — for this G1, **+X is forward**, **+Z is up** (confirmed via the front d435 camera).
- **USD camera convention** — a camera looks down its **local −Z**, with +Y up, +X right. (So an
  un-rotated camera in a Z-up scene looks straight *down*.)
- **Euler caveat** — Euler angles (the X/Y/Z rotation numbers in the Isaac panel) **don't round-trip
  cleanly** between the GUI and the USD file (different order conventions). Pass rotation *intent*
  ("tilt down 20°") rather than typing euler numbers back and forth; quaternions are unambiguous.

---

## 5. Physics & articulation

- **PhysX** — the physics engine inside Isaac Sim that actually integrates motion, contacts, joints.
- **Rigid body** — a solid piece with mass/inertia that PhysX simulates (each robot link).
- **Articulation** — a connected set of links + joints simulated as **one** robot (better stability than
  loose bodies). The whole unified robot is **one articulation**.
- **Articulation root** — the prim marking where an articulation starts. There must be exactly **one** per
  robot; ours is the G1 **pelvis**. The neck and hands are *branches* of it (their old standalone-robot
  bits were deactivated).
- **Joint** — a connection between two links.
  - **Revolute joint** — a hinge (1 rotational DOF). `neck_pan` (about Z), `neck_tilt` (about Y), and all
    of G1's joints are revolute. The unified robot has **55** of them.
  - **Fixed joint** — rigidly welds two links. `neck_mount` fixes the neck base to the torso.
- **DOF (degree of freedom)** — one independent axis of motion = one revolute joint. 55 total; ~43 are
  *actuated* (29 G1 body + 12 driven hand joints + 2 neck); the other 12 are passive hand "follower" joints.
- **Self-collision** — whether a robot's own links collide with each other. Turned **off** here (so the
  neck doesn't fight the head). Inherited from G1's articulation setting.
- **Underactuated (the Inspire hands)** — fewer motors than joints. Each hand has 6 driven *proximal*
  joints; the *intermediate/distal* joints follow mechanically. This is by design, not a bug.

---

## 6. Articulation config & actuator config (the big topic — read this carefully)

### Articulation config (the container) — `ArticulationCfg`

**Plain definition:** the Isaac Lab Python object that fully describes one robot to the simulator —
*which* USD to load, *how* it spawns, what state it *starts* in, and how its joints are *driven*. It's the
single "recipe" Lab uses to put your robot in a scene and make it controllable. Think of it as the
**robot's setup sheet.**

**Its parts:**

| Part | What it is | For the neck/this project |
|---|---|---|
| **`spawn`** | *How to bring the asset in* — the `usd_path` + physics property overrides (solver iterations, self-collision, etc.) | point `usd_path` → `g1_inspire_neck.usd` |
| **`init_state`** | *The starting pose on reset* — root position/orientation + each joint's starting angle/velocity | add `neck_pan: 0.0`, `neck_tilt: 0.0` (start centered → camera forward) |
| **`soft_joint_pos_limit_factor`** | *Usable fraction of each joint's range* (e.g. 0.9 = use 90% of the limits) | inherited; no change needed |
| **`actuators`** | *The actuator config* — a dict of actuator **groups**, each defining gains/limits/armature/model for a set of joints | add a `"neck"` group |

```

**So: actuator config is *one part of* articulation config** (the `actuators={}` field). Adding the neck
touches two parts — `init_state.joint_pos` and `actuators`.

**Intentionality:** the USD's built-in values are auto-generated importer defaults (fine for casual Sim
testing). The `ArticulationCfg` is the **authoritative spec used for training/transfer**, so be deliberate
here — match the **physical limits** (`effort_limit`, `velocity_limit`) to the real servo, and treat the
**gains** (`stiffness`/`damping`/`armature`) as informed starting values you **tune by testing** (sag →
raise stiffness; jitter → raise damping). It's "informed + validated," not one-shot precision — and never
copy the USD's gain numbers (different scale).

### Actuator config (a part of the above)

**Actuator config = how each joint's motor responds to a command.** It does NOT decide *what* command to
send (that's the policy/task) — it defines *how hard/fast the motor pulls toward a target, and its limits.*

### The control loop
```
policy/teleop ──target angle──► actuator ──torque──► joint moves
  (the "brain":              (the "muscle": how strongly it
   WHERE to go)               pulls, with limits)
```

### Two layers (USD drives vs Lab config — not a contradiction)

| Layer | Lives in | Used by | Neck status |
|---|---|---|---|
| **1. USD drives** | the `.usd` file | **Isaac Sim** directly | ✅ done — this is what moved the neck in Sim |
| **2. Lab `ArticulationCfg`** | Python (Isaac Lab) | **Isaac Lab** | ⏳ add the neck when running the Lab pipeline |

- **USD drives** = portable default motor settings baked into the file, so the robot works standalone in
  any USD/PhysX app (why the neck moved in Isaac Sim with no extra code).
- **Lab `ArticulationCfg`** = the authoritative, code-managed control spec. At **load time** it *writes its
  numbers into PhysX*, overriding the USD values — and adds things the USD lacks (armature) or richer motor
  models. "Authored in Lab, applied to the sim."

**Why override if the USD already has values?**
1. The values are usually *different* (Lab values are tuned for training — e.g. Inspire finger USD
   stiffness `0.23` vs Lab `1000`; **Lab gains are a different scale, don't reuse USD numbers**).
2. **Armature** doesn't exist in the USD at all — only Lab adds it.
3. Lab can install a different **actuator model** (see below) the USD can't represent.
4. Lab can *choose not to* override: `stiffness=None` means "keep the USD value."
5. Code is version-controlled, tunable, swappable per task, and supports domain randomization.

### USD drive values (the actual per-joint attributes)

**Conceptually:** the joint behaves like a **spring + shock absorber** — a spring (*stiffness*) pulls it
toward the target angle, a damper (*damping*) resists motion to prevent overshoot, and the output torque is
capped at the *effort limit*. As the formula PhysX uses:
`torque = stiffness·(target − angle) − damping·angular_velocity, clamped to ±maxForce`

| Attribute | Meaning |
|---|---|
| `drive:angular:physics:type = force` | how gains are interpreted |
| `drive:angular:physics:stiffness` | **P gain (kp)** — how hard it pulls to target |
| `drive:angular:physics:damping` | **D gain (kd)** — velocity resistance |
| `drive:angular:physics:maxForce` | **torque limit** (neck: 0.9 N·m) |
| `drive:angular:physics:targetPosition` | the commanded angle |
| `physxJoint:maxJointVelocity` | speed cap (neck: ~6 rad/s) |
| `physics:lowerLimit/upperLimit` | joint range (neck pan ±2 rad, tilt ±1 rad; stored in **degrees**) |

### Key gain/limit terms

- **Stiffness (kp)** — how strongly the joint is pulled toward its target (the controller's spring
  constant). Too low → the head lags or droops; too high → it buzzes/vibrates. (neck: ~100 Lab-scale, tune.)

- **Damping (kd)** — resistance proportional to speed; the shock absorber that prevents overshoot and
  oscillation. Too little → wobble; too much → sluggish. (neck: ~10% of stiffness.)

- **Effort limit / maxForce** — the motor's maximum torque; a hard ceiling the real servo can't exceed.
  (neck servo ≈ 0.9 N·m.)

- **Velocity limit** — the joint's maximum speed. (neck ≈ 6 rad/s.)

- **Armature** — the motor's own rotational inertia (its rotor + gears), reflected through the gearbox to
  the joint. With the neck's **288:1** reduction this internal inertia dominates what the joint effectively
  "feels," so declaring it keeps a geared joint from buzzing or going unstable in sim — it's mainly a
  numerical-stability term. **Lab-only**, not in the USD. (neck: ~0.01, tune; your other groups use 0.0–0.1.)

- **Initial state** — the joint pose restored on reset; set to 0 so the neck starts centered (camera
  forward, level) each episode.

### How stiffness, damping, and armature work together (and where armature fits)

These are tuned as a *set*, not independently — this is the part that makes armature click:

- **Stiffness does the actual work** — it's what holds the joint at the commanded angle. You generally want
  it as high as the joint can tolerate (stiffer = holds position better, tracks commands more crisply).
- **Damping and armature are what *let* stiffness be high without the joint going unstable.** A light or
  heavily-geared joint driven with high stiffness and nothing to settle it will buzz, oscillate, or blow up
  in the physics solver.
- **Armature is the main stability knob for geared joints.** It adds effective inertia at the joint, which
  keeps the solver stable at higher stiffness. The trade-off: too much armature makes the joint feel heavy
  and slow to respond.
- **You almost never set armature to make the joint *move*** — it's the background steadiness that makes
  the *other* gains usable. Its importance scales with the **gear ratio** (the neck's 288:1 is high, so it
  benefits), with how **light** the link is, and with the **control timestep** (bigger steps need more
  stability margin).

**Practical tuning order:** set `effort_limit`/`velocity_limit` from the real servo → raise `stiffness`
until the joint holds position well → if it jitters or explodes, raise `armature` (and/or `damping`) until
it's stable → ease `stiffness` back if needed. So armature's *relevance* is entirely about letting
stiffness/damping do their job cleanly on a geared joint.

### Actuator models (the "recipe" turning a command into torque)
Same input (target), different realism of the motor physics:

| Model (Isaac Lab class) | How torque is computed | Realism |
|---|---|---|
| **Implicit PD** (`ImplicitActuatorCfg`) | PD, solved by PhysX; fixed torque cap | idealized "spring to target" |
| **Explicit PD** (`IdealPDActuatorCfg`) | same PD, computed in Python | same physics, you own the loop |
| **DC motor** (`DCMotorCfg`) | PD **+ torque–speed curve** (torque drops as speed rises) | models real servo saturation |
| **Learned net** (`ActuatorNetMLPCfg`/LSTM) | a net trained on **real motor data** predicts torque | captures friction/backlash/lag |

For the neck: **start with `ImplicitActuatorCfg`** (matches G1, simple, stable); **switch to `DCMotorCfg`
later** if you need tighter sim-to-real of the Dynamixel's dynamics.

### How the torque is decided each step (and who decides it)

**"Deciding the torque" = computing the single number (N·m) the motor applies to the joint, recomputed
every physics step (hundreds of Hz).** It's a continuous correction loop, not a one-time choice.

**Who decides:** the **actuator model** decides the final torque, via the **controller** inside it. The
controller (the PD law) *proposes* a raw torque; the model *finalizes* it by applying the motor's limits.
*Controller proposes, model finalizes.* (For an Implicit PD actuator these nearly coincide: model = PD + a
cap. A DC-motor/learned-net model adds more motor behavior around the same proposal step.)

The computation:
```
error  = target − current_angle
τ_raw  = stiffness · error  −  damping · current_speed     ← the CONTROLLER proposes
τ      = clamp(τ_raw, −effort_limit, +effort_limit)         ← the MODEL finalizes (motor's strength)
         (DC-motor model: also reduce τ by the torque–speed curve)
apply: acceleration = τ / (link_inertia + armature)         ← armature shapes the RESPONSE, not τ
       → new speed → new angle → repeat next step
```

How each concept factors in:

| Concept | Role in deciding/applying the torque |
|---|---|
| **target** | what it aims at; bigger gap → bigger `error` → more torque |
| **current angle** (feedback) | sets `error`; as the joint arrives, error → 0 so torque eases off automatically |
| **stiffness (kp)** | scales the pull (strength of the correction) |
| **current speed** (feedback) | feeds the damping term |
| **damping (kd)** | opposes motion (the brakes) — kills overshoot/oscillation |
| **effort_limit** | hard clamp on the final torque (motor's max strength) |
| **velocity_limit** | speed cap; in a DC-motor model, also shrinks available torque as speed rises |
| **armature** | does **not** enter the torque formula — it sits on the response side (`τ / (inertia+armature)`), shaping how that torque accelerates the joint; the main stability term |
| **actuator model** | picks *which* formula computes `τ` (Implicit/Ideal PD, DC-motor, or learned net) |

So in one line: **the controller multiplies the gap (stiffness) and speed (damping) to propose a torque; the
model clamps it to what the motor can deliver; armature then governs how hard that torque accelerates the
joint — all re-run every tick.**

### Recommended neck actuator group (for the Lab config, step in §10)
```python
"neck": ImplicitActuatorCfg(
    joint_names_expr=["neck_pan", "neck_tilt"],
    effort_limit=5.0,     # cap; real servo ~0.9 N·m — tune
    velocity_limit=6.0,   # rad/s (XC330)
    stiffness=100.0,      # Lab-scale, start moderate — tune
    damping=10.0,         # ~0.1 × stiffness — tune
    armature=0.01,        # geared servo; configs use 0.0–0.1
),
```

---

## 7. The camera (ZED Mini)

- **Camera prim (`UsdGeom.Camera`)** — defines a *viewpoint + lens* only. It does **not** itself produce
  pixels; a render output must be attached at runtime. Ours is `/twist2_neck/tilt_link/ZEDM/camera`.
- **ZED Mini** — a Stereolabs **stereo** RGB-D camera. Two lenses 63 mm apart; the SDK does stereo matching
  on-device and outputs **rectified left RGB + a depth map**.
- **Intrinsics** — the lens math that sets field of view:
  - **focalLength** (3.06 mm) and **aperture** (horizontal 5.91, vertical 3.324 mm) → **FOV ≈ 88°×57°**.
  - FOV depends only on the ratio aperture/focalLength.
  - **clippingRange** (0.1–15 m) — near/far planes; set to match the ZED's depth range.
  - (Datasheet's raw 102° max FOV includes lens distortion a pinhole sim can't reproduce; we use the
    rectified ~88°, which is what the SDK actually delivers.)
- **RGB vs depth** — both come from the **same camera**, as separate **output channels (annotators)**. You
  do **not** need a separate depth camera.
- **Ground-truth depth** — in sim, take the renderer's exact depth rather than simulating stereo matching.
  Cleaner and what you'd train on. (Only simulate stereo if you specifically want ZED depth *noise*.)
- **Annotator / render product** — the render output attached to a camera that actually produces an image
  (rgb, `distance_to_image_plane` for depth, segmentation, etc.). Configured in **Lab** when you register
  the camera as a sensor, e.g. `data_types=["rgb", "distance_to_image_plane"]`.
- **Left vs right feed** — the ZED is stereo, but for this project use **one camera (the left eye) + GT
  depth**. The deployed policy consumes rectified RGB + depth, which a single camera reproduces. Add a
  second camera only if your policy ingests raw stereo pairs.
- **Body mesh vs camera** — the ZED shell mesh is **cosmetic**; the `camera` prim is the **sensor**. They
  were intentionally decoupled in the scene (body seated as you placed it; camera kept facing forward).
  Only the camera's viewpoint/aim affects collected data.

---

## 8. The end-to-end pipeline & sim-to-real

```
1. Isaac Lab: unified USD + actuator config = controllable, realistic robot
              teleop/script tasks; ZED renders RGB(+depth)
              RECORD: images + joint states + actions  ──► dataset
2. convert to LeRobot dataset format  (convert_twist2_to_lerobot.py)
3. Fine-tune GR00T on that dataset    (Isaac-GR00T repo, GPU training — NOT in Isaac Lab)
4. (optional) Evaluate the policy back in Isaac Lab before hardware
5. Deploy: a runtime on the robot's compute reads real ZED + encoders → GR00T
           → joint targets → real motors   (Isaac Lab is NOT running here)
```

- **Sim-to-real** — making a policy trained in sim work on the real robot. Hinges on matching the
  **interface** (same joints/order incl. the neck = the *action* space; same camera image = the
  *observation*) and the **dynamics** (realistic actuators so learned behavior transfers).
- **Why each piece of this project matters for transfer:**
  - Unified USD = the robot that generates data.
  - ZED intrinsics + forward aim = the sim image matches the real image.
  - Neck in the actuator config = the neck is part of the action space the policy learns to output, and
    moves realistically.
- **Isaac Lab's role in deployment** — it's mostly a **training-time / data-collection / evaluation** tool;
  it does **not** run on the robot. A lightweight runtime (e.g. `lerobot_twist2_deploy`) runs the policy on
  the real hardware.
- **GR00T** — NVIDIA's vision-language-action robot foundation model; fine-tuned on your dataset, then
  deployed. Heavy — usually runs on a Jetson/external GPU, not the stock onboard controller.
- **LeRobot** — a common dataset/training format/toolkit; the bridge between collected data and GR00T.

---

## 9. Project files

| File | Role |
|---|---|
| `g1_inspire_neck.usd` | **The deliverable.** Unified G1 + hands + neck + ZED. One articulation, 55 DOF. Use this in Lab. |
| `g1_inspire_neck_TEST.usd` | Standalone viewer: pins the pelvis (so it doesn't fall) + ground + lights. **Inspection only.** |
| `g1_inspire.usd` | G1 29-DOF + Inspire hands, already one articulation (our working copy). |
| `neck_v9/twist2_neck_v9.usd` | The camera neck (visual + physics fixes baked in). |
| `neck_v9/zedm.usd` | The ZED Mini asset (body mesh + `camera` prim). Open directly to view the bare camera. |
| `ZEDM.step` | Source CAD for the ZED Mini (tessellated into `zedm.usd`). |
| `HANDOFF.md` | Step-by-step status + next steps. |
| `PROJECT_GLOSSARY.md` | This file. |

---

## 10. What's done & what's next

**Done (the asset is functionally complete):**
- Unified single articulation (G1 + hands + neck), 55 DOF, self-collisions off, one root.
- Camera neck mounted to the torso; pan/tilt **confirmed actuating** in Isaac Sim (USD drives work).
- ZED Mini integrated: body mesh + `camera` prim, real intrinsics, aimed forward, 0.1–15 m clip.
- USD-level drives verified consistent with G1 for all joints incl. the neck.

**Next:**
1. **Sim sanity check** — open `g1_inspire_neck_TEST.usd`, Play: robot stable, no NaN, arms/hands/neck
   actuate, look through `camera`.
2. **Confirm which env/config your Lab pipeline actually loads** (prerequisite for the edits below).
3. **Lab articulation config** — point `usd_path` at `g1_inspire_neck.usd`; add `neck_pan`/`neck_tilt` to
   init state + the `"neck"` actuator group (incl. **armature**).
4. **Register `camera` as an RGB(+depth) sensor** in the env; add neck to the action space, camera to
   observations/recorder.
5. **Collect → LeRobot → fine-tune GR00T → deploy.**

---

## 11. Gotchas learned (so they don't bite again)

- **Editing USD files while Isaac has them open desyncs the session** → `KeyError: <class 'NoneType'>`,
  unclickable prims, body/camera showing mismatched stale poses. Fix: **fully quit Isaac** (New Stage is
  not enough) and reopen; do edits with Isaac closed.
- **Euler angles don't round-trip** between the GUI panel and USD — communicate rotation *intent*, not
  euler numbers.
- **Mesh units/frame** — CAD meshes may be mm + Y-up + global; kinematics are m + Z-up. Mismatch makes
  parts look huge/detached. (Fixed on the neck.)
- **Camera frustum gizmo size = far-clip** — a huge far clip draws a planet-sized cone. Keep it sane
  (15 m here). Hide camera gizmos via viewport **eye icon → Show By Type → Cameras**.
- **Lab gains ≠ USD gains** (different scale) — never copy USD drive numbers into the Lab `ArticulationCfg`.
- **Instanceable prims** block editing their children — mark non-instanceable first.
- **Floating base** — the robot free-falls standalone (no `PhysicsScene`/ground); correct for Lab. Use the
  TEST file (pins the pelvis) for manual inspection.
