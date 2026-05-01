package main

import (
	"testing"

	"theforge/internal/ipc"
)

func TestWorkshopStateStartsWithBenchAndEmptyShelf(t *testing.T) {
	ws := newWorkshopState()

	if ws.Bench.ItemID != "" {
		t.Fatalf("bench item = %q, want empty", ws.Bench.ItemID)
	}
	if len(ws.Shelf) != 0 {
		t.Fatalf("shelf len = %d, want 0", len(ws.Shelf))
	}
}

func TestWorkshopStateAppliesStatusSnapshot(t *testing.T) {
	ws := newWorkshopState()
	ws.ApplyStatus(ipc.WorkshopStatus{
		SessionID: "bench-storm-brand",
		Bench: ipc.WorkshopBench{
			ItemID:               "storm-brand",
			Label:                "Storm Brand",
			SpritePath:           "/tmp/item.png",
			ProjectileSpritePath: "/tmp/projectile.png",
			Manifest: map[string]interface{}{
				"type":             "Weapon",
				"sub_type":         "Staff",
				"crafting_station": "Mythril Anvil",
				"stats": map[string]interface{}{
					"damage": 24.0,
				},
			},
		},
		Shelf: []ipc.WorkshopVariant{
			{VariantID: "bench-storm-brand-v1", Label: "Heavier Shot"},
		},
	})

	if ws.SessionID != "bench-storm-brand" {
		t.Fatalf("session = %q", ws.SessionID)
	}
	if ws.Bench.ItemID != "storm-brand" {
		t.Fatalf("bench item = %q", ws.Bench.ItemID)
	}
	if len(ws.Shelf) != 1 || ws.Shelf[0].VariantID != "bench-storm-brand-v1" {
		t.Fatalf("shelf = %#v", ws.Shelf)
	}
	if ws.Bench.Stats.Damage != 24 {
		t.Fatalf("bench damage = %d", ws.Bench.Stats.Damage)
	}
	if ws.Bench.ContentType != "Weapon" || ws.Bench.SubType != "Staff" || ws.Bench.CraftingStation != "Mythril Anvil" {
		t.Fatalf("bench metadata lost: %#v", ws.Bench)
	}
}
