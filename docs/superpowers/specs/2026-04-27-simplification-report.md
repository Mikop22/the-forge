# Simplification + Best-Practices Pass

**Date:** 2026-04-27
**Tools:** Ruff 0.15.12 across `agents/` (excluding `.venv`, `qa/results`).
**Constraint:** preserve all functionality. Apply only changes whose semantics are demonstrably zero-impact.

## Ruff inventory (536 warnings total)

| Code | Count | Description | Action |
|---|---|---|---|
| E501 | 348 | line-too-long | **Skipped** — pure style noise |
| UP045 | 70 | `Optional[X]` → `X \| None` | **Skipped** — codebase runs on Python 3.9; PEP 604 syntax is risky for runtime introspection (pydantic) |
| E402 | 41 | module-import-not-at-top | **Skipped** — patterns are intentional `sys.path` manipulation |
| RUF002 | 15 | ambiguous unicode in docstrings | **Skipped** — em-dashes and other unicode are user-facing, intentional |
| F401 | 14 | unused imports | **Applied (13 of 14)** |
| SIM117 | 11 | nested with-statements | **Skipped** — refactor risk |
| UP037 | 7 | quoted annotation no longer needed | **Skipped** — minimal value |
| RUF100 | 6 | unused noqa | **Skipped** — minimal value |
| Other | 19 | smaller categories | **Skipped** |

## Applied — F401 unused imports (13 files)

| File | Removed |
|---|---|
| `agents/architect/reference_finder.py` | `typing.Optional` |
| `agents/architect/reference_policy.py` | `dataclasses.field` |
| `agents/architect/test_polished_architect.py` | two unused |
| `agents/core/cross_consistency.py` | one unused |
| `agents/core/paths.py` | one unused |
| `agents/forge_master/models.py` | one unused |
| `agents/forge_master/templates/snippets.py` | `re` module |
| `agents/forge_master/test_forge_reviewer.py` | `pytest` unused |
| `agents/pixelsmith/armor_compositor.py` | `pathlib.Path` |
| `agents/pixelsmith/pixelsmith.py` | one unused |
| `agents/qa/repeat_storm_brand.py` | `traceback` (function rewritten earlier doesn't need it) |
| `agents/tests/stress/timing_test_xhigh.py` | `json` |

## Reverted — F401 false positive

`agents/architect/prompts.py` had `from architect.weapon_thesis_prompt import build_prompt as build_weapon_thesis_prompt`. Ruff flagged it as unused locally, but it is publicly exported and consumed by `agents/architect/thesis_generator.py:103` via `prompt_router.build_weapon_thesis_prompt()` (dynamic attribute access). Two tests in `architect/test_weapon_thesis_prompt.py` lock the public surface. **Reverted; the import is the public API contract.**

## Verification

- `cd agents && python3 -m pytest` → **387 passed**
- `cd BubbleTeaTerminal && go test ./...` → all packages pass

## Why I stayed conservative

1. **No codex review available** until April 29 (usage cap). Without an adversarial second opinion, I avoided changes whose safety I couldn't fully prove with grep.
2. **Python 3.9 runtime.** PEP 604 syntax (`X | None`) needs `from __future__ import annotations` to be safe at module-import time, and even then pydantic's runtime `get_type_hints()` can fail. The 70 UP045 warnings are real but each one is an audit by itself. **Defer to codex.**
3. **Style-noise rules.** 348 line-too-long warnings would mean reflowing strings and prompts that are intentionally written for readability. Not worth the diff churn pre-demo.

## Recommended follow-up (post-codex-reset on April 29)

1. Have codex propose a careful `Optional` → `X | None` migration with a strategy for the pydantic introspection sites.
2. Have codex audit the 11 SIM117 nested-with-statements — each is a small refactor that improves readability if done correctly.
3. Run `coverage` against the test suite to find dead branches; that's the highest-yield code-trim pass remaining.
