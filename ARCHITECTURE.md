# TD4Gaia — Architecture

TouchDesigner project that turns **Gaia** — a distributed home-intelligence system (sensors, cameras, an LLM-driven "soul"/mood, a dream layer) — into real-time generative visuals, lighting (DMX) and a live device-control panel. Built and version-controlled with **Embody** (externalizes the network to git-diffable files) and **Envoy** (an MCP server that lets an AI agent inspect and edit the live TD network directly).

Gaia itself lives outside this repo: Node-RED orchestrator + `brain.json` state, a Mosquitto MQTT bus, Ollama (local LLM), Raspberry Pi / OPS / Core nodes running cameras, MediaPipe, YOLO. TD talks to it exclusively over the network (OSC + MQTT) — no shared filesystem, no direct code dependency.

## 1. System context

```mermaid
flowchart LR
    subgraph House["Gaia — the house"]
        Core["Core / miniPC\nNode-RED + brain.json\nosc_bridge.py"]
        Broker[("Mosquitto\nMQTT broker\n192.168.1.142:1883")]
        Ollama["Ollama\nlocal LLM"]
        Pi["Raspberry Pi nodes\n(ingresso, ...)"]
        OPS["OPS node\n(soggiorno)\nmocap + camera"]
        Core --- Broker
        Pi -- "gaia/device/*, gaia/mediapipe/pose" --- Broker
        OPS -- "gaia/device/*, gaia/mediapipe/pose" --- Broker
    end

    subgraph TD["This repo — TouchDesigner"]
        Bridge["Bridge COMP\nOSC + MQTT ingest/egress"]
        Visuals["Visuals COMP\ngenerative render pipeline"]
        Window["/gaia_control_window\nservice control UI"]
        Bridge --> Visuals
        Bridge --> Window
    end

    Core == "OSC :7000 raw + :7001 canvas" ==> Bridge
    Bridge == "OSC :9008 (mood nudge, lighting)" ==> Core
    OPS == "OSC :7000 mocap (direct, bypasses Core)" ==> Bridge
    Broker <-. "MQTT: gaia/device/+/status + commands" .-> Bridge
    Bridge -. "HTTP :11434" .-> Ollama
```

Three independent channels share the same OSC port (7000) but never collide — TD tells them apart purely by address prefix (`/gaia/...` vs `/gaia/mocap/...`).

| # | Channel | Direction | Transport | Purpose |
|---|---|---|---|---|
| 1 | Bridge (osc_bridge.py on Core) | Gaia → TD | OSC :7000 (raw flatten) + :7001 (curated canvas) | House state: mood, rooms, lights, people, lexicon, one-shot events |
| 1 | Bridge (osc_bridge.py on Core) | TD → Gaia | OSC :9008 → MQTT `gaia/touchdesigner/...` | Lighting control, mood nudges (deltas) |
| 2 | Mocap direct | OPS → TD | OSC :7000, `/gaia/mocap/...` namespace | High-frequency raw landmarks (pose/hands/face), bypasses Core entirely |
| 3 | Device protocol | TD ↔ Broker | MQTT `gaia/device/{id}/status`\|`command` | Service-plane only — presence, enable/disable/restart, **not** data |

