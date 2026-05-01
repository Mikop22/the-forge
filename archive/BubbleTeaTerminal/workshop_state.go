package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	"theforge/internal/ipc"
	"theforge/internal/modsources"
)

type workshopBench struct {
	ItemID          string
	Label           string
	Manifest        map[string]interface{}
	SpritePath      string
	ProjectilePath  string
	Stats           itemStats
	ContentType     string
	SubType         string
	CraftingStation string
}

const maxPinnedNotes = 5

type workshopVariant struct {
	VariantID      string
	Label          string
	Rationale      string
	ChangeSummary  string
	Manifest       map[string]interface{}
	SpritePath     string
	ProjectilePath string
}

type workshopRuntimeBanner struct {
	BridgeAlive      bool
	WorldLoaded      bool
	LiveItemName     string
	LastInjectStatus string
	LastRuntimeNote  string
}

type workshopState struct {
	SessionID  string
	SnapshotID int
	Bench      workshopBench
	Shelf      []workshopVariant
	Runtime    workshopRuntimeBanner
}

func newWorkshopState() workshopState {
	return workshopState{
		Shelf: []workshopVariant{},
	}
}

func loadWorkshopState() workshopState {
	ws := newWorkshopState()
	ws.ApplyStatus(ipc.ReadWorkshopStatus())
	return ws
}

func workshopIDFromLabel(label string) string {
	cleaned := strings.TrimSpace(strings.ToLower(label))
	if cleaned == "" {
		return ""
	}
	var b strings.Builder
	lastDash := false
	for _, r := range cleaned {
		switch {
		case r >= 'a' && r <= 'z', r >= '0' && r <= '9':
			b.WriteRune(r)
			lastDash = false
		default:
			if !lastDash {
				b.WriteRune('-')
				lastDash = true
			}
		}
	}
	return strings.Trim(b.String(), "-")
}

func workshopBenchFromCraftedItem(item craftedItem) workshopBench {
	return workshopBench{
		ItemID:          workshopIDFromLabel(item.label),
		Label:           item.label,
		SpritePath:      item.spritePath,
		ProjectilePath:  item.projSpritePath,
		Stats:           item.stats,
		ContentType:     item.contentType,
		SubType:         item.subType,
		CraftingStation: item.craftingStation,
	}
}

func (ws *workshopState) SetBenchFromCraftedItem(item craftedItem, manifest map[string]interface{}) {
	ws.Bench = workshopBenchFromCraftedItem(item)
	ws.Bench.Manifest = manifest
	if ws.Bench.ItemID != "" {
		ws.SessionID = "bench-" + ws.Bench.ItemID
	}
}

func workshopBenchFromStatus(bench ipc.WorkshopBench) workshopBench {
	label := bench.Label
	if label == "" {
		label = bench.ItemID
	}
	result := workshopBench{
		ItemID:         bench.ItemID,
		Label:          label,
		Manifest:       bench.Manifest,
		SpritePath:     bench.SpritePath,
		ProjectilePath: bench.ProjectileSpritePath,
		Stats:          extractItemStats(bench.Manifest),
		ContentType:    manifestString(bench.Manifest, "type", "content_type"),
		SubType:        manifestString(bench.Manifest, "sub_type"),
		CraftingStation: manifestString(
			bench.Manifest,
			"crafting_station",
		),
	}
	return result
}

func workshopBenchHasRenderableContent(bench workshopBench) bool {
	if strings.TrimSpace(bench.ItemID) != "" {
		return true
	}
	if strings.TrimSpace(bench.Label) != "" {
		return true
	}
	if len(bench.Manifest) > 0 {
		return true
	}
	if strings.TrimSpace(bench.SpritePath) != "" {
		return true
	}
	if strings.TrimSpace(bench.ProjectilePath) != "" {
		return true
	}
	return false
}

func (ws *workshopState) ApplyStatus(status ipc.WorkshopStatus) {
	ws.SessionID = status.SessionID
	ws.SnapshotID = status.SnapshotID
	ws.Bench = workshopBenchFromStatus(status.Bench)
	ws.Shelf = make([]workshopVariant, 0, len(status.Shelf))
	for _, variant := range status.Shelf {
		ws.Shelf = append(ws.Shelf, workshopVariant{
			VariantID:      variant.VariantID,
			Label:          variant.Label,
			Rationale:      variant.Rationale,
			ChangeSummary:  variant.ChangeSummary,
			Manifest:       variant.Manifest,
			SpritePath:     variant.SpritePath,
			ProjectilePath: variant.ProjectileSpritePath,
		})
	}
}

func craftedItemFromWorkshopBench(bench workshopBench) craftedItem {
	return craftedItem{
		label:           bench.Label,
		contentType:     bench.ContentType,
		subType:         bench.SubType,
		craftingStation: bench.CraftingStation,
		stats:           extractItemStats(bench.Manifest),
		spritePath:      bench.SpritePath,
		projSpritePath:  bench.ProjectilePath,
	}
}

func manifestString(manifest map[string]interface{}, keys ...string) string {
	if manifest == nil {
		return ""
	}
	for _, key := range keys {
		if value, ok := manifest[key].(string); ok && value != "" {
			return value
		}
	}
	return ""
}

func loadPinnedMemoryNotes() []string {
	path := filepath.Join(modsources.Dir(), "session_shell_status.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}

	var payload struct {
		PinnedNotes []string `json:"pinned_notes"`
	}
	if err := json.Unmarshal(data, &payload); err != nil {
		return nil
	}

	return normalizePinnedNotes(payload.PinnedNotes)
}

func normalizePinnedNotes(notes []string) []string {
	cleanedNotes := make([]string, 0, len(notes))
	for _, note := range notes {
		cleaned := strings.TrimSpace(note)
		if cleaned == "" {
			continue
		}
		cleanedNotes = append(cleanedNotes, cleaned)
		if len(cleanedNotes) >= maxPinnedNotes {
			break
		}
	}
	return cleanedNotes
}
