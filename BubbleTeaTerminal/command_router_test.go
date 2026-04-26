package main

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

func TestCommandRouterPlainTextWithoutActiveBenchRoutesForge(t *testing.T) {
	route := routeWorkshopCommand("make it sharper", false, nil)

	if route.Action != commandActionForge {
		t.Fatalf("action = %q, want forge", route.Action)
	}
	if route.Directive != "make it sharper" {
		t.Fatalf("directive = %q, want plain text prompt", route.Directive)
	}
}

func TestCommandRouterPlainTextWithActiveBenchRoutesVariants(t *testing.T) {
	route := routeWorkshopCommand("make it heavier", true, []workshopVariant{{VariantID: "storm-brand"}})

	if route.Action != commandActionVariants {
		t.Fatalf("action = %q, want variants", route.Action)
	}
	if route.Directive != "make it heavier" {
		t.Fatalf("directive = %q, want plain text directive", route.Directive)
	}
}

func TestWorkshopCommandForgeAlwaysForcesForgeFlow(t *testing.T) {
	route := routeWorkshopCommand("/forge keep the cast dramatic", true, []workshopVariant{{VariantID: "storm-brand"}})

	if route.Action != commandActionForge {
		t.Fatalf("action = %q, want forge", route.Action)
	}
	if route.Directive != "keep the cast dramatic" {
		t.Fatalf("directive = %q, want forge prompt", route.Directive)
	}
}

func TestWorkshopCommandEmptyForgeFailsClosedInRouter(t *testing.T) {
	route := routeWorkshopCommand("/forge", true, nil)

	if route.Action != commandActionUnsupported {
		t.Fatalf("action = %q, want unsupported", route.Action)
	}
	if route.Directive != "" {
		t.Fatalf("directive = %q, want empty", route.Directive)
	}
}

func TestWorkshopCommandEmptyForgeDirectiveShowsValidationError(t *testing.T) {
	m := initialModel()
	m.state = screenInput
	m.textInput.SetValue("/forge")

	next, _ := m.updateInput(tea.KeyMsg{Type: tea.KeyEnter})
	updated, ok := next.(model)
	if !ok {
		t.Fatalf("updateInput() returned %T, want model", next)
	}
	if updated.state == screenForge {
		t.Fatal("updateInput() entered forge for empty /forge directive")
	}
	if updated.errMsg != "Prompt cannot be empty." {
		t.Fatalf("errMsg = %q, want Prompt cannot be empty.", updated.errMsg)
	}
}

func TestWorkshopCommandEmptyVariantsShowsUsageNotice(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())

	m := initialModel()
	m.workshop.Bench = workshopBench{ItemID: "storm-brand", Label: "Storm Brand"}

	nextModel, _ := m.handleShellCommand("/variants   ")
	next := nextModel.(model)

	if next.workshopNotice != "Usage: /variants <direction>" {
		t.Fatalf("workshopNotice = %q, want variants usage", next.workshopNotice)
	}
	if next.shellError != "Usage: /variants <direction>" {
		t.Fatalf("shellError = %q, want variants usage", next.shellError)
	}
	if next.errMsg != "Usage: /variants <direction>" {
		t.Fatalf("errMsg = %q, want variants usage", next.errMsg)
	}
}

func TestWorkshopCommandRestoreLiveMapsToLastLive(t *testing.T) {
	route := routeWorkshopCommand("/restore live", true, nil)

	if route.Action != commandActionRestore {
		t.Fatalf("action = %q, want restore", route.Action)
	}
	if route.RestoreTarget != "last_live" {
		t.Fatalf("restore target = %q, want last_live", route.RestoreTarget)
	}
}

func TestWorkshopCommandRestoreBaselineWorks(t *testing.T) {
	route := routeWorkshopCommand("/restore baseline", true, nil)

	if route.Action != commandActionRestore {
		t.Fatalf("action = %q, want restore", route.Action)
	}
	if route.RestoreTarget != "baseline" {
		t.Fatalf("restore target = %q, want baseline", route.RestoreTarget)
	}
}

func TestWorkshopCommandRestoreEmptyFailsClosed(t *testing.T) {
	route := routeWorkshopCommand("/restore", true, nil)

	if route.Action != commandActionUnsupported {
		t.Fatalf("action = %q, want unsupported", route.Action)
	}
	if route.RestoreTarget != "" {
		t.Fatalf("restore target = %q, want empty", route.RestoreTarget)
	}
}

