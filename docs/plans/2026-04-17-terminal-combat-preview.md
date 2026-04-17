# Terminal Combat Preview Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a pre-inject terminal combat preview that animates forged weapons and projectiles in the Bubble Tea staging screen.

**Architecture:** Keep the first version entirely in `BubbleTeaTerminal/`. Add a small RGBA canvas/compositor that can draw generated PNG sprites into a fixed-size scene, then render that scene through terminal half-block output. The staging screen chooses an animation profile from the current `craftedItem` and manifest data, advances it from the existing `animTick`, and degrades cleanly when sprites or terminal space are missing.

**Tech Stack:** Go 1.24, Bubble Tea v1.3, Lipgloss v1.1, Go `image`/`color` packages. Tests use `cd BubbleTeaTerminal && go test ./...`.

---

## File Map

| File | Change |
|---|---|
| `BubbleTeaTerminal/model.go` | Add preview fields only if needed; prefer deriving frame from existing `animTick`. |
| `BubbleTeaTerminal/main.go` | Optionally tune animation tick cadence when staging preview is visible. |
| `BubbleTeaTerminal/screen_staging.go` | Replace direct static-only preview area with animated combat preview plus existing static panels. |
| `BubbleTeaTerminal/combat_preview.go` | New preview profile selection, frame composition, and half-block rendering adapter. |
| `BubbleTeaTerminal/combat_preview_test.go` | New tests for profile selection, frame output, bounds, and missing sprites. |
| `BubbleTeaTerminal/main_test.go` | Add integration tests for staging view layout and preview presence. |

---

## Task 1: Extract Sprite Loading Into A Reusable Helper

**Files:**
- Modify: `BubbleTeaTerminal/screen_staging.go`
- Create: `BubbleTeaTerminal/combat_preview.go`
- Test: `BubbleTeaTerminal/combat_preview_test.go`

- [ ] **Step 1: Write failing tests for sprite loading**

Create `combat_preview_test.go` with tests that write a small RGBA PNG to `t.TempDir()` and assert:

```go
func TestLoadPreviewSpriteCropsTransparentBounds(t *testing.T) {
    path := writeTestSprite(t, 6, 6, func(img *image.RGBA) {
        img.Set(2, 1, color.RGBA{R: 255, A: 255})
        img.Set(3, 4, color.RGBA{G: 255, A: 255})
    })

    spr, ok := loadPreviewSprite(path)
    if !ok {
        t.Fatal("loadPreviewSprite returned ok=false")
    }
    if spr.Bounds().Dx() != 2 || spr.Bounds().Dy() != 4 {
        t.Fatalf("cropped bounds = %v, want 2x4", spr.Bounds())
    }
}

func TestLoadPreviewSpriteMissingPathReturnsFalse(t *testing.T) {
    if _, ok := loadPreviewSprite("/does/not/exist.png"); ok {
        t.Fatal("missing sprite returned ok=true")
    }
}
```

- [ ] **Step 2: Run the focused tests and confirm failure**

```bash
cd BubbleTeaTerminal && go test -run 'TestLoadPreviewSprite' -v
```

Expected: FAIL because `loadPreviewSprite` does not exist.

- [ ] **Step 3: Implement `loadPreviewSprite`**

Move the PNG open/decode and transparent bounding-box crop logic out of `renderSprite` into:

```go
func loadPreviewSprite(path string) (image.Image, bool)
```

Keep `renderSprite(path)` behavior unchanged by calling the helper and passing the result into a new internal renderer:

```go
func renderSpriteImage(img image.Image) string
```

- [ ] **Step 4: Run tests**

```bash
cd BubbleTeaTerminal && go test -run 'TestLoadPreviewSprite' -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add BubbleTeaTerminal/screen_staging.go BubbleTeaTerminal/combat_preview.go BubbleTeaTerminal/combat_preview_test.go
git commit -m "refactor: extract terminal sprite loading"
```

---

## Task 2: Add A Terminal Canvas Compositor

