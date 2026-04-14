# Claude-Code Terminal Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan in the current session, one fresh implementer subagent per task, with spec review and code-quality review before moving on.

**Goal:** Refactor the Bubble Tea TUI into a Claude Code-style session shell with a persistent command bar, transcript-centric output, compact runtime status, and inline bench/shelf context, without regressing forge generation or live inject behavior.

**Architecture:** Keep the existing orchestrator and runtime contracts working while changing the TUI from a screen-driven renderer to a session-shell renderer. Do the redesign in layers: first define the unified shell state and command grammar, then add transcript/runtime freshness contracts, then migrate the current `screen*` flows into a single shell with legacy overlays where needed.

**Tech Stack:** Go 1.24+, Bubble Tea, Lip Gloss, Python orchestrator contracts, tModLoader `ForgeConnector`, file-backed IPC under `ModSources`.

---

## Required Execution Protocol

Every task below must follow this exact loop.

1. Dispatch a fresh implementation subagent with the full task text and relevant file context. Do not reuse an implementation subagent across tasks.
2. Have the implementation subagent write the failing test first.
3. Run the task-specific failing test command and confirm the expected failure.
4. Have the implementation subagent write the minimal code to satisfy the task.
5. Run the task-specific verification command and confirm it passes before review starts.
6. Have the implementation subagent do a brief self-review and report any cleanup performed.
7. Dispatch a fresh spec-review subagent to check only spec compliance for that task. If it finds issues, send the task back to the implementer, rerun the task verification, and re-run spec review.
8. Dispatch a fresh code-quality review subagent only after spec review is clean. If it finds issues, send the task back to the implementer, rerun the task verification, and re-run code-quality review.
9. Commit only after both reviews are clean and the task verification is green.

Do not overlap implementation tasks. This plan assumes sequential same-session execution with review gates between every task.

## Scope

### In scope for V1
- single session-shell renderer for the TUI
- persistent bottom command bar
- explicit command grammar for forge vs workshop actions
- compact top runtime/status strip
- transcript/event feed in the main panel
- inline bench and shelf modules inside the session shell
- runtime freshness semantics for the status strip
- persisted session transcript/memory contract sufficient for resume

### Out of scope for V1
- heavy new AI planning behavior
- background variant generation orchestration beyond the current director path
- major orchestrator/pipeline logic changes outside the session contract
- redesigning hidden-audition internals
- rich compare UI, timelines, or multi-item workspace management

## Non-Negotiable Constraints

1. Do not regress `enterForge()` request writing, polling, or ready-state transition.
2. Do not regress workshop actions already on `main`: `variants`, `bench`, `try`, `restore`.
3. Do not make runtime status look “live” when connector/world state is stale.
4. Do not force the user through more modes than the current app; the redesign must remove mode friction, not add to it.
5. Keep natural-language workshop input and slash commands in one consistent grammar.

## Acceptance Criteria

1. The TUI opens into a single persistent shell instead of switching between visually disconnected screens.
2. A persistent bottom command input is visible whenever the app is active.
3. The main body is a transcript/feed, not a screen-sized static form.
4. Bench and shelf are rendered as inline context modules in the shell.
5. Runtime banner shows offline/stale state correctly when the connector heartbeat is absent.
6. Plain text input is unambiguous:
   - when no active bench exists, it forges a new item
   - when an active bench exists, it defaults to workshop direction/variants
7. Existing forge and workshop regression tests still pass.

## Command Grammar

Define this before implementation and keep it stable.

- Plain text with no active bench: forge prompt
- Plain text with active bench: workshop `variants` directive
- Slash commands:
  - `/forge <prompt>`
  - `/variants <direction>`
  - `/bench <variant-id-or-number>`
  - `/try`
  - `/restore <baseline|live>`
  - `/status`
  - `/memory`
  - `/what-changed`
  - `/help`

`/restore live` must map to `last_live` in the persisted contract.

