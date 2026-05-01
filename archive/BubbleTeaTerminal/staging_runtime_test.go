package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"theforge/internal/ipc"
)

func TestStagingViewShowsRuntimeBannerFields(t *testing.T) {
	m := initialModel()
	item := craftedItem{
		label:          "Storm Brand",
		contentType:    "Weapon",
		subType:        "Staff",
		spritePath:     "",
		projSpritePath: "",
	}
	m.previewItem = &item
	m.workshop.SetBenchFromCraftedItem(item, map[string]interface{}{})
	m.revealPhase = 3
	m.workshop.Runtime = workshopRuntimeBanner{
		BridgeAlive:      true,
		WorldLoaded:      true,
		LiveItemName:     "Storm Brand",
		LastInjectStatus: "item_injected",
		LastRuntimeNote:  "Ready on bench",
	}

	view := m.stagingView()
	for _, want := range []string{
		"Runtime Online",
		"World Loaded",
		"Live item: Storm Brand",
		"Inject status: item_injected",
		"Ready on bench",
	} {
		if !strings.Contains(view, want) {
			t.Fatalf("stagingView() missing %q\n%s", want, view)
		}
	}
}

func TestStagingViewHidesHealthyIdleRuntimeDetails(t *testing.T) {
	m := initialModel()
	item := craftedItem{
		label:       "Storm Brand",
		contentType: "Weapon",
		subType:     "Staff",
	}
	m.previewItem = &item
	m.workshop.SetBenchFromCraftedItem(item, map[string]interface{}{})
	m.revealPhase = 3
	m.workshop.Runtime = workshopRuntimeBanner{
		BridgeAlive: true,
		WorldLoaded: true,
	}

	view := m.stagingView()
	if strings.Contains(view, "Runtime Online") || strings.Contains(view, "World Loaded") {
		t.Fatalf("stagingView() = %q, want healthy idle runtime details hidden", view)
	}
	if strings.Contains(view, "[R] Reprompt sprite") {
		t.Fatalf("stagingView() = %q, want legacy action hints removed", view)
	}
	if strings.Contains(view, "Type / in the command bar") {
		t.Fatalf("stagingView() = %q, want duplicate command hint removed", view)
	}
	if strings.Contains(view, "variants") {
		t.Fatalf("stagingView() = %q, want variants hidden until variants UX is ready", view)
	}
}

func TestStagingViewDoesNotDuplicateOfflineRuntimeNote(t *testing.T) {
	m := initialModel()
	item := craftedItem{label: "Storm Brand", contentType: "Weapon", subType: "Staff"}
	m.previewItem = &item
	m.workshop.SetBenchFromCraftedItem(item, map[string]interface{}{})
	m.revealPhase = 3
	m.workshop.Runtime = workshopRuntimeBanner{
		BridgeAlive:     false,
		LastRuntimeNote: "Runtime Offline",
	}

	view := m.stagingView()
	if strings.Count(view, "Runtime Offline") > 1 {
		t.Fatalf("stagingView() = %q, want Runtime Offline rendered once", view)
	}
}

func TestApplyWorkshopStatusRefreshesForgeItemName(t *testing.T) {
	m := initialModel()
	m.forgeItemName = "Old Name"
	m.applyWorkshopStatus(ipc.WorkshopStatus{
		SessionID: "bench-storm-brand",
		Bench: ipc.WorkshopBench{
			ItemID: "storm-brand",
			Label:  "Storm Brand",
			Manifest: map[string]interface{}{
				"type":     "Weapon",
				"sub_type": "Staff",
				"stats": map[string]interface{}{
					"damage": 24.0,
				},
			},
		},
	})

	if m.forgeItemName != "Storm Brand" {
		t.Fatalf("forgeItemName = %q, want bench label", m.forgeItemName)
	}
}

func TestAcceptInjectUsesBenchLabelAfterWorkshopStatus(t *testing.T) {
	home := t.TempDir()
	ms := filepath.Join(home, "ModSources")
	t.Setenv("HOME", home)
	t.Setenv("FORGE_MOD_SOURCES_DIR", ms)

	m := initialModel()
	m.previewMode = previewModeActions
	m.applyWorkshopStatus(ipc.WorkshopStatus{
		SessionID: "bench-storm-brand",
		Bench: ipc.WorkshopBench{
			ItemID: "storm-brand",
			Label:  "Storm Brand",
			Manifest: map[string]interface{}{
				"type":     "Weapon",
				"sub_type": "Staff",
				"stats": map[string]interface{}{
					"damage": 24.0,
				},
			},
		},
	})
	m.forgeItemName = "Old Name"

	_, _ = m.updateStaging(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'a'}})

	data, err := os.ReadFile(filepath.Join(ms, "forge_inject.json"))
	if err != nil {
		t.Fatalf("read forge_inject.json: %v", err)
	}
	var payload map[string]interface{}
	if err := json.Unmarshal(data, &payload); err != nil {
		t.Fatalf("unmarshal forge_inject.json: %v", err)
	}
	if got := payload["item_name"]; got != "Storm Brand" {
		t.Fatalf("item_name = %#v, want Storm Brand", got)
	}
}

