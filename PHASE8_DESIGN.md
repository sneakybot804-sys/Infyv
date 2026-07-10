# Phase 8 Design — Premium Desktop GUI

Phase 8 adds a premium PySide6 desktop application. The backend (Phases 1-7)
is **frozen**: no schema, public API, or behaviour change. The GUI is a
presentation layer over a new, permanent, Qt-free core: `gui_core`.

## Architectural contract

```
GUI  /  future AI assistant  /  future REST API  /  plugin host  /  CLI
                              |
                     ApplicationFacade      <-- the ONLY public entry point
                              |
   +----------+----------+----+-----+-----------+-----------+
   |          |          |          |           |           |
 EventBus  Registry   Pipeline  StateStore   Runner      Logs
                              |
                    (stateless Command objects)
                              |
                    frozen backend producers
```

* **`ApplicationFacade` is the only public symbol.** No front end imports an
  internal service (bus, registry, pipeline, state store, runner) or a backend
  producer directly. The facade is thin: it orchestrates and delegates, and
  contains no business logic.
* **No Qt in `gui_core`.** No `QObject`, `QWidget`, signals or slots. Qt lives
  only in the future `gui/` package (Phase 8B onward).

## Core services

### EventBus (`gui_core/events.py`)
Priority-aware (HIGH > NORMAL > LOW), deterministic publish/subscribe. Caches
the latest payload for the **persistent state** events only
(`ProjectLoaded`, `VideoSelected`, `SettingsChanged`) so a late subscriber can
`subscribe(..., replay=True)` and immediately synchronize. Volatile events
(`PhaseProgress`, `LogMessage`, ...) are never cached or replayed. The future
AI assistant subscribes to the same bus.

### Structured logging (`gui_core/logs.py`)
`LogRecord` carries typed fields: `timestamp, module, level, message, phase,
category, artifact`. Front ends filter by field (`filter_records`) and never
parse raw strings. Every record is republished as a `LogMessage` event. The
GUI never prints directly.

### Artifact contract (`gui_core/artifacts.py`)
Read-only map of the frozen producer output filenames and `output/`
discovery. Never writes or overwrites; producers remain the sole writers and
already implement never-overwrite semantics.

### Plugin registry (`gui_core/registry.py`)
Categorized (`ANALYSIS, EDITING, RENDERING, EFFECTS, AUDIO, AI, UTILITY`).
The eight built-in phases self-register via `register_builtins()` during
facade construction; external plugins call the same `register()`. The GUI
never distinguishes built-in from external. Adding a future capability
(Effects, Transitions, Music, Voice, GPU render, Color Grading, Motion
Graphics) means registering a plugin — no change to existing classes or the
GUI.

### Commands (`gui_core/commands.py`)
Stateless `Command` objects, one per phase, each wrapping exactly one existing
producer method. Everything is provided at execution time via an immutable
`CommandContext` (video path, output dir, producer factories, artifact
resolver, bus, logger, and a reserved `CancellationToken`). Commands store no
mutable state and are never singletons, which keeps future queueing, retries,
batch jobs and distributed execution simple. Backend errors are normalized
into a `PhaseResult`; producer error types never cross the facade boundary.

### Pipeline (`gui_core/pipeline.py`)
Builds the dependency graph **from the registry** (not a hardcoded table) and
computes gating: a phase is runnable when a video is selected and every
artifact produced by its dependencies exists. Gating graph:

```
Analysis    -> (video)
Highlight   -> Analysis
OCR         -> (video)
Audio       -> (video)
Fusion      -> Highlight + OCR + Audio
Decision    -> Fusion
Render      -> Decision
Subtitles   -> (video)
```

`validate_acyclic()` guards against dependency cycles.

### State (`gui_core/state.py`)
`ProjectState` is an immutable (frozen) snapshot and the single business-state
container. **Only `StateStore` creates new snapshots**; nothing mutates state
in place. Transitions publish the matching persistent-state event. Widgets
hold no business state; they render `ProjectState`.

### Runner (`gui_core/runner.py`)
Synchronous. Builds a fresh `CommandContext` per run and executes one
command. Threading is a front-end concern (the GUI will run it on a worker
thread in Phase 8D); cancellation is reserved via the context token.

## Development order

| Sub-phase | Scope |
| --- | --- |
| 8A | Qt-free `gui_core` application layer (this deliverable) |
| 8B | Theme system (centralized tokens, no hardcoded colors) |
| 8C | Reusable custom widgets (GlassCard, NeonButton, ...) |
| 8D | Main window shell + Qt worker adapters over the bus |
| 8E | Dashboard |
| 8F | Pipeline view |
| 8G | Remaining pages (Preview, Logs, Project/Output browser, Settings, Timeline) |
| 8H | Animations & polish |
| 8I | Optimization |

## Future-proof seams (not implemented now)

* **Multiple projects / workspace switching** — `StateStore` is per-project;
  the facade is the switch point.
* **Plugin marketplace** — registry is categorized and protocol-based.
* **Remote / cloud / GPU rendering** — a render plugin/command variant;
  progress already flows as priority-aware events.
* **AI agents** — subscribe to the same bus and call the same facade.
* **Collaboration** — events are plain, serializable records.

## 8A status

Implemented: `errors, events, logs, artifacts, registry, commands, pipeline,
state, runner, producers, facade` plus a Qt-free test suite (fakes only; no
PySide6/FFmpeg/Ollama/network). No dependency added to `requirements.txt`
(PySide6 is introduced only when the `gui/` layer begins, subject to explicit
approval).
