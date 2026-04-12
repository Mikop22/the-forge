# Forge Design Improvements Implementation Plan

Archived summary of a Bubble Tea cleanup/polish pass.

## Main Themes

1. Functional changes such as a global animation ticker and richer crafted-item state.
2. Rendering changes such as sigils, staging metadata, and heat-bar polish.
3. General TUI cleanup such as prompt framing and title fixes.

## Durable Takeaway

The lasting value here is the split between behavior changes and rendering polish; the step-by-step execution script was much longer than the final design intent.

**Step 2: Run test to verify it fails**

```bash
go test ./... -run TestCraftedItemStoresAllFields -v
```
Expected: FAIL — `craftedItems` undefined.

**Step 3: Implement**

Add the struct definition near the top of `main.go` (after `optionItem`):

```go
type craftedItem struct {
	label       string
	tier        string
	damageClass string
	styleChoice string
	projectile  string
}
```

In the `model` struct, replace:
```go
items []string
```
with:
```go
craftedItems []craftedItem
```

Update `craftedLabel()` to return a `craftedItem`:

```go
func (m model) buildCraftedItem() craftedItem {
	name := strings.TrimSpace(m.prompt)
	if name == "" {
		name = "Unnamed Artifact"
	}
	label := name
	if m.tier != "" {
		label = fmt.Sprintf("%s (%s)", name, m.tier)
	}
	return craftedItem{
		label:       label,
		tier:        m.tier,
		damageClass: m.damageClass,
		styleChoice: m.styleChoice,
		projectile:  m.projectile,
	}
}
```

In `updateForge()`, replace:
```go
m.items = append(m.items, m.craftedLabel())
```
with:
```go
m.craftedItems = append(m.craftedItems, m.buildCraftedItem())
```

Remove the old `craftedLabel()` function.

Update `stagingView()` — replace `m.items` references:
```go
if len(m.craftedItems) == 0 {
    lines = append(lines, styles.Hint.Render("No crafted items yet."))
} else {
    for i, item := range m.craftedItems {
        lines = append(lines, styles.Inventory.Render(fmt.Sprintf("%d. %s", i+1, m.revealItem(item.label))))
    }
}
```

Update `resetForCraftAnother()` — remove `m.items = ...` if present (items persist; nothing to reset there).

**Step 4: Fix existing tests** that reference `m.items`:

In `model_test.go`, update all `m.items` → `m.craftedItems`, and `.items[0]` → `.craftedItems[0].label`:

- `TestAutoPathSkipsWizard`: `len(m.craftedItems) != 1`
- `TestManualWizardProgressionToForge`: `len(m.craftedItems) != 1` and `!strings.Contains(m.craftedItems[0].label, "(Starter)")`
- `TestCraftAnotherKeepsInventoryAndResetsFlow`: `m.craftedItems = []craftedItem{{label: "Void Blade (Hardmode)"}}` and `len(m.craftedItems) != 1`

**Step 5: Run full test suite**

```bash
go test ./...
```
Expected: all PASS

**Step 6: Commit**

```bash
git add main.go model_test.go
git commit -m "refactor: replace items []string with craftedItem struct to carry all wizard fields"
```

---

## Task 4: Staging view shows item metadata

With `craftedItem` in place, show a metadata line under each item in the staging area when class/style/projectile are available.

**Files:**
- Modify: `main.go`, `styles.go`

**Step 1: Add `Meta` style for item metadata** (distinct from the existing `Meta` used in sigil column — reuse it or add a new one):

In `styles.go`, the existing `Meta` style uses `colorGold` — that works well. No style change needed.

**Step 2: Update `stagingView()` to show metadata**

Replace the inventory rendering block in `stagingView()`:

```go
for i, item := range m.craftedItems {
    lines = append(lines, styles.Inventory.Render(fmt.Sprintf("%d. %s", i+1, m.revealItem(item.label))))
    if m.revealPhase >= 3 && (item.damageClass != "" || item.styleChoice != "" || item.projectile != "") {
        meta := buildMetaLine(item)
        lines = append(lines, styles.Meta.Render("   "+meta))
    }
}
```

Add helper function:

```go
func buildMetaLine(item craftedItem) string {
	parts := []string{}
	if item.damageClass != "" {
		parts = append(parts, item.damageClass)
	}
	if item.styleChoice != "" {
		parts = append(parts, item.styleChoice)
	}
	if item.projectile != "" && item.projectile != "None" {
		parts = append(parts, item.projectile)
	}
	if len(parts) == 0 {
		return ""
	}
	return strings.Join(parts, " · ")
}
```

**Step 3: Run full test suite**

```bash
go test ./...
```
Expected: all PASS

**Step 4: Commit**

```bash
git add main.go
git commit -m "feat: show class/style/projectile metadata in staging area"
```

---

## Task 5: Sigil column shows chosen values and fixes premature fill