func TestWorkshopCommandRestoreTypoFailsClosed(t *testing.T) {
	route := routeWorkshopCommand("/restore typo", true, nil)

	if route.Action != commandActionUnsupported {
		t.Fatalf("action = %q, want unsupported", route.Action)
	}
	if route.RestoreTarget != "" {
		t.Fatalf("restore target = %q, want empty", route.RestoreTarget)
	}
}

func TestWorkshopCommandInvalidRestoreShowsUsageNotice(t *testing.T) {
	tests := []string{"/restore", "/restore typo"}

	for _, input := range tests {
		t.Run(input, func(t *testing.T) {
			t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())

			m := initialModel()
			m.workshop.Bench = workshopBench{ItemID: "storm-brand", Label: "Storm Brand"}

			nextModel, _ := m.handleShellCommand(input)
			next := nextModel.(model)

			if next.workshopNotice != "Usage: /restore baseline | live" {
				t.Fatalf("workshopNotice = %q, want restore usage", next.workshopNotice)
			}
			if next.shellError != "Usage: /restore baseline | live" {
				t.Fatalf("shellError = %q, want restore usage", next.shellError)
			}
			if next.errMsg != "Usage: /restore baseline | live" {
				t.Fatalf("errMsg = %q, want restore usage", next.errMsg)
			}
		})
	}
}

func TestWorkshopCommandBenchResolvesShelfIndexToVariantID(t *testing.T) {
	shelf := []workshopVariant{
		{VariantID: "storm-brand-a"},
		{VariantID: "storm-brand-b"},
	}
	route := routeWorkshopCommand("/bench 2", true, shelf)

	if route.Action != commandActionBench {
		t.Fatalf("action = %q, want bench", route.Action)
	}
	if route.VariantID != "storm-brand-b" {
		t.Fatalf("variant id = %q, want storm-brand-b", route.VariantID)
	}
}

func TestWorkshopCommandBenchNonNumericVariantIdIsAllowed(t *testing.T) {
	route := routeWorkshopCommand("/bench foo", true, []workshopVariant{{VariantID: "storm-brand"}})

	if route.Action != commandActionBench {
		t.Fatalf("action = %q, want bench", route.Action)
	}
	if route.VariantID != "foo" {
		t.Fatalf("variant id = %q, want foo", route.VariantID)
	}
}

func TestWorkshopCommandBenchMultiTokenVariantIdFailsClosed(t *testing.T) {
	route := routeWorkshopCommand("/bench foo bar", true, []workshopVariant{{VariantID: "storm-brand"}})

	if route.Action != commandActionUnsupported {
		t.Fatalf("action = %q, want unsupported", route.Action)
	}
	if route.VariantID != "" {
		t.Fatalf("variant id = %q, want empty", route.VariantID)
	}
}

func TestWorkshopCommandBenchZeroFailsClosed(t *testing.T) {
	route := routeWorkshopCommand("/bench 0", true, []workshopVariant{{VariantID: "storm-brand"}})

	if route.Action != commandActionUnsupported {
		t.Fatalf("action = %q, want unsupported", route.Action)
	}
	if route.VariantID != "" {
		t.Fatalf("variant id = %q, want empty", route.VariantID)
	}
}

func TestWorkshopCommandBenchNumericTailFailsClosed(t *testing.T) {
	route := routeWorkshopCommand("/bench 2 extra", true, []workshopVariant{{VariantID: "storm-brand-a"}, {VariantID: "storm-brand-b"}})

	if route.Action != commandActionUnsupported {
		t.Fatalf("action = %q, want unsupported", route.Action)
	}
	if route.VariantID != "" {
		t.Fatalf("variant id = %q, want empty", route.VariantID)
	}
}

func TestWorkshopCommandBenchOutOfRangeFailsClosed(t *testing.T) {
	route := routeWorkshopCommand("/bench 3", true, []workshopVariant{{VariantID: "storm-brand-a"}, {VariantID: "storm-brand-b"}})

	if route.Action != commandActionUnsupported {
		t.Fatalf("action = %q, want unsupported", route.Action)
	}
	if route.VariantID != "" {
		t.Fatalf("variant id = %q, want empty", route.VariantID)
	}
}