## Runtime Freshness Rules

- `forge_connector_alive.json` heartbeat is the primary truth for `Runtime Online`
- `forge_runtime_summary.json` is secondary display data only
- if heartbeat is absent, the top strip must render runtime offline even if summary says `bridge_alive=true`
- if summary is stale or missing, fall back to connector status and heartbeat only
- the UI must not display a stale `live item` as active runtime truth when the connector is offline

## Contract Changes

### TUI-side session state
Create a new unified session model instead of spreading shell state across separate screen renderers.

Expected new Go types:
- `sessionEvent`
- `sessionFeed`
- `sessionShellState`
- `shellMode` or equivalent lightweight overlay state

### Persisted workshop/session state
Current `WorkshopStatus` is not sufficient for transcript/memory.

Add a bounded persisted session payload with:
- recent session events
- pinned memory notes
- current command suggestions or context hints only if cheap

This can be added either by:
- extending `WorkshopStatus`, or
- adding a sibling persisted contract such as `workshop_session_status.json`

Recommendation: add a sibling session-status contract instead of bloating `WorkshopStatus`, so bench/shelf transport stays small and stable.

## Task Plan

### Task 1: Define target TUI state model and migration boundary

**Files:**
- Modify: `BubbleTeaTerminal/model.go`
- Modify: `BubbleTeaTerminal/main.go`
- Create: `BubbleTeaTerminal/session_shell.go`
- Create: `BubbleTeaTerminal/session_events.go`
- Test: `BubbleTeaTerminal/main_test.go`

**Step 1: Write the failing test**

Add a small focused test asserting the shell can render with:
- a top strip
- a feed container
- a persistent command bar

Prefer a renderer-level test over a full integration test.

**Step 2: Run test to verify it fails**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run TestSessionShell -v
```

Expected: fail because the session shell types/renderers do not exist.

**Step 3: Write minimal implementation**

Implement:
- `sessionEvent`
- `sessionShellState`
- a shell renderer entrypoint used by `View()`

Do not remove legacy screens yet. Just create the new shell scaffolding and wire `View()` through it.

**Step 4: Run test to verify it passes**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run TestSessionShell -v
```

**Step 5: Implementation subagent self-review**

Have the implementer subagent report:
- what changed
- which task-local tests passed
- any cleanup performed before review

**Step 6: Spec review**

Dispatch a fresh spec-review subagent against this task only.

Gate:
- do not continue until spec review is clean
- if review fails, fix, rerun `TestSessionShell`, and repeat spec review

**Step 7: Code-quality review**

Dispatch a fresh code-quality review subagent against the diff for this task only.

Gate:
- do not continue until code-quality review is clean
- if review fails, fix, rerun `TestSessionShell`, and repeat code-quality review

**Step 8: Commit**

```bash
git add BubbleTeaTerminal/model.go BubbleTeaTerminal/main.go BubbleTeaTerminal/session_shell.go BubbleTeaTerminal/session_events.go BubbleTeaTerminal/main_test.go
git commit -m "feat: add session shell scaffolding"
```

### Task 2: Define and persist transcript + memory contract

**Files:**
- Create: `agents/contracts/session_shell.py`
- Modify: `agents/contracts/workshop.py`
- Modify: `agents/core/workshop_session.py`
- Modify: `agents/orchestrator.py`
- Create: `agents/tests/test_session_shell_contract.py`
- Modify: `agents/tests/test_workshop_session.py`
- Modify: `agents/tests/test_workshop_orchestrator_transport.py`

**Step 1: Write the failing test**

Add tests asserting:
- persisted session state can round-trip recent events
- pinned memory notes survive save/load
- a workshop error preserves feed/memory state instead of wiping it

**Step 2: Run test to verify it fails**

Run:

```bash
pytest -q agents/tests/test_session_shell_contract.py agents/tests/test_workshop_session.py agents/tests/test_workshop_orchestrator_transport.py
```