Two sub-issues: (a) the Tier sigil shows filled (`◉`) on `screenMode` before anything is chosen, and (b) chosen values aren't displayed — only the slot name.

**Files:**
- Modify: `main.go`

**Step 1: Write the failing test**

```go
func TestSigilColumnShowsChosenValues(t *testing.T) {
	m := initialModel()
	m.tier = "Hardmode"
	m.damageClass = "Melee"
	col := m.sigilColumn()
	if !strings.Contains(col, "Hardmode") {
		t.Fatalf("expected sigil column to contain chosen tier value, got: %s", col)
	}
	if !strings.Contains(col, "Melee") {
		t.Fatalf("expected sigil column to contain chosen class value, got: %s", col)
	}
}

func TestSigilColumnNoPreemptiveFill(t *testing.T) {
	m := initialModel()
	m.state = screenMode
	// No values chosen yet
	col := m.sigilColumn()
	// Should not show ◉ for tier just because we're on screenMode
	lines := strings.Split(col, "\n")
	for _, line := range lines[1:] { // skip header
		if strings.Contains(line, "◉") {
			t.Fatalf("expected no filled sigil before any choice, got line: %s", line)
		}
	}
}
```

**Step 2: Run test to verify it fails**

```bash
go test ./... -run TestSigilColumn -v
```
Expected: FAIL

**Step 3: Implement**

Replace `sigilColumn()` in `main.go`:

```go
func (m model) sigilColumn() string {
	slots := []string{"Tier", "Class", "Style", "Proj"}
	values := []string{m.tier, m.damageClass, m.styleChoice, m.projectile}
	lines := []string{styles.Meta.Render("Sigils")}
	for i := range slots {
		mark := "○"
		label := slots[i]
		if values[i] != "" {
			mark = "◉"
			label = values[i]
		}
		lines = append(lines, styles.Body.Render(fmt.Sprintf("%s %s", mark, label)))
	}
	return strings.Join(lines, "\n")
}
```

**Step 4: Run tests**

```bash
go test ./... -run TestSigilColumn -v
```
Expected: PASS

**Step 5: Run full suite**

```bash
go test ./...
```

**Step 6: Commit**

```bash
git add main.go model_test.go
git commit -m "fix: sigil column shows chosen values and removes premature fill"
```

---

## Task 6: Back navigation with Escape key

Add `Escape` handling so users can go back: from `screenMode` → `screenInput`, and from `screenWizard` → previous wizard step or `screenMode` if on step 0.

**Files:**
- Modify: `main.go`, `model_test.go`

**Step 1: Write the failing tests**

```go
func TestEscapeFromModeGoesBackToInput(t *testing.T) {
	m := initialModel()
	m.state = screenMode
	m.prompt = "Void Blade"

	m, _ = updateModel(m, tea.KeyMsg{Type: tea.KeyEsc})
	if m.state != screenInput {
		t.Fatalf("expected input screen after Escape from mode, got %v", m.state)
	}
}

func TestEscapeFromWizardFirstStepGoesBackToMode(t *testing.T) {
	m := initialModel()
	m.state = screenWizard
	m.wizardIndex = 0
	m.prompt = "Void Blade"

	m, _ = updateModel(m, tea.KeyMsg{Type: tea.KeyEsc})
	if m.state != screenMode {
		t.Fatalf("expected mode screen after Escape from wizard step 0, got %v", m.state)
	}
}

func TestEscapeFromWizardMidStepGoesBackOneStep(t *testing.T) {
	m := initialModel()
	m.state = screenWizard
	m.wizardIndex = 2
	m.tier = "Hardmode"
	m.damageClass = "Melee"
	m.configureWizardStep()

	m, _ = updateModel(m, tea.KeyMsg{Type: tea.KeyEsc})
	if m.state != screenWizard {
		t.Fatalf("expected wizard screen after Escape mid-wizard, got %v", m.state)
	}
	if m.wizardIndex != 1 {
		t.Fatalf("expected wizard step 1 after Escape from step 2, got %d", m.wizardIndex)
	}
}
```

**Step 2: Run tests to verify they fail**

```bash
go test ./... -run "TestEscape" -v
```
Expected: FAIL

**Step 3: Implement**

In `updateMode()`, add escape handling before the enter check:

```go
if key, ok := msg.(tea.KeyMsg); ok {
    switch key.Type {
    case tea.KeyEsc:
        m.state = screenInput
        m.textInput.Focus()
        return m, nil
    case tea.KeyEnter:
        // existing enter logic...
    }
}
```

In `updateWizard()`, add escape handling:

```go
if key, ok := msg.(tea.KeyMsg); ok {
    switch key.Type {
    case tea.KeyEsc:
        if m.wizardIndex == 0 {
            m.state = screenMode
            return m, nil
        }
        m.wizardIndex--
        // Clear the value for the step we're going back to
        switch m.wizardIndex {
        case 0:
            m.tier = ""
        case 1:
            m.damageClass = ""
        case 2:
            m.styleChoice = ""
        case 3:
            m.projectile = ""
        }
        m.configureWizardStep()
        return m, nil
    case tea.KeyEnter:
        // existing enter logic...
    }
}
```

Note: the existing code uses `if key, ok := msg.(tea.KeyMsg); ok && key.Type == tea.KeyEnter` — refactor each into a switch on `key.Type` to accommodate both cases.

**Step 4: Run tests**

```bash
go test ./... -run "TestEscape" -v
```
Expected: PASS

**Step 5: Run full suite**

```bash
go test ./...
```

**Step 6: Commit**

```bash
git add main.go model_test.go
git commit -m "feat: add Escape key back navigation through mode and wizard screens"
```

---

## Task 7: Use wizardGlyphs in wizard view

`wizardGlyphs = []string{"⛨", "⚔", "✶", "➶"}` is defined but never used. Wire each glyph to its wizard step (Tier, Class, Style, Projectile) as a prefix in the step question display and in the hint line.

**Files:**
- Modify: `main.go`

**Step 1: Update `wizardView()` to show the glyph for the current step**

```go
func (m model) wizardView() string {
	step := fmt.Sprintf("Step %d of %d", m.wizardIndex+1, len(wizardSteps))
	glyph := wizardGlyphs[m.wizardIndex%len(wizardGlyphs)]
	lines := []string{
		styles.TitleRune.Render(glyph + "  Manual Override"),
		styles.Progress.Render(step),
	}
	lines = append(lines, "", m.wizardList.View(), styles.Hint.Render("↑/↓ navigate  •  Enter select  •  Esc back"))
	return strings.Join(lines, "\n")
}
```

This also addresses the duplicate title issue (Task 8) — the wizard list's own `.Title` (set to the step question like "Choose Tier") is shown by the list component, so the outer title just shows the glyph + "Manual Override".

**Step 2: Run full suite**

```bash
go test ./...
```
Expected: all PASS (no behavior change)

**Step 3: Commit**

```bash
git add main.go
git commit -m "feat: use wizardGlyphs in wizard view and fix duplicate title"
```

---

## Task 8: PromptInput visual framing

The `PromptInput` style is plain `colorText` foreground with no border. Add a dim border so it reads clearly as an input field.

**Files:**
- Modify: `styles.go`

**Step 1: Update `PromptInput` style**

In `newStyles()`, replace:

```go
PromptInput: lipgloss.NewStyle().
    Foreground(colorText),
```

with:

```go
PromptInput: lipgloss.NewStyle().
    Border(lipgloss.RoundedBorder()).
    BorderForeground(colorDim).
    Padding(0, 1),
```

**Step 2: Run full suite**

```bash
go test ./...
```
Expected: all PASS

**Step 3: Commit**

```bash
git add styles.go
git commit -m "feat: add visual border framing to prompt input field"
```

---

## Task 9: Set terminal window title on launch

Use `tea.SetWindowTitle` to name the terminal window "The Forge" when the program starts.

**Files:**
- Modify: `main.go`

**Step 1: Update `Init()`**

```go
func (m model) Init() tea.Cmd {
	return tea.Batch(
		textinput.Blink,
		animTickCmd(),
		tea.SetWindowTitle("The Forge"),
	)
}
```

**Step 2: Run full suite**

```bash
go test ./...
```
Expected: all PASS

**Step 3: Commit**

```bash
git add main.go
git commit -m "feat: set terminal window title to The Forge on launch"
```

---

## Task 10: Final smoke test — run the app

Visually verify all changes by running the app end-to-end.

**Step 1: Run**

```bash
go run .
```

**Step 2: Verify checklist**

- [ ] Ember strip animates on input screen (not frozen)
- [ ] Heat bar shows `████░░░░ 50%` style during forge
- [ ] Wizard shows glyph + "Manual Override" title, no duplication
- [ ] Wizard steps show the correct glyph (`⛨`, `⚔`, `✶`, `➶`) per step
- [ ] Escape on mode screen returns to input
- [ ] Escape on wizard step 0 returns to mode; mid-wizard goes back one step
- [ ] Sigil column shows chosen value (e.g. `◉ Hardmode`) instead of just `◉ Tier`
- [ ] Sigil column shows `○ Tier` (not filled) before any choice on mode screen
- [ ] After forging with Manual Override, staging shows metadata line `Melee · Swing · Beam Slash`
- [ ] Prompt input has a visible rounded border
- [ ] Terminal window title is "The Forge"

**Step 3: Commit if any final tweaks made**

```bash
git add -p
git commit -m "fix: final visual adjustments from smoke test"
```

---

## Hint: Running all tests

```bash
go test ./... -v
```