func TestCommandRouterUnknownSlashCommandsFailClosed(t *testing.T) {
	route := routeWorkshopCommand("/mystery do this", true, []workshopVariant{{VariantID: "storm-brand"}})

	if route.Action != commandActionUnsupported {
		t.Fatalf("action = %q, want unsupported", route.Action)
	}
	if route.Directive != "do this" {
		t.Fatalf("directive = %q, want stripped mystery payload", route.Directive)
	}
}

func TestWorkshopCommandTryBareWorks(t *testing.T) {
	route := routeWorkshopCommand("/try", true, nil)

	if route.Action != commandActionTry {
		t.Fatalf("action = %q, want try", route.Action)
	}
}

func TestWorkshopCommandTryWithTrailingArgsFailsClosed(t *testing.T) {
	route := routeWorkshopCommand("/try now", true, nil)

	if route.Action != commandActionUnsupported {
		t.Fatalf("action = %q, want unsupported", route.Action)
	}
}

func TestWorkshopInformationalCommandsRouteLocally(t *testing.T) {
	tests := []struct {
		input string
		want  commandAction
	}{
		{input: "/status", want: commandActionStatus},
		{input: "/memory", want: commandActionMemory},
		{input: "/what-changed", want: commandActionWhatChanged},
		{input: "/help", want: commandActionHelp},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			route := routeWorkshopCommand(tt.input, true, nil)
			if route.Action != tt.want {
				t.Fatalf("action = %q, want %q", route.Action, tt.want)
			}
		})
	}
}

func TestWorkshopRequestPayloadUsesRealRouterOutput(t *testing.T) {
	route := routeWorkshopCommand("/bench 2", true, []workshopVariant{
		{VariantID: "storm-brand-a"},
		{VariantID: "storm-brand-b"},
	})
	payload := buildWorkshopRequestPayloadFromRoute(route, "session-1", "storm-brand", 7)

	if got := payload["action"]; got != "bench" {
		t.Fatalf("action = %#v, want bench", got)
	}
	if got := payload["session_id"]; got != "session-1" {
		t.Fatalf("session_id = %#v, want session-1", got)
	}
	if got := payload["bench_item_id"]; got != "storm-brand" {
		t.Fatalf("bench_item_id = %#v, want storm-brand", got)
	}
	if got := payload["snapshot_id"]; got != 7 {
		t.Fatalf("snapshot_id = %#v, want 7", got)
	}
	if got := payload["variant_id"]; got != "storm-brand-b" {
		t.Fatalf("variant_id = %#v, want storm-brand-b", got)
	}
}

func TestWorkshopRequestPayloadAlwaysIncludesSnapshotID(t *testing.T) {
	route := routeWorkshopCommand("/variants make it louder", true, nil)
	payload := buildWorkshopRequestPayloadFromRoute(route, "session-1", "storm-brand", 0)

	got, ok := payload["snapshot_id"]
	if !ok {
		t.Fatal("snapshot_id missing from workshop request payload, want explicit zero when not hydrated")
	}
	if got != 0 {
		t.Fatalf("snapshot_id = %#v, want 0", got)
	}
}

func TestHistoryCommandListsCraftedItems(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()
	m.craftedItems = []craftedItem{
		{label: "Storm Brand", contentType: "Weapon", subType: "Staff"},
		{label: "Frost Blade", contentType: "Weapon", subType: "Sword"},
	}

	m2, _ := m.handleShellCommand("/history")
	next := m2.(model)

	if !strings.Contains(next.shellNotice, "Storm Brand") {
		t.Fatalf("shellNotice = %q, want 'Storm Brand' in history", next.shellNotice)
	}
	if !strings.Contains(next.shellNotice, "Frost Blade") {
		t.Fatalf("shellNotice = %q, want 'Frost Blade' in history", next.shellNotice)
	}
}

func TestHistoryCommandEmptySession(t *testing.T) {
	t.Setenv("FORGE_MOD_SOURCES_DIR", t.TempDir())
	m := initialModel()

	m2, _ := m.handleShellCommand("/history")
	next := m2.(model)

	if !strings.Contains(next.shellNotice, "No items") && !strings.Contains(next.shellNotice, "empty") {
		t.Fatalf("shellNotice = %q, want empty-session message", next.shellNotice)
	}
}
