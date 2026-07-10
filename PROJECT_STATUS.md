# Project Status

**Project:** Local AI Gaming Video Editor (Windows 11, fully local, Ollama)
**Language:** Python

## Completion

The full local pipeline (Phases 1-7) is implemented and merged into `main`.
Phase 8 (the premium desktop GUI) has started with Phase 8A, the Qt-free
`gui_core` application layer.

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Project architecture | Done |
| 2 | FFmpeg service | Done |
| 3 | Ollama integration (streaming) | Done |
| 3.5 | Benchmark system | Done |
| 4A | Generic video analysis (`analysis.json`, 4a.1) | Done |
| 5A | Highlight scoring (`highlight.json`, 5a.1) | Done |
| 5B | OCR / HUD text (`ocr.json`, 5b.1) | Done |
| 5C | Audio analysis (`audio.json`, 5c.1) | Done |
| 5D | Signal fusion (`enriched_highlight.json`, 5d.1) | Done |
| 5E | AI decision pipeline (`edit_plan.json`, 5e.1) | Done |
| 6 | Automatic video rendering (rendered MP4) | Done |
| 7 | Subtitle engine (`subtitles.json` 7.1 + `.srt`) | Done |
| 8A | Qt-free `gui_core` application layer | Done (verified: 219 passed) |
| 8B | Theme foundation (tokens, dark theme, ThemeManager) | Done (verified) |
| 8C-1 | Widget infrastructure (base, styling, animation, effects) | Done (verified) |
| 8C-2 | Primitive widgets (GlassCard, NeonButton, IconButton, SectionHeader) | In progress |
| 8C-3..8C-6 / 8D-8I | Remaining widgets, pages, polish | Not started |

## Pipeline

```
Video
  -> Analysis (4A)
  -> Highlight (5A)
       +-- OCR (5B)
       +-- Audio (5C)
  -> Signal Fusion (5D)
  -> Decision (5E)
  -> Render (6)
  -> Subtitles (7)
```

## Test status

**173 passed, 1 skipped** on `main`. Phase 8A adds further Qt-free unit tests
for `gui_core` (fakes only; no PySide6/FFmpeg/Ollama/network). Existing tests
are unchanged.

## Architecture rules (enforced)

- Completed phases are frozen; no breaking API or schema changes.
- Dependency injection throughout; config-driven; no magic numbers.
- Every phase ships its own config module and error type, tests, and docs.
- Producers never overwrite output files.

## Phase 8 (GUI) notes

- `gui_core` is the permanent, Qt-free application layer. `ApplicationFacade`
  is its only public entry point; all front ends (GUI, future AI assistant,
  REST API, plugin host, CLI) talk only to the facade.
- No Qt symbol appears in `gui_core`; Qt begins in the future `gui/` package.
- See `PHASE8_DESIGN.md` for the full architecture and the 8A-8I plan.

## Known limitations

- **CPU-only, slow LLM.** `qwen3:8b` is functional but slow on the target CPU;
  the model is configurable in `config.py` (`OllamaConfig.model`).
- **Default subtitle backend is a placeholder** that yields no cues (no ASR
  dependency bundled); a real backend can be registered behind the existing
  Protocol without an API change.
- **No CI yet.** Tests run locally via `pytest`.