func TestResolveRuntimeBannerPrefersFreshSummaryWhenHeartbeatAlive(t *testing.T) {
	now := time.Date(2026, time.April, 12, 12, 0, 0, 0, time.UTC)
	banner := resolveRuntimeBanner(
		ipc.RuntimeSummary{
			BridgeAlive:      true,
			WorldLoaded:      true,
			LiveItemName:     "Storm Brand",
			LastInjectStatus: "item_injected",
			LastRuntimeNote:  "Ready on bench",
			UpdatedAt:        now.Add(-2 * time.Second).Format(time.RFC3339),
		},
		true,
		"item_injected",
		"Ready on bench",
		now,
	)

	if !banner.BridgeAlive {
		t.Fatal("BridgeAlive = false, want true when heartbeat is present")
	}
	if !banner.WorldLoaded {
		t.Fatal("WorldLoaded = false, want true for a fresh summary")
	}
	if banner.LiveItemName != "Storm Brand" {
		t.Fatalf("LiveItemName = %q, want Storm Brand", banner.LiveItemName)
	}
}

func TestResolveRuntimeBannerHeartbeatMissingForcesOffline(t *testing.T) {
	now := time.Date(2026, time.April, 12, 12, 0, 0, 0, time.UTC)
	banner := resolveRuntimeBanner(
		ipc.RuntimeSummary{
			BridgeAlive:      true,
			WorldLoaded:      true,
			LiveItemName:     "Storm Brand",
			LastInjectStatus: "item_injected",
			LastRuntimeNote:  "Ready on bench",
			UpdatedAt:        now.Add(-45 * time.Second).Format(time.RFC3339),
		},
		false,
		"item_injected",
		"Ready on bench",
		now,
	)

	if banner.BridgeAlive {
		t.Fatal("BridgeAlive = true, want false when heartbeat is absent")
	}
	if banner.WorldLoaded {
		t.Fatal("WorldLoaded = true, want false when heartbeat is absent")
	}
	if banner.LiveItemName != "" {
		t.Fatalf("LiveItemName = %q, want empty when heartbeat is absent", banner.LiveItemName)
	}
	if banner.LastInjectStatus != "" {
		t.Fatalf("LastInjectStatus = %q, want empty when heartbeat is absent", banner.LastInjectStatus)
	}
	if banner.LastRuntimeNote != "Runtime Offline" {
		t.Fatalf("LastRuntimeNote = %q, want Runtime Offline", banner.LastRuntimeNote)
	}
}

func TestResolveRuntimeBannerStaleSummaryFallsBackToMenuNote(t *testing.T) {
	now := time.Date(2026, time.April, 12, 12, 0, 0, 0, time.UTC)
	banner := resolveRuntimeBanner(
		ipc.RuntimeSummary{
			BridgeAlive:      true,
			WorldLoaded:      false,
			LiveItemName:     "Storm Brand",
			LastInjectStatus: "item_injected",
			LastRuntimeNote:  "Stale live runtime note",
			UpdatedAt:        now.Add(-2 * time.Minute).Format(time.RFC3339),
		},
		true,
		"item_injected",
		"At main menu.",
		now,
	)

	if !banner.BridgeAlive {
		t.Fatal("BridgeAlive = false, want true when heartbeat is present")
	}
	if banner.WorldLoaded {
		t.Fatal("WorldLoaded = true, want false for stale menu summary")
	}
	if banner.LiveItemName != "" {
		t.Fatalf("LiveItemName = %q, want empty for stale menu summary", banner.LiveItemName)
	}
	if banner.LastInjectStatus != "" {
		t.Fatalf("LastInjectStatus = %q, want empty for stale menu summary", banner.LastInjectStatus)
	}
	if banner.LastRuntimeNote != "At main menu." {
		t.Fatalf("LastRuntimeNote = %q, want At main menu.", banner.LastRuntimeNote)
	}
}

func TestResolveRuntimeBannerStaleSummaryIgnoresConnectorDetail(t *testing.T) {
	now := time.Date(2026, time.April, 12, 12, 0, 0, 0, time.UTC)
	banner := resolveRuntimeBanner(
		ipc.RuntimeSummary{
			BridgeAlive:      true,
			WorldLoaded:      true,
			LiveItemName:     "Storm Brand",
			LastInjectStatus: "item_injected",
			LastRuntimeNote:  "Item delivered to inventory.",
			UpdatedAt:        now.Add(-2 * time.Minute).Format(time.RFC3339),
		},
		true,
		"item_injected",
		"Item delivered to inventory.",
		now,
	)

	if banner.LastRuntimeNote != "Runtime status stale." {
		t.Fatalf("LastRuntimeNote = %q, want Runtime status stale.", banner.LastRuntimeNote)
	}
}

