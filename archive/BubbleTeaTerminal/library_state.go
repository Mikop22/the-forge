package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"theforge/internal/modsources"
)

const maxLibraryItems = 30

type libraryItem struct {
	Label           string                 `json:"label"`
	ItemID          string                 `json:"item_id"`
	ContentType     string                 `json:"content_type"`
	SubType         string                 `json:"sub_type"`
	CraftingStation string                 `json:"crafting_station,omitempty"`
	SpritePath      string                 `json:"sprite_path"`
	ProjectilePath  string                 `json:"projectile_path,omitempty"`
	Manifest        map[string]interface{} `json:"manifest"`
	CreatedAt       string                 `json:"created_at"`
}

func libraryPath() string {
	return filepath.Join(modsources.Dir(), "forge_library.json")
}

func loadLibraryItems() []libraryItem {
	data, err := os.ReadFile(libraryPath())
	if err != nil {
		return nil
	}
	var items []libraryItem
	if err := json.Unmarshal(data, &items); err != nil {
		return nil
	}
	return normalizeLibraryItems(items)
}

func saveLibraryItems(items []libraryItem) {
	items = normalizeLibraryItems(items)
	data, err := json.MarshalIndent(items, "", "  ")
	if err != nil {
		return
	}
	_ = os.MkdirAll(modsources.Dir(), 0o755)
	_ = os.WriteFile(libraryPath(), append(data, '\n'), 0o644)
}

func normalizeLibraryItems(items []libraryItem) []libraryItem {
	out := make([]libraryItem, 0, len(items))
	for _, item := range items {
		item.Label = strings.TrimSpace(item.Label)
		if item.Label == "" {
			continue
		}
		if item.ItemID == "" {
			item.ItemID = workshopIDFromLabel(item.Label)
		}
		out = append(out, item)
	}
	if len(out) > maxLibraryItems {
		out = out[len(out)-maxLibraryItems:]
	}
	return out
}

func libraryItemFromState(item craftedItem, manifest map[string]interface{}) libraryItem {
	label := strings.TrimSpace(item.label)
	if label == "" {
		label = manifestString(manifest, "display_name", "item_name")
	}
	return libraryItem{
		Label:           label,
		ItemID:          workshopIDFromLabel(label),
		ContentType:     item.contentType,
		SubType:         item.subType,
		CraftingStation: item.craftingStation,
		SpritePath:      item.spritePath,
		ProjectilePath:  item.projSpritePath,
		Manifest:        manifest,
		CreatedAt:       time.Now().UTC().Format(time.RFC3339),
	}
}

func libraryItemFromBench(bench workshopBench) libraryItem {
	return libraryItem{
		Label:           bench.Label,
		ItemID:          bench.ItemID,
		ContentType:     bench.ContentType,
		SubType:         bench.SubType,
		CraftingStation: bench.CraftingStation,
		SpritePath:      bench.SpritePath,
		ProjectilePath:  bench.ProjectilePath,
		Manifest:        bench.Manifest,
		CreatedAt:       time.Now().UTC().Format(time.RFC3339),
	}
}

func (m model) libraryItemsWithCurrentBench() []libraryItem {
	items := append([]libraryItem{}, m.generatedItems...)
	if workshopBenchHasRenderableContent(m.workshop.Bench) {
		items = upsertLibraryItem(items, libraryItemFromBench(m.workshop.Bench))
	}
	return items
}

func (item libraryItem) craftedItem() craftedItem {
	return craftedItem{
		label:           item.Label,
		contentType:     item.ContentType,
		subType:         item.SubType,
		craftingStation: item.CraftingStation,
		stats:           extractItemStats(item.Manifest),
		spritePath:      item.SpritePath,
		projSpritePath:  item.ProjectilePath,
	}
}

func (item libraryItem) workshopBench() workshopBench {
	crafted := item.craftedItem()
	bench := workshopBenchFromCraftedItem(crafted)
	bench.Manifest = item.Manifest
	return bench
}

func upsertLibraryItem(items []libraryItem, next libraryItem) []libraryItem {
	next.Label = strings.TrimSpace(next.Label)
	if next.Label == "" {
		return normalizeLibraryItems(items)
	}
	key := strings.ToLower(next.ItemID)
	if key == "" {
		key = strings.ToLower(workshopIDFromLabel(next.Label))
		next.ItemID = key
	}
	filtered := make([]libraryItem, 0, len(items)+1)
	for _, item := range items {
		itemKey := strings.ToLower(item.ItemID)
		if itemKey == "" {
			itemKey = strings.ToLower(workshopIDFromLabel(item.Label))
		}
		if itemKey == key {
			continue
		}
		filtered = append(filtered, item)
	}
	filtered = append(filtered, next)
	return normalizeLibraryItems(filtered)
}

func resolveLibraryItem(items []libraryItem, raw string) (libraryItem, bool) {
	query := strings.TrimSpace(raw)
	if query == "" {
		return libraryItem{}, false
	}
	if idx, err := strconv.Atoi(query); err == nil {
		zeroIdx := idx - 1
		if zeroIdx >= 0 && zeroIdx < len(items) {
			return items[zeroIdx], true
		}
		return libraryItem{}, false
	}
	normalized := strings.ToLower(workshopIDFromLabel(query))
	for _, item := range items {
		if strings.EqualFold(item.Label, query) ||
			strings.EqualFold(item.ItemID, query) ||
			strings.EqualFold(item.ItemID, normalized) {
			return item, true
		}
	}
	return libraryItem{}, false
}
