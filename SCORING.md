# Highlight Scoring (Phase 5A)

The Highlight Scoring Engine (`highlight_scorer.py`) reads a Phase 4A
`analysis.json` (schema `4a.1`) and produces a ranked `highlight.json`
(schema `5a.1`). It is **generic and game-agnostic**: it uses only signals
already available from Phase 4A and contains no kill/HUD/OCR/audio logic.

No Ollama, no FFmpeg, no video editing.

## Inputs (per scene, from Phase 4A)

- `avg_motion` (0..255) — mean frame-difference motion
- `avg_brightness` (0..255)
- `avg_static` (0..1) — stillness
- `duration` (seconds)
- overlap with `idle_sections` and `black_screens`

## Formula

Each signal is first **normalized to 0..1**, then multiplied by its weight.
Positive contributions are summed and penalties subtracted:

```
motion_n     = clamp(avg_motion      / motion_reference,     0..1)
brightness_n = clamp(avg_brightness  / brightness_reference, 0..1)
duration_n   = clamp(duration        / duration_reference,   0..1)
idle_ratio   = fraction of the scene covered by idle_sections   (0..1)
black_ratio  = fraction of the scene covered by black_screens   (0..1)
static       = avg_static                                       (0..1)

raw = motion_n     * motion_weight
    + brightness_n * brightness_weight
    + duration_n   * duration_weight
    - idle_ratio   * idle_penalty_weight
    - black_ratio  * black_penalty_weight
    - static       * static_penalty_weight

score_0_100 = clamp(raw / (motion_weight + brightness_weight + duration_weight), 0..1) * 100
```

Dividing by the sum of positive weights keeps the 0..100 scale stable no
matter how the weights are tuned — there are **no magic scaling constants**.

## Weighting (motion-dominant, by project decision)

| Priority | Factor | Default weight | Why |
| --- | --- | --- | --- |
| 1 | Motion | `motion_weight = 1.0` | Motion is the primary evidence that *something is happening* (action, fights, movement). |
| 2 | Idle penalty | `idle_penalty_weight = 0.7` | Idle overlap means the player/camera was inactive — the opposite of a highlight. |
| 3 | Black-screen penalty | `black_penalty_weight = 0.9` | Black frames (loading/transitions) are unwatchable. Strongest penalty. |
| 4 | Static penalty | `static_penalty_weight = 0.4` | High stillness correlates with low action; complements motion. |
| 5 | Duration | `duration_weight = 0.2` | Longer scenes carry slightly more content, but only up to a reference length so long idle shots aren't rewarded. |
| 6 | Brightness | `brightness_weight = 0.1` | Weak positive: very dark scenes are usually menus; lowest positive influence. |

All weights, references and thresholds live in `HighlightScoringConfig`.
Nothing is hardcoded in the logic.

### Normalization references (what “1.0” means)

| Config | Default | Meaning |
| --- | --- | --- |
| `motion_reference` | 40.0 | `avg_motion` at/above this → full motion credit. |
| `brightness_reference` | 255.0 | Linear map of brightness to 0..1. |
| `duration_reference_seconds` | 8.0 | Scene at/above this → full duration credit. |

## Thresholds & classification rules

Applied to the final 0..100 score:

| Classification | Rule (default) |
| --- | --- |
| **Excellent** | `score >= excellent_threshold` (70) |
| **Good** | `score >= good_threshold` (45) |
| **Average** | `score >= average_threshold` (20) |
| **Ignore** | below `average_threshold`, **or** `black_ratio >= force_ignore_black_ratio` (0.6) |

The black-ratio override forces `Ignore` regardless of score: a scene that is
mostly black has nothing worth keeping. Thresholds are validated to be
strictly descending on construction.

## Ranking

Scenes are sorted by `score` descending; ties break by earlier `start` for
deterministic output. Each scene gets a 1-based `rank` (rank 1 = best).

## Output

See `JSON_SCHEMA.md` (`highlight.json`, schema `5a.1`). Each scene includes
its `score`, `classification`, `rank`, and a `components` breakdown showing
how much each factor contributed — useful for tuning and for later phases.

## How Phase 5B/5C (OCR & audio) integrate without changing this architecture

The engine is intentionally structured so future signals are **additive**:

1. **New signals become new components.** Add fields to `ScoreComponents`
   (e.g. `audio_energy`, `voice_excitement`, `ocr_event`) and matching
   weights/references to `HighlightScoringConfig`. The `raw` sum simply
   gains more terms; the 0..100 rescale already divides by the sum of
   positive weights, so it adapts automatically.
2. **The scoring contract is unchanged.** Inputs are still normalized to
   0..1 and weighted; ranking and classification are untouched.
3. **Separation of concerns.** Audio analysis (5C) and OCR (5B) run in their
   **own modules** and enrich the per-scene data (or a parallel signals map)
   *before* scoring. The scorer consumes normalized signals; it never
   performs OCR or audio work itself.
4. **Schema evolution.** Bump the `highlight.json` schema version when new
   components appear; existing consumers ignore unknown fields.

This keeps Phase 5A as the stable scoring/ranking core while 5B/5C only add
inputs.