func TestUpdateStagingClearsEmptyRuntimeBannerFields(t *testing.T) {
	m := initialModel()
	m.injectStatus = "item_injected"
	m.injectDetail = "Item delivered to inventory."
	m.workshop.Runtime = workshopRuntimeBanner{
		BridgeAlive:      true,
		WorldLoaded:      false,
		LastInjectStatus: "item_injected",
		LastRuntimeNote:  "Item delivered to inventory.",
	}

	updated, _ := m.updateStaging(runtimeSummaryMsg{
		banner: workshopRuntimeBanner{
			BridgeAlive:     true,
			WorldLoaded:     false,
			LastRuntimeNote: "At main menu.",
		},
	})
	m = updated.(model)

	if m.injectStatus != "" {
		t.Fatalf("injectStatus = %q, want empty when banner clears it", m.injectStatus)
	}
	if m.injectDetail != "" {
		t.Fatalf("injectDetail = %q, want empty when banner clears it", m.injectDetail)
	}
}

func TestApplyWorkshopStatusRefreshesPreviewFromPartialBenchData(t *testing.T) {
	m := initialModel()
	m.forgeItemName = "Old Name"

	m.applyWorkshopStatus(ipc.WorkshopStatus{
		SessionID: "bench-storm-brand",
		Bench: ipc.WorkshopBench{
			ItemID: "storm-brand",
			Manifest: map[string]interface{}{
				"type":     "Weapon",
				"sub_type": "Staff",
				"stats": map[string]interface{}{
					"damage": 24.0,
				},
			},
			SpritePath: "/tmp/storm-brand.png",
		},
	})

	if m.previewItem == nil {
		t.Fatal("previewItem = nil, want bench preview from partial bench data")
	}
	if m.previewItem.label != "storm-brand" {
		t.Fatalf("previewItem.label = %q, want fallback to item id", m.previewItem.label)
	}
	if m.forgeItemName != "storm-brand" {
		t.Fatalf("forgeItemName = %q, want fallback to item id", m.forgeItemName)
	}
}

func TestStagingViewInjectionShowsElapsedTime(t *testing.T) {
	m := initialModel()
	item := craftedItem{label: "Storm Brand", contentType: "Weapon", subType: "Staff"}
	m.previewItem = &item
	m.workshop.SetBenchFromCraftedItem(item, map[string]interface{}{})
	m.revealPhase = 3
	m.injecting = true
	m.operationKind = operationInjecting
	m.operationLabel = "Storm Brand"
	m.operationStartedAt = time.Now().UTC().Add(-8 * time.Second)

	view := m.stagingView()
	if strings.Contains(view, "⟳ Injecting into Terraria...") {
		t.Fatalf("stagingView() contains duplicate static injecting line; should be removed")
	}
}

func TestStagingViewItemPendingUsesDistinctMarker(t *testing.T) {
	m := initialModel()
	item := craftedItem{label: "Storm Brand", contentType: "Weapon", subType: "Staff"}
	m.previewItem = &item
	m.workshop.SetBenchFromCraftedItem(item, map[string]interface{}{})
	m.revealPhase = 3
	m.injectStatus = "item_pending"

	view := m.stagingView()
	if strings.Contains(view, "appeared in your inventory") {
		t.Fatalf("stagingView() item_pending = %q, want 'appeared in your inventory' absent", view)
	}
	if !strings.Contains(view, "enter a world") {
		t.Fatalf("stagingView() item_pending = %q, want 'enter a world' text", view)
	}
	if strings.Contains(view, "✔ Item appeared") {
		t.Fatalf("stagingView() item_pending uses success marker, want pending marker")
	}
}

func TestStagingCommandModeEntryClearsWorkshopNotice(t *testing.T) {
	m := initialModel()
	item := craftedItem{label: "Storm Brand", contentType: "Weapon", subType: "Staff"}
	m.previewItem = &item
	m.workshop.SetBenchFromCraftedItem(item, map[string]interface{}{})
	m.revealPhase = 3
	m.workshopNotice = "Director request sent."
	m.state = screenStaging

	updated, _ := m.updateStaging(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'/'}})
	next := updated.(model)

	if next.workshopNotice != "" {
		t.Fatalf("workshopNotice = %q, want empty after entering command mode", next.workshopNotice)
	}
}

func TestStagingTabEntryClearsWorkshopNotice(t *testing.T) {
	m := initialModel()
	item := craftedItem{label: "Storm Brand", contentType: "Weapon", subType: "Staff"}
	m.previewItem = &item
	m.workshop.SetBenchFromCraftedItem(item, map[string]interface{}{})
	m.revealPhase = 3
	m.workshopNotice = "Director request sent."
	m.state = screenStaging

	updated, _ := m.updateStaging(tea.KeyMsg{Type: tea.KeyTab})
	next := updated.(model)

	if next.workshopNotice != "" {
		t.Fatalf("workshopNotice = %q after Tab, want empty", next.workshopNotice)
	}
}