**Files:**
- Modify: `BubbleTeaTerminal/combat_preview.go`
- Test: `BubbleTeaTerminal/combat_preview_test.go`

- [ ] **Step 1: Write failing canvas tests**

Add tests for:

```go
func TestPreviewCanvasDrawSpriteClipsToBounds(t *testing.T)
func TestPreviewCanvasRenderHalfBlocksHasStableWidth(t *testing.T)
func TestPreviewCanvasTransparentPixelsPreserveBackground(t *testing.T)
```

The tests should create a small canvas, draw a small sprite partly outside bounds, and assert no panic, expected color placement, and line widths no wider than the requested canvas width.

- [ ] **Step 2: Run the focused tests and confirm failure**

```bash
cd BubbleTeaTerminal && go test -run 'TestPreviewCanvas' -v
```

Expected: FAIL because the canvas type does not exist.

- [ ] **Step 3: Implement the canvas**

Add:

```go
type previewCanvas struct {
    w, h int
    bg color.RGBA
    pixels []color.RGBA
}

func newPreviewCanvas(w, h int, bg color.RGBA) *previewCanvas
func (c *previewCanvas) set(x, y int, px color.Color)
func (c *previewCanvas) drawSprite(img image.Image, centerX, centerY float64, scale float64, rotationRad float64)
func (c *previewCanvas) renderHalfBlocks() string
```

Use nearest-neighbor sampling. Keep rotation simple and deterministic. Skip pixels with alpha below the existing `isTransparent` threshold.

- [ ] **Step 4: Run tests**

```bash
cd BubbleTeaTerminal && go test -run 'TestPreviewCanvas' -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add BubbleTeaTerminal/combat_preview.go BubbleTeaTerminal/combat_preview_test.go
git commit -m "feat: add terminal preview canvas"
```

---

## Task 3: Select Combat Preview Profiles

**Files:**
- Modify: `BubbleTeaTerminal/combat_preview.go`
- Test: `BubbleTeaTerminal/combat_preview_test.go`

- [ ] **Step 1: Write failing profile tests**

Add tests for:

```go
func TestCombatPreviewProfileForSwordUsesSwing(t *testing.T)
func TestCombatPreviewProfileForSpearUsesThrust(t *testing.T)
func TestCombatPreviewProfileForGunBowStaffUsesShoot(t *testing.T)
func TestCombatPreviewProfileUsesUseTimeForLoopLength(t *testing.T)
```

- [ ] **Step 2: Run the focused tests and confirm failure**

```bash
cd BubbleTeaTerminal && go test -run 'TestCombatPreviewProfile' -v
```

Expected: FAIL because profile selection does not exist.

- [ ] **Step 3: Implement profile selection**

Add:

```go
type combatPreviewKind int

const (
    combatPreviewSwing combatPreviewKind = iota
    combatPreviewThrust
    combatPreviewShoot
)

type combatPreviewProfile struct {
    kind combatPreviewKind
    loopTicks int
    projectileDelayTicks int
    projectileSpeed float64
}

func combatPreviewProfileFor(item craftedItem, manifest map[string]interface{}) combatPreviewProfile
```

Derive kind from `item.subType`, falling back to `contentType` and manifest mechanics. Use `stats.UseTime` when available; clamp loop length to a terminal-friendly range such as 8-24 TUI frames.

- [ ] **Step 4: Run tests**

```bash
cd BubbleTeaTerminal && go test -run 'TestCombatPreviewProfile' -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add BubbleTeaTerminal/combat_preview.go BubbleTeaTerminal/combat_preview_test.go
git commit -m "feat: classify combat preview profiles"
```

---

## Task 4: Render Animated Combat Frames

**Files:**
- Modify: `BubbleTeaTerminal/combat_preview.go`
- Test: `BubbleTeaTerminal/combat_preview_test.go`

- [ ] **Step 1: Write failing render tests**

Add tests for:

```go
func TestRenderCombatPreviewReturnsNonEmptyFrameWithItemSprite(t *testing.T)
func TestRenderCombatPreviewIncludesProjectileWhenAvailable(t *testing.T)
func TestRenderCombatPreviewMissingSpritesDoesNotPanic(t *testing.T)
func TestRenderCombatPreviewFrameChangesWithTick(t *testing.T)
```

- [ ] **Step 2: Run the focused tests and confirm failure**

```bash
cd BubbleTeaTerminal && go test -run 'TestRenderCombatPreview' -v
```

Expected: FAIL because `renderCombatPreview` does not exist.

- [ ] **Step 3: Implement `renderCombatPreview`**

Add:

```go
func renderCombatPreview(item craftedItem, manifest map[string]interface{}, tick int, maxWidth int) string
```

Use a fixed internal pixel canvas, for example 72x32, then render to 72 columns by 16 terminal rows before framing. Draw:

- dark arena background
- simple player/hand anchor
- item sprite transformed by the selected profile
- projectile sprite after `projectileDelayTicks`
- a minimal muzzle flash or hit spark for shoot profiles

Keep this pure and deterministic: no timers, no filesystem writes, no terminal queries.

- [ ] **Step 4: Run tests**

```bash
cd BubbleTeaTerminal && go test -run 'TestRenderCombatPreview' -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add BubbleTeaTerminal/combat_preview.go BubbleTeaTerminal/combat_preview_test.go
git commit -m "feat: render terminal combat preview frames"
```

---

## Task 5: Integrate Preview Into Staging Screen

**Files:**
- Modify: `BubbleTeaTerminal/screen_staging.go`
- Modify: `BubbleTeaTerminal/main.go` only if tick cadence needs adjustment
- Test: `BubbleTeaTerminal/main_test.go`

- [ ] **Step 1: Write failing staging integration tests**

Add tests asserting:

```go
func TestStagingViewRendersCombatPreviewForBenchItem(t *testing.T)
func TestStagingViewHidesCombatPreviewInVeryCompactTerminal(t *testing.T)
func TestStagingViewPreviewLinesDoNotExceedTerminalWidth(t *testing.T)
```

- [ ] **Step 2: Run the focused tests and confirm failure**

```bash
cd BubbleTeaTerminal && go test -run 'TestStagingView.*CombatPreview|TestStagingViewPreviewLines' -v
```

Expected: FAIL because staging does not call `renderCombatPreview`.

- [ ] **Step 3: Add preview to `stagingView`**

Inside the `m.revealPhase >= 3` block, before the static sprite panels, call:

```go
preview := renderCombatPreview(latest, m.forgeManifest, m.animTick, m.contentWidth)
```

Render it in `styles.SpriteFrame` or a dedicated preview style. For narrow terminals, omit the animated preview and keep the existing stacked static panels.

- [ ] **Step 4: Review animation tick cadence**

The current tick is 200ms. If motion feels too choppy, change `animTickCmd()` to 100ms and run the full test suite. Do not add another independent ticker unless tests show the shared tick causes problems.

- [ ] **Step 5: Run tests**

```bash
cd BubbleTeaTerminal && go test ./... -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add BubbleTeaTerminal/screen_staging.go BubbleTeaTerminal/main.go BubbleTeaTerminal/main_test.go
git commit -m "feat: show combat preview on staging bench"
```

---

## Task 6: Manual Verification

**Files:**
- Modify only if manual verification finds layout or animation defects.

- [ ] **Step 1: Run the TUI**

```bash
cd BubbleTeaTerminal && go run .
```

- [ ] **Step 2: Verify representative items**

Check at least:

- sword: compact arc, readable sprite, no layout overflow
- spear: forward thrust, returns to idle
- gun or bow: held forward, projectile appears after flash
- staff: cast/hold-forward profile, projectile visible
- missing projectile: no panic and no empty visual hole

- [ ] **Step 3: Run full tests one final time**

```bash
cd BubbleTeaTerminal && go test ./... -v
```

Expected: PASS.

- [ ] **Step 4: Commit fixes if needed**

```bash
git add BubbleTeaTerminal
git commit -m "fix: polish combat preview layout"
```
