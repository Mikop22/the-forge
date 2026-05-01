# CLAUDE.md

These notes apply when editing the **archived** Go Bubble Tea terminal UI under **`archive/BubbleTeaTerminal/`**. The primary Forge workflow today is **MCP** (`agents/mcp_server.py`) plus an IDE forge skill — see the root **README.md**.

## TUI UX Standards

### Keyboard Flow
- Every screen must have a visible exit path.
- `Ctrl+C` quits globally.
- `Esc` cancels the active mode or moves one level back.
- `Enter` confirms only when the current input or selection is valid.
- Slash commands must route through one shared handler.
- Local commands must produce visible feedback in the current screen.

### Spatial Consistency
- Render with the current terminal width from `WindowSizeMsg`.
- Do not hard-code full-width separators.
- Test narrow, normal, and wide terminal sizes.
- Horizontal panels must stack on compact terminals.
- No rendered line should exceed terminal width unless it is intentionally scrollable.

### Feedback Loops
- Async operations must show visible feedback within one render cycle.
- Polling flows need stale-state or timeout messaging.
- Success, pending, timeout, and failure states must be visually distinct.
- Quiet feed filtering must not hide user-requested command responses.

### Information Density
- The default shell should stay quiet.
- Show welcome, active operation, user-requested command output, errors, and prompt.
- Keep debug and runtime details behind explicit commands unless they affect the user.
- Staging may show richer Terraria item details, but action hints must stay visible.

### Merge Checklist For TUI Changes
- `go test ./...` passes from `archive/BubbleTeaTerminal` (after `cd archive/BubbleTeaTerminal`).
- A keyboard escape path is tested for any new screen or mode.
- Narrow terminal rendering is tested.
- Async success and failure states are tested.
- No hidden feed event is the only source of user feedback.
