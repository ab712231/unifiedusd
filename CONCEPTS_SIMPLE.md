# Simple Concepts & Logic Flows

The easy-to-read companion to `PROJECT_GLOSSARY.md`. Same ideas, stripped down to plain definitions and
simple flow diagrams. Read this first; go to the glossary when you want the detail.

---

## The big picture (what we're doing)

```
Build ONE robot file (G1 + hands + neck + camera)
        ↓
Load it in Isaac Lab → drive it around, camera records what it sees
        ↓
Use those recordings to train a policy (GR00T)
        ↓
Put the trained policy on the real robot
```

The robot file is `g1_inspire_neck.usd`. It's finished. Everything left is on the software/training side.

---

## Two pieces of software

- **Isaac Sim** = the **world**. Runs the physics, draws everything, lets you click around by hand.
- **Isaac Lab** = the **control room** built on top of Sim. Code that runs experiments at scale: drives the
  robot, records data, tests policies.

> Sim makes things *happen*. Lab is where you *run the experiment*. Lab can't run without Sim under it.

---

## The robot file (USD)

- **USD** = the robot's file format — its body, joints, camera, physics, all in one.
- **Prim** = any item in that file (a part, a joint, the camera).
- **Reference / sublayer** = pulling other files in so several assets become one robot.

That's all you need: USD = the robot described in a file.

---

## How the robot is put together

- **Link** = one solid part (a forearm, the head).
- **Joint** = the connection between two parts.
  - **Revolute joint** = a hinge that rotates (the neck pan + tilt, every G1 joint).
  - **Fixed joint** = a weld that doesn't move (holds the neck onto the torso).
- **DOF** = one thing that can move = one hinge. Our robot has 55.
- **Articulation** = the whole connected robot treated as one unit. Ours is **one** articulation.

```
torso ──(fixed)── neck base ──(pan hinge)── ──(tilt hinge)── camera platform
```

---

## Making joints move — there are TWO layers

The motor settings for a joint live in two places. This trips people up, so:

```
Layer 1: USD file      → simple built-in defaults. Isaac SIM uses these.   (neck: done)
Layer 2: Isaac Lab     → the real, tuned settings. Isaac LAB uses these,
                          and overrides Layer 1 when you load the robot.    (neck: to add)
```

- The neck already moves in **Sim** because Layer 1 is set.
- For **Lab** (training), you add the neck to Layer 2 so it's tuned and consistent.

> Same idea as "the file has rough defaults; the training code sets the proper values."

---

## Articulation config vs actuator config

Both are Layer 2 (the Isaac Lab settings). One is the box, the other is a thing in the box.

- **Articulation config** = the robot's **setup sheet**. It says: which file to load, where it starts, and
  how its joints are driven.
- **Actuator config** = **one part** of that setup sheet — the part describing the **motors** (how strong,
  how springy, etc.) for groups of joints.

```
Articulation config (setup sheet)
├── which file to load
├── starting pose (joint angles at reset)
├── joint range
└── actuator config  ← the motor settings  (this is where the neck "muscle" goes)
```

---

## The "muscle" settings (actuator config knobs)

Think of a joint as a **spring + shock absorber** pulling itself to where you told it.

| Setting | Plain meaning | Analogy |
|---|---|---|
| **Stiffness** | how hard it pulls toward the target | spring strength |
| **Damping** | how much it resists moving | shock absorber / honey |
| **Effort limit** | the motor's max strength (can't exceed) | how strong the muscle is |
| **Velocity limit** | the motor's top speed | how fast it can move |
| **Armature** | the motor's built-in steadiness (anti-twitch) | the heaviness of a low bike gear |

**How they relate:** stiffness does the work; damping + armature are what *let* stiffness be high without
the joint buzzing or going crazy. You raise stiffness for crisp motion, and raise armature/damping if it
gets unstable.

---

## Who controls the joint (the chain of command)

```
Policy / you        →  "look left"          (decides WHERE to go)
   ↓
Controller (PD)     →  a torque proposal    (decides HOW HARD to push)
   ↓
Motor               →  actual torque        (does it, up to its strength limit)
   ↓
Joint moves
```

- **Policy** = the brain (the goal).
- **Controller** = the reflex (a tiny rule: push harder the farther you are from the goal).
- **Motor** = the muscle (produces the push, but has a strength limit).

The **actuator model** is the package that holds the controller + the motor's limits. So:
**the actuator model decides the torque, using the controller inside it** (controller proposes, model
finalizes by capping it to the motor's strength).

---

## How the push (torque) is decided — every instant

Hundreds of times a second, for each joint:

```
1. How far am I from the target?        (the gap)
2. Push proportional to the gap          × stiffness     (the spring)
3. Minus a brake based on my speed       × damping        (the shock absorber)
4. Don't exceed the motor's strength     clamp to effort limit
5. Apply it → joint moves a little → repeat
```

As the joint reaches the target, the gap shrinks to zero, so the push fades out on its own. Armature isn't
part of this push — it just makes the joint respond smoothly instead of twitchily.

---

## The camera

- One **camera** = the eye. RGB and depth are **two outputs of the same eye** (no separate depth camera).
- The camera (a ZED Mini) is mounted on the neck, so it moves when the neck moves.
- **Depth** is turned on later in Lab, as one extra output channel — nothing to add to the file.

```
camera  →  RGB image   (color)
        →  depth image  (distance per pixel)   ← switched on in Lab
```

---

## The whole pipeline

```
1. Isaac Lab: drive the robot, camera records  →  images + joint motions  (a dataset)
2. Convert the dataset to the training format (LeRobot)
3. Train/fine-tune the policy (GR00T) on it      ← separate GPU step, not in Lab
4. (optional) test the policy back in Lab
5. Put the policy on the real robot → it reads the real camera, moves the real joints
```

---

## Sim-to-real (why all of this matters)

The point is for a policy learned in simulation to work on the **real** robot. That only happens if sim and
real **match**:

- **Same inputs** — the sim camera image must look like the real camera image.
- **Same outputs** — the sim joints (including the neck) must match the real joints the policy controls.
- **Same feel** — the sim motors must behave like the real motors (this is what the actuator settings are
  for).

> Everything we built — the unified robot, the camera with real specs, the neck motor settings — exists to
> make the simulation close enough to reality that the trained policy transfers.

---

## One-line summary of each big word

- **Isaac Sim** — the simulator (the world).
- **Isaac Lab** — the code framework that runs experiments in that world.
- **USD** — the robot's file.
- **Articulation** — the whole robot as one connected unit.
- **Joint / DOF** — a place the robot can move.
- **Articulation config** — the robot's setup sheet in Lab.
- **Actuator config** — the motor-settings part of that sheet.
- **Controller** — the rule that decides how hard to push a joint.
- **Actuator model** — controller + motor limits, packaged; it decides the final push.
- **Stiffness / damping** — pull strength / resistance.
- **Effort / velocity limit** — the motor's max strength / speed.
- **Armature** — the motor's built-in steadiness (keeps it stable).
- **Policy (GR00T)** — the trained brain that decides what to do.
- **Sim-to-real** — making sim match reality so the trained brain works on the real robot.