Expected: fail because transcript/memory fields are not part of the persisted session contract.

**Step 3: Write minimal implementation**

Add a bounded session-shell contract with:
- recent events (small ring buffer)
- pinned memory notes

Recommendation:
- persist these in the workshop session store
- mirror only the minimal display snapshot back to the TUI

**Step 4: Run test to verify it passes**

Run:

```bash
pytest -q agents/tests/test_session_shell_contract.py agents/tests/test_workshop_session.py agents/tests/test_workshop_orchestrator_transport.py
```

**Step 5: Implementation subagent self-review**

Have the implementer subagent report:
- persisted contract changes
- which round-trip and transport tests passed
- any cleanup performed before review

**Step 6: Spec review**

Dispatch a fresh spec-review subagent against the session contract task only.

Gate:
- do not continue until spec review is clean
- if review fails, fix, rerun the task test command, and repeat spec review

**Step 7: Code-quality review**

Dispatch a fresh code-quality review subagent against the diff for this task only.

Gate:
- do not continue until code-quality review is clean
- if review fails, fix, rerun the task test command, and repeat code-quality review

**Step 8: Commit**

```bash
git add agents/contracts/session_shell.py agents/contracts/workshop.py agents/core/workshop_session.py agents/orchestrator.py agents/tests/test_session_shell_contract.py agents/tests/test_workshop_session.py agents/tests/test_workshop_orchestrator_transport.py
git commit -m "feat: persist workshop session transcript"
```

### Task 3: Lock the command grammar

**Files:**
- Modify: `BubbleTeaTerminal/command_bar.go`
- Modify: `BubbleTeaTerminal/model.go`
- Modify: `BubbleTeaTerminal/screen_input.go`
- Create: `BubbleTeaTerminal/command_router.go`
- Create: `BubbleTeaTerminal/command_router_test.go`

**Step 1: Write the failing test**

Add tests for:
- plain text with no active bench -> forge action
- plain text with active bench -> `variants`
- `/forge` always forces forge flow
- `/restore live` maps to `last_live`
- `/bench 2` resolves shelf index -> variant id

**Step 2: Run test to verify it fails**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run 'TestCommandRouter|TestWorkshopCommand' -v
```

Expected: fail because the current logic is split across `screen_input.go` and `command_bar.go`.

**Step 3: Write minimal implementation**

Create a single command routing helper that returns an explicit command/action type used by the shell.

Do not leave meaning split between different screens.

**Step 4: Run test to verify it passes**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run 'TestCommandRouter|TestWorkshopCommand' -v
```

**Step 5: Implementation subagent self-review**

Have the implementer subagent report:
- final command grammar behavior
- which router tests passed
- any cleanup performed before review

**Step 6: Spec review**

Dispatch a fresh spec-review subagent against the command grammar task only.

Gate:
- do not continue until spec review is clean
- if review fails, fix, rerun the task test command, and repeat spec review

**Step 7: Code-quality review**

Dispatch a fresh code-quality review subagent against the diff for this task only.

Gate:
- do not continue until code-quality review is clean
- if review fails, fix, rerun the task test command, and repeat code-quality review

**Step 8: Commit**

```bash
git add BubbleTeaTerminal/command_bar.go BubbleTeaTerminal/model.go BubbleTeaTerminal/screen_input.go BubbleTeaTerminal/command_router.go BubbleTeaTerminal/command_router_test.go
git commit -m "refactor: unify forge and workshop command grammar"
```

### Task 4: Add runtime freshness policy for the top strip

**Files:**
- Modify: `BubbleTeaTerminal/internal/ipc/ipc.go`
- Modify: `BubbleTeaTerminal/screen_staging.go`
- Create: `BubbleTeaTerminal/runtime_strip.go`
- Modify: `BubbleTeaTerminal/staging_runtime_test.go`
- Modify: `mod/ForgeConnector/ForgeConnectorSystem.cs`
- Modify: `agents/tests/test_workshop_runtime_summary_source_contract.py`