**Design rule** (confirmed against Gaia's own `GAIA_TD_INTEGRATION.md`): **OSC is the data plane, MQTT is the service plane.** TD never subscribes to raw Gaia data over MQTT — everything that drives visuals arrives over OSC through the Core bridge. The one deliberate exception is channel 3, which has no OSC equivalent by design.

## 2. Channel 1 detail — OSC Bridge

```mermaid
sequenceDiagram
    participant NR as Node-RED (Core)
    participant OB as osc_bridge.py
    participant TD as TouchDesigner
    NR->>OB: WS broadcast (dashboard payload, ~10Hz decoupled)
    OB->>TD: OSC :7000 /gaia/... (raw flatten, ~1900 addresses, debug/firehose)
    NR->>OB: MQTT gaia/td/canvas (tick every 2s, Node-RED "Build TD Canvas")
    OB->>TD: OSC :7001 /gaia/canvas/... (curated: soul, rooms, lights, bricks, lexicon, dream)
    NR->>OB: one-shot events (level_up, dream_new, face_enrolled, person_recognized, plant_note)
    OB->>TD: OSC :7001 /gaia/canvas/event/... (immediate, not on the 2s tick)
    TD->>OB: OSC :9008 /gaia/td/lighting/... or /gaia/td/mood/...
    OB->>NR: MQTT gaia/touchdesigner/<path>
    Note over NR,TD: mood nudge closes the loop:<br/>TD's delta updates brain.mood,<br/>next canvas tick reflects it back as new palette colors
```

Landed in TD as `oscin1` (raw, port 7000) feeding `Visuals/data`, and a dedicated OSC In DAT (port 7001) feeding `Visuals/data_canvas` — kept separate because the curated feed mixes text (mood name, room activity, colors) with numbers, which a numeric-only OSC In CHOP can't carry. `/project1/container1/MoodNudge` sends the TD → Gaia mood deltas.

## 3. Channel 2 detail — Mocap direct

```mermaid
flowchart LR
    OPS["OPS node\nmediapipe_node.py\n(OSC_LANDMARKS=1)"] -- "OSC :7000\n/gaia/mocap/{device}/pose|hand|face/{person}\n~12Hz, bypasses Core" --> Bridge2["Visuals/mocap_bridge\n(Script CHOP, activity-based pooling)"]
    Bridge2 --> MocapGeo["mocap_geo\n(glslPOP compute → point sprite)"]
```

Person-indexed (`person_id` consistent across pose/hand/face within one frame, best-effort by lateral position — not a persistent identity). Pooled defensively per body part (pose/hands: top-N by activity; face: **fixed per-region budget**, since pooling the whole face by activity let one busy region — e.g. lips while talking — starve the rest).

## 4. Channel 3 detail — Device protocol (service plane)

```mermaid
sequenceDiagram
    participant Devices as Pi / OPS / Core agents
    participant Broker as MQTT Broker
    participant Agent as Bridge/gaia_agent<br/>(TD as a device)
    participant Control as Bridge/gaia_control<br/>(TD as controller)
    participant UI as devices_list<br/>(Play/Stop/Restart)

    Agent->>Broker: gaia/device/td-agentXX/status (retained, every 30s)
    Devices->>Broker: gaia/device/{id}/status (retained, every 30s)
    Broker->>Control: gaia/device/+/status (subscribed to all)
    Control->>Control: devices_table rebuilt (one row per device+service)
    UI->>Control: send_command(device_id, service, action) [button click]
    Control->>Broker: gaia/device/{id}/command {action, service}
    Broker->>Devices: gaia/device/{id}/command
    Broker->>Agent: gaia/device/all/command (broadcast) or gaia/device/td-agentXX/command
```

Both `gaia_agent` and `gaia_control` use raw `paho.mqtt.client` (not TD's native MQTT Client DAT). Both follow the same hard-won thread-safety pattern: **worker threads (paho's network thread, a heartbeat/staleness thread) touch only a `queue.Queue`; an Execute DAT's `onFrameStart` drains it on the main thread** — TD raises `tdError` if `run()` or any operator/parameter access happens off the main thread. `gaia_startup` (project root, outside Embody's tracked tree) fires `onStart` at real TD launch; the in-tree lifecycle DATs use `onCreate` for same-session recreation (a `.tox` "Start" toggle does not survive Embody's externalization roundtrip — a project-specific gotcha, not a TD limitation).

## 5. TouchDesigner network map

```mermaid
flowchart TB
    subgraph P["/project1/container1"]
        subgraph Bridge["Bridge"]
            mqtt_bridge["mqtt_bridge\n('#' firehose, debug/log only)"]
            web_bridge["web_bridge\n(gaia-web dashboard via Web Render TOP)"]
            ollama_bridge["ollama_bridge\n(direct /api/generate call)"]
            gaia_agent["gaia_agent\n(TD as a Gaia device)"]
            gaia_control["gaia_control\n(TD as controller + UI)"]
        end
        oscin1["oscin1 (OSC In CHOP, :7000)"]
        MoodNudge["MoodNudge (OSC Out, :9008)"]
        subgraph Visuals["Visuals"]
            data["data / data_canvas\n(OSC → CHOP channels)"]
            soul["soul_geo\n('soul' point-cloud sphere)"]
            zones["zones_geo\n(room/zone layout + DMX colors)"]
            mocap["mocap_geo + mocap_bridge\n(motion capture point cloud)"]
            dream["dream_geo/cam/light/render\n(crossfaded dream layer)"]
            sediment["sediment_* chain\n(lexicon feedback accumulation)"]
            inhabitants["inhabitants_geo\n(YOLO object seeds)"]
            moodwash["moodwash_ctrl\n(mood-color wash)"]
            dmx["dmx_ctrl / dmx_out1\n(lighting output)"]
            render1["render1 → composite_out → out_null"]
        end
        Embody["Embody\n(externalization tooling)"]
    end
    oscin1 --> data
    data --> soul & zones & moodwash & inhabitants
    soul & zones & mocap & dream & sediment & inhabitants & moodwash --> render1
    zones --> dmx
    MoodNudge -.-> Bridge
```

Six generative features, each independently controllable and DMX/composite-linked: **mood color** (`moodwash_*`), **object inhabitants** (`inhabitants_geo`, FNV-1a seeded — same word/class always draws the same way), **DMX lighting** (`dmx_*`, mirrors real house state or the on-screen zone colors), **dream sequence** (`dream_*`, crossfaded secondary render), **level-up bang** (`envelope_levelup`), **lexicon sediment** (`sediment_*`, a feedback-accumulated visual memory of Gaia's vocabulary).

## 6. Dev tooling — Embody + Envoy

- **Embody** externalizes COMPs/DATs to git-diffable files (`.tox`, `.py`, `.glsl`, `.tsv`) tracked in `externalizations.tsv`, and strips/restores the live network around `project.save()`. One hard rule learned the hard way: **never nest an independently-externalized `.tox` inside another tracked `.tox`** — it loses its contents on reload. Keep one tox level per subtree.
- **Envoy** runs an MCP server inside TD (port 9870) so an AI agent can query and mutate the live network directly — used to build and debug everything in `Bridge/`.
- Git LFS tracks `*.toe`/`*.tox` (binary); `Backup/`, `TDImportCache/`, `.tdn_backup/`, `.venv/`, `logs/` are regenerated locally and gitignored — git history replaces Embody's own local numbered-`.toe` backups.
