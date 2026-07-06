# Unified G1 (neck + ZED) → `unitree_sim_isaaclab` Integration Plan

## The revelation

The data-collection pipeline **already exists**. `/home/g1/unitree_sim_isaaclab` is a complete,
working Isaac Lab → episode-recording pipeline for the Unitree G1, already built around almost
exactly our robot (G1 + Inspire hand). We do **not** need to build an environment from scratch —
we need to **integrate our unified USD** (the neck + ZED additions) into it.

Estimate: the framework is ~90% of the way there. Our job is a handful of targeted edits, not a
new system.

---

## What already exists in the repo (don't rebuild)

| Piece | Location | Notes |
|---|---|---|
| Robot configs | `robots/unitree.py`, `tasks/common_config/robot_configs.py` | `G129_CFG_WITH_INSPIRE_HAND`, preset `G1RobotPresets.g1_29dof_inspire_base_fix(...)` — same body + hands as ours, **minus the neck + ZED** |
| Tasks (gym envs) | `tasks/g1_tasks/` | e.g. `pick_place_redblock_g1_29dof_inspire`, registered as `Isaac-PickPlace-RedBlock-G129-Inspire-Joint` (a `ManagerBasedRLEnv`) |
| Observations | `tasks/common_observations/` | `camera_state.py` (`get_camera_image` → RGB to shared memory), `g1_29dof_state.py`, `inspire_state.py` (joint states). **RGB only — no depth wired in** |
| Camera configs | `tasks/common_config/camera_configs.py` | `CameraPresets` build `CameraCfg` via `PinholeCameraCfg`; `data_types=["rgb"]` by default |
| Actions | task `ActionsCfg` | `mdp.JointPositionActionCfg(asset_name="robot", joint_names=[".*"])` — regex grabs **all** joints |
| Recorder | `tools/episode_writer.py` | Writes `colors/*.jpg`, `depths/*.jpg`, `data.json`. ⚠️ depth saved as **lossy JPG** |
| Entry point | `sim_main.py` | `--task ... --action_source {dds,replay,policy} --generate_data --generate_data_dir ...` |
| Teleop | `send_commands_keyboard.py`, `action_provider/` | DDS-based (same protocol as the real robot) + keyboard |

---

## What we built standalone, validated, and ready to transplant

| Artifact | File | Status |
|---|---|---|
| Articulation config (init_state + actuators incl. **neck** group) | `articlation_cfg.py` → the `robot_cfg` | ✅ validated (neck holds at 0, turns to 1.0 rad) |
| ZED camera sensor (RGB + metric depth) | `depth_sensing.py` → the `CameraCfg` (`spawn=None`, prim `.../ZEDM/camera`) | ✅ validated (saves correct `(720,1280) float32` metric depth) |

Validated neck actuator group (the only hand-tuned part; body gains come from the shipped config):
```
neck: joint_names_expr=["neck_pan","neck_tilt"],
      stiffness=100, damping=10, effort_limit=5.0, velocity_limit=6.0, armature=0.01
```
(USD limits: pan ±2.0 rad, tilt ±1.0 rad.)

---

## Integration tasks (the actual work, once team approves)

1. **Add the unified robot config.** In `robots/unitree.py` / `robot_configs.py`, clone the inspire
   preset, swap `usd_path` → `g1_inspire_neck.usd`, and graft in our validated **neck** actuator
   group + `neck_pan`/`neck_tilt` init pose (0). Result: a `g1_29dof_inspire_neck` preset.

2. **Neck into actions — likely free.** Actions use `joint_names=[".*"]`, which auto-includes
   `neck_pan`/`neck_tilt` once they're in the USD. Just **verify** they appear and have a sane init
   pose. (If the action vector order must match the real robot, place the neck DOFs accordingly.)

3. **Add a ZED camera preset.** In `camera_configs.py`, add a preset pointing at
   `{ENV_REGEX_NS}/Robot/twist2_neck/tilt_link/ZEDM/camera` with **`spawn=None`** to keep the baked
   intrinsics (focal 3.06, clip 0.1–15) — differs from their `PinholeCameraCfg` approach.

4. **Register the camera in observations.** Add the ZED to `get_camera_image` in
   `common_observations/camera_state.py` (the "head" view).

5. **Make/adapt a task** in `tasks/g1_tasks/` that uses the new robot preset + ZED camera; register
   its gym id.

6. **Single-env smoke test** (MD Step 6): 55 DOF, neck bound, camera renders, no NaN, neck sweep
   moves the head in recorded frames. Only then scale to parallel envs.

---

## Decisions / blockers (need team input)

- **Sign-off to edit the repo** — do not modify `unitree_sim_isaaclab` until approved.
- **Replace vs. add** — does the unified robot become a new preset alongside the existing inspire
  config, or replace it?
- **Camera intrinsics** — keep our baked ZED optics (`spawn=None`) vs. their `PinholeCameraCfg`.
- **Depth path** — the recorder saves depth as **lossy JPG**. Depth is now understood to be **for
  something else later (NOT GR00T)** and is captured as a **lossless per-pixel metric matrix**
  (meters, sky→0, `float32`; see `depth_sensing.py`). So depth likely does **not** flow through
  this pipeline's JPG path as-is — confirm where depth data should land.

---

## Status of the overall goal (MD steps)

| Step | Status |
|---|---|
| 1–2 USD fix + verify | ✅ done |
| 3 Articulation config (neck actuators) | ✅ done & validated |
| 4 Camera sensor (RGB + metric depth) | ✅ proven standalone |
| 5 Wire neck→actions, camera→observations | ⏸️ = integration tasks above (team sign-off) |
| 6 Validate full env | ⏸️ follows 5 |
| 7 Collect data | 🔲 uses `sim_main.py --generate_data` |
| 8 Convert to LeRobot | 🔲 (note: repo records JSON, not LeRobot — conversion is separate) |
| 9 Fine-tune GR00T | 🔲 |

See also: project memory `articulation-config.md`, `unifiedusd-neck-camera.md`.