**Step 1: Write the failing test**

Add tests that assert:
- heartbeat absence forces `Runtime Offline`
- stale summary does not override missing heartbeat
- menu state falls back to non-live runtime note

**Step 2: Run test to verify it fails**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run TestResolveRuntimeBanner -v
cd ..
pytest -q agents/tests/test_workshop_runtime_summary_source_contract.py
```

Expected: fail if freshness/invalidation is not enforced strongly enough.

**Step 3: Write minimal implementation**

Implement:
- explicit top-strip runtime state helper
- freshness fallback rules in the TUI
- any small connector-side summary adjustment needed for clean display semantics

**Step 4: Run test to verify it passes**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run TestResolveRuntimeBanner -v
cd ..
pytest -q agents/tests/test_workshop_runtime_summary_source_contract.py
dotnet build mod/ForgeConnector/ForgeConnector.csproj -v minimal
```

**Step 5: Implementation subagent self-review**

Have the implementer subagent report:
- freshness logic added
- which Go/Python/build checks passed
- any cleanup performed before review

**Step 6: Spec review**

Dispatch a fresh spec-review subagent against the runtime freshness task only.

Gate:
- do not continue until spec review is clean
- if review fails, fix, rerun the task verification command set, and repeat spec review

**Step 7: Code-quality review**

Dispatch a fresh code-quality review subagent against the diff for this task only.

Gate:
- do not continue until code-quality review is clean
- if review fails, fix, rerun the task verification command set, and repeat code-quality review

**Step 8: Commit**

```bash
git add BubbleTeaTerminal/internal/ipc/ipc.go BubbleTeaTerminal/screen_staging.go BubbleTeaTerminal/runtime_strip.go BubbleTeaTerminal/staging_runtime_test.go mod/ForgeConnector/ForgeConnectorSystem.cs agents/tests/test_workshop_runtime_summary_source_contract.py
git commit -m "fix: add runtime freshness rules for session shell"
```

### Task 5: Build the transcript-first session renderer

**Files:**
- Modify: `BubbleTeaTerminal/main.go`
- Modify: `BubbleTeaTerminal/model.go`
- Modify: `BubbleTeaTerminal/styles.go`
- Modify: `BubbleTeaTerminal/screen_forge.go`
- Modify: `BubbleTeaTerminal/screen_staging.go`
- Create: `BubbleTeaTerminal/session_feed.go`
- Create: `BubbleTeaTerminal/session_feed_test.go`

**Step 1: Write the failing test**

Add tests asserting:
- forge progress emits/updates feed entries
- workshop actions add feed entries
- connector results add feed entries
- feed is shown in the shell view

**Step 2: Run test to verify it fails**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run TestSessionFeed -v
```

Expected: fail because no transcript model is yet wired through state updates.

**Step 3: Write minimal implementation**

Implement:
- feed append/update helpers
- compact event row rendering
- shell view using top strip + feed + bottom command bar

Keep the old screen states temporarily if needed, but route their output into the shell.

**Step 4: Run test to verify it passes**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run TestSessionFeed -v
```

**Step 5: Implementation subagent self-review**

Have the implementer subagent report:
- feed events added or updated
- which shell/feed tests passed
- any cleanup performed before review

**Step 6: Spec review**

Dispatch a fresh spec-review subagent against the transcript renderer task only.

Gate:
- do not continue until spec review is clean
- if review fails, fix, rerun `TestSessionFeed`, and repeat spec review

**Step 7: Code-quality review**

Dispatch a fresh code-quality review subagent against the diff for this task only.

Gate:
- do not continue until code-quality review is clean
- if review fails, fix, rerun `TestSessionFeed`, and repeat code-quality review

**Step 8: Commit**

