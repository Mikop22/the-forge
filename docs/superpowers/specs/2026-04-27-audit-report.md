# Codebase Audit — Dead Code, Orphaned Files, Redundant Tests

**Date:** 2026-04-27
**Method:** Vulture (≥80% confidence) on production Python; `go vet` on Go; manual import-graph scan; manual review of each finding.
**Strict rule applied:** nothing was removed unless every caller and reference was identified by grep AND the function body had no observable behavior depending on the symbol.

## Summary

| Bucket | Findings | Acted on | Risk-skipped |
|---|---|---|---|
| A — Dead Python imports | 2 | 2 | 0 |
| A — Dead Python params | 2 | 0 | 2 (callers pass them) |
| A — Dead Python locals | 1 | 0 | 1 (intentional API stability) |
| A — Go dead code | 0 (`go vet` clean) | — | — |
| B — Orphaned files | 0 | — | — |
| C — Redundant tests | 0 (none confidently identified without deeper review) | — | — |

Verified pytest 387/387 + Go all green after removals.

## Findings

### Bucket A — Acted on

1. **`agents/architect/models.py:8` — `from typing import ... Union`**
   Confidence: 100%. `Union[` does not appear anywhere in the file. Removed. Tests pass.

2. **`agents/orchestrator.py:46` — `load_hidden_lab_request` import**
   Defined in `agents/core/runtime_contracts.py:85`, imported in orchestrator's `from core.runtime_contracts import (...)` block but never referenced in the orchestrator body. Other imports from the same module are used. Removed only the dead import line. Tests pass.

### Bucket A — Identified but skipped (risk > value)

3. **`agents/core/cross_consistency.py:55-56` — params `item_art_output`, `projectile_art_output`**
   Vulture flagged these as 100% confidence unused VARIABLES. They are unread inside `evaluate_cross_consistency`'s body, but they are part of the public function signature and ARE passed by callers:
   - `agents/core/test_cross_consistency.py:40,113-114` pass them as kwargs
   - `agents/core/cross_consistency.py:211` (`apply_hidden_audition_consistency_gate`) passes `item_art_output=finalist.item_sprite_path`
   Removing the params would require simultaneously updating all three call sites, and the params look like deliberate API surface for future visual-comparison tooling. **Skipped — marginal value, real refactor surface.**

4. **`agents/pixelsmith/pixelsmith.py:365` — param `base_description` of `build_img2img_prompt`**
   Same shape: vulture flagged unread-locally, but four callers (lines 604, 892, 940, 986) all pass `parsed.visuals.description` or `proj.description` for it. The function discards the value and uses LLM-extracted descriptions instead. Removing the param would touch 4 call sites and one docstring. **Skipped — same reasoning.**

5. **`agents/pixelsmith/pixelsmith.py:365` (different report) — local var `base_description`**
   Same item as above; the symbol is the param itself.

### Bucket B — Orphaned files

After excluding `.venv/`, gitignored dev tools (`agents/param_sweep.py`, `agents/probe_enrichment.py`), and intentional standalone scripts (`agents/qa/run_qa.py`, `agents/qa/quarantine_check.py`, `agents/qa/repro_status_race.py`, `agents/qa/repeat_storm_brand.py`, `agents/orchestrator_smoke.py`, `agents/pixelsmith/download_weights.py`), no file has zero importers AND zero invocation paths. All "orphaned" candidates are intentional entry-point scripts with documented use.

No backup / orig / scratch files anywhere in the repo (`*.bak`, `*_old.*`, `*.orig` all empty).

### Bucket C — Redundant tests

43 test files vs. 82 source files (≈52% test density). No confidently-identifiable redundancy. Specific concerns I considered but did not act on:

- `agents/tests/test_orchestrator_smoke.py` and `agents/orchestrator_smoke.py` — different files, different purposes (one runs in pytest, the other is a standalone script). Not redundant.
- `agents/architect/test_thesis_*` — three test files for thesis pipeline, but they cover different stages (generator, judges, weapon prompt). Not redundant.

A deeper test-redundancy pass would require running coverage to find tests that exercise identical execution paths. **Deferred** — not blocking demo, and the cost of removing a test that catches a regression outweighs the cost of keeping it.

## Apply order (record)

```
agents/architect/models.py:8 — drop unused Union import
agents/orchestrator.py:46     — drop unused load_hidden_lab_request import
```

## Verification

- `cd agents && python3 -m pytest` → 387 passed
- `cd BubbleTeaTerminal && go test ./...` → all packages pass

## Recommended follow-up (post-demo)

1. Re-run vulture every 4 weeks; remove genuinely-dead imports as they accumulate.
2. When the codex usage cap resets (Apr 29), have codex do a deeper adversarial pass — particularly on the cross_consistency / pixelsmith param questions where my judgment was "skip for safety." Codex may surface a cleaner refactor.
3. Run `coverage` against pytest to find never-exercised branches; those are the real test-redundancy candidates.