```bash
git add BubbleTeaTerminal/main.go BubbleTeaTerminal/model.go BubbleTeaTerminal/styles.go BubbleTeaTerminal/screen_forge.go BubbleTeaTerminal/screen_staging.go BubbleTeaTerminal/session_feed.go BubbleTeaTerminal/session_feed_test.go
git commit -m "feat: render forge ui as a session feed"
```

### Task 6: Migrate input/mode screens into overlays or shell subviews

**Files:**
- Modify: `BubbleTeaTerminal/main.go`
- Modify: `BubbleTeaTerminal/model.go`
- Modify: `BubbleTeaTerminal/screen_input.go`
- Modify: `BubbleTeaTerminal/screen_mode.go`
- Modify: `BubbleTeaTerminal/screen_wizard.go`
- Modify: `BubbleTeaTerminal/screen_staging.go`
- Test: `BubbleTeaTerminal/main_test.go`

**Step 1: Write the failing test**

Add tests covering:
- initial shell with no bench still accepts forge prompt
- manual wizard still works
- shell remains persistent through forge -> ready -> inject

**Step 2: Run test to verify it fails**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run 'TestInputShell|TestWizardShell|TestForgeToInjectFlow' -v
```

Expected: fail because the app still swaps whole-screen renderers.

**Step 3: Write minimal implementation**

Convert the old screen concepts into:
- shell subviews
- overlays
- or input phases

The final `View()` should always render the session shell.

**Step 4: Run test to verify it passes**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run 'TestInputShell|TestWizardShell|TestForgeToInjectFlow' -v
```

**Step 5: Implementation subagent self-review**

Have the implementer subagent report:
- which legacy screen paths were collapsed
- which shell flow tests passed
- any cleanup performed before review

**Step 6: Spec review**

Dispatch a fresh spec-review subagent against the shell migration task only.

Gate:
- do not continue until spec review is clean
- if review fails, fix, rerun the task flow tests, and repeat spec review

**Step 7: Code-quality review**

Dispatch a fresh code-quality review subagent against the diff for this task only.

Gate:
- do not continue until code-quality review is clean
- if review fails, fix, rerun the task flow tests, and repeat code-quality review

**Step 8: Commit**

```bash
git add BubbleTeaTerminal/main.go BubbleTeaTerminal/model.go BubbleTeaTerminal/screen_input.go BubbleTeaTerminal/screen_mode.go BubbleTeaTerminal/screen_wizard.go BubbleTeaTerminal/screen_staging.go BubbleTeaTerminal/main_test.go
git commit -m "refactor: collapse forge ui into persistent shell"
```

### Task 7: Add contextual suggestions and lightweight pinned memory rendering

**Files:**
- Modify: `BubbleTeaTerminal/model.go`
- Modify: `BubbleTeaTerminal/session_shell.go`
- Modify: `BubbleTeaTerminal/styles.go`
- Modify: `BubbleTeaTerminal/workshop_state.go`
- Modify: `agents/orchestrator.py`
- Modify: `agents/core/workshop_session.py`
- Create: `BubbleTeaTerminal/suggestions_test.go`

**Step 1: Write the failing test**

Add tests asserting:
- empty input shows forge suggestion when no bench exists
- empty input shows `/variants` or `/bench` suggestions when appropriate
- pinned memory notes render only when present

**Step 2: Run test to verify it fails**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run TestSuggestions -v
```

Expected: fail because the shell has no suggestion/memory renderer yet.

**Step 3: Write minimal implementation**

Implement:
- lightweight suggestion resolver
- pinned memory block in shell
- persisted memory hydration from workshop session state

Keep memory small and bounded.

**Step 4: Run test to verify it passes**

Run:

```bash
cd BubbleTeaTerminal
go test ./... -run TestSuggestions -v
cd ..
pytest -q agents/tests/test_session_shell_contract.py agents/tests/test_workshop_session.py
```

**Step 5: Implementation subagent self-review**

Have the implementer subagent report:
- suggestion states covered
- memory rendering behavior
- which Go/Python tests passed
- any cleanup performed before review

**Step 6: Spec review**

Dispatch a fresh spec-review subagent against the suggestions and memory task only.

Gate:
- do not continue until spec review is clean
- if review fails, fix, rerun the task verification command set, and repeat spec review

**Step 7: Code-quality review**

Dispatch a fresh code-quality review subagent against the diff for this task only.

Gate:
- do not continue until code-quality review is clean
- if review fails, fix, rerun the task verification command set, and repeat code-quality review

**Step 8: Commit**

```bash
git add BubbleTeaTerminal/model.go BubbleTeaTerminal/session_shell.go BubbleTeaTerminal/styles.go BubbleTeaTerminal/workshop_state.go BubbleTeaTerminal/suggestions_test.go agents/orchestrator.py agents/core/workshop_session.py
git commit -m "feat: add session suggestions and pinned memory"
```

### Task 8: Full non-regression verification

**Files:**
- No new production files
- Reuse all touched tests

**Step 1: Run Go verification**

```bash
cd BubbleTeaTerminal
go test ./...
```

Expected: PASS

**Step 2: Run Python verification**

```bash
cd ..
pytest -q agents/tests/test_workshop_contracts.py \
  agents/tests/test_workshop_session.py \
  agents/tests/test_workshop_runtime_summary_source_contract.py \
  agents/tests/test_workshop_director.py \
  agents/tests/test_workshop_restore.py \
  agents/tests/test_workshop_orchestrator_transport.py
```

Expected: PASS

**Step 3: Run connector verification**

```bash
dotnet build mod/ForgeConnector/ForgeConnector.csproj -v minimal
```

Expected: build succeeds

**Step 4: Smoke-check acceptance criteria**

Manual checks:
- forge a new item from plain text
- generate variants from plain text with an active bench
- `/bench 1`
- `/try`
- `/restore baseline`
- connector offline state displays correctly

**Step 5: Final implementation self-review**

Have the implementer/controller summarize:
- which acceptance criteria were verified
- which commands were run
- any residual risks before final review

**Step 6: Final spec review**

Dispatch a fresh spec-review subagent against the whole feature.

Gate:
- do not continue until the feature-level spec review is clean
- if review fails, fix the relevant task, rerun the affected verification, and repeat spec review

**Step 7: Final code-quality review**

Dispatch a fresh code-quality review subagent against the full implementation.

Gate:
- do not continue until the feature-level code-quality review is clean
- if review fails, fix the relevant task, rerun the affected verification, and repeat code-quality review

**Step 8: Commit**

```bash
git add -A
git commit -m "test: verify claude-code shell redesign"
```

## Suggested Execution Order

1. Task 1
2. Task 3
3. Task 4
4. Task 2
5. Task 5
6. Task 6
7. Task 7
8. Task 8

This order reduces the risk of building UI on top of an ambiguous state model or stale runtime semantics.

## Notes For The Implementer

- This plan is written for same-session subagent-driven execution, not a separate executing-plans session.
- Use a fresh implementation subagent for each task and fresh reviewer subagents for each review pass.
- Do not start the next task while either the spec review or code-quality review for the current task is open.
- Prefer introducing new shell/event types over mutating every legacy field in place.
- Keep old screens alive only as temporary migration helpers; do not let them remain the final mental model.
- If transcript persistence starts to bloat `WorkshopStatus`, split it into a sibling contract instead of overloading the existing bench/shelf payload.
- If runtime freshness cannot be represented cleanly from existing files, fix the connector-side summary semantics before styling the top strip.

## Recommended Commit Series

1. `feat: add session shell scaffolding`
2. `refactor: unify forge and workshop command grammar`
3. `fix: add runtime freshness rules for session shell`
4. `feat: persist workshop session transcript`
5. `feat: render forge ui as a session feed`
6. `refactor: collapse forge ui into persistent shell`
7. `feat: add session suggestions and pinned memory`
8. `test: verify claude-code shell redesign`
