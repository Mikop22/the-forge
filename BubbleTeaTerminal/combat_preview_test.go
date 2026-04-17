package main

import (
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func writeTestSprite(t *testing.T, width, height int, paint func(*image.RGBA)) string {
	t.Helper()

	img := image.NewRGBA(image.Rect(0, 0, width, height))
	paint(img)

	path := filepath.Join(t.TempDir(), "sprite.png")
	f, err := os.Create(path)
	if err != nil {
		t.Fatalf("create test sprite: %v", err)
	}
	defer f.Close()

	if err := png.Encode(f, img); err != nil {
		t.Fatalf("encode test sprite: %v", err)
	}

	return path
}

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

func TestPreviewCanvasDrawSpriteClipsToBounds(t *testing.T) {
	canvas := newPreviewCanvas(3, 3, color.RGBA{A: 255})
	sprite := image.NewRGBA(image.Rect(0, 0, 2, 2))
	sprite.Set(0, 0, color.RGBA{R: 255, A: 255})
	sprite.Set(1, 0, color.RGBA{G: 255, A: 255})
	sprite.Set(0, 1, color.RGBA{B: 255, A: 255})
	sprite.Set(1, 1, color.RGBA{R: 255, G: 255, A: 255})

	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("drawSprite panicked: %v", r)
		}
	}()

	canvas.drawSprite(sprite, -0.5, -0.5, 1, 0)

	if got := canvas.pixels[0]; got != (color.RGBA{R: 255, G: 255, A: 255}) {
		t.Fatalf("pixel[0] = %#v, want bottom-right sprite color", got)
	}
	if got := canvas.pixels[1]; got != (color.RGBA{A: 255}) {
		t.Fatalf("pixel[1] = %#v, want background", got)
	}
	if got := canvas.pixels[3]; got != (color.RGBA{A: 255}) {
		t.Fatalf("pixel[3] = %#v, want background", got)
	}
}

func TestPreviewCanvasRenderHalfBlocksHasStableWidth(t *testing.T) {
	canvas := newPreviewCanvas(5, 4, color.RGBA{A: 255})
	canvas.set(0, 0, color.RGBA{R: 255, A: 255})
	canvas.set(1, 0, color.RGBA{G: 255, A: 255})
	canvas.set(2, 1, color.RGBA{B: 255, A: 255})
	canvas.set(4, 3, color.RGBA{R: 255, B: 255, A: 255})

	rendered := canvas.renderHalfBlocks()
	lines := strings.Split(rendered, "\n")
	if len(lines) != 2 {
		t.Fatalf("rendered line count = %d, want 2", len(lines))
	}
	for i, line := range lines {
		if got := lipgloss.Width(line); got > 5 {
			t.Fatalf("line %d width = %d, want <= 5", i, got)
		}
	}
}

func TestPreviewCanvasTransparentPixelsPreserveBackground(t *testing.T) {
	bg := color.RGBA{R: 12, G: 34, B: 56, A: 255}
	canvas := newPreviewCanvas(2, 2, bg)
	sprite := image.NewRGBA(image.Rect(0, 0, 1, 1))
	sprite.Set(0, 0, color.RGBA{R: 255, A: 0x7f})

	canvas.drawSprite(sprite, 0, 0, 1, 0)

	for i, got := range canvas.pixels {
		if got != bg {
			t.Fatalf("pixel[%d] = %#v, want background %#v", i, got, bg)
		}
	}
}

func TestCombatPreviewProfileForSwordUsesSwing(t *testing.T) {
	profile := combatPreviewProfileFor(craftedItem{subType: "Sword"}, nil)
	if profile.kind != combatPreviewSwing {
		t.Fatalf("profile.kind = %v, want swing", profile.kind)
	}
}

func TestCombatPreviewProfileForSpearUsesThrust(t *testing.T) {
	profile := combatPreviewProfileFor(craftedItem{subType: "Spear"}, nil)
	if profile.kind != combatPreviewThrust {
		t.Fatalf("profile.kind = %v, want thrust", profile.kind)
	}
}

func TestCombatPreviewProfileForGunBowStaffUsesShoot(t *testing.T) {
	for _, subType := range []string{"Gun", "Bow", "Staff", "Cannon"} {
		t.Run(subType, func(t *testing.T) {
			profile := combatPreviewProfileFor(craftedItem{contentType: "Weapon", subType: subType}, nil)
			if profile.kind != combatPreviewShoot {
				t.Fatalf("profile.kind = %v, want shoot", profile.kind)
			}
		})
	}
}

func TestCombatPreviewProfileUsesUseTimeForLoopLength(t *testing.T) {
	fast := combatPreviewProfileFor(craftedItem{stats: itemStats{UseTime: 8}}, nil)
	slow := combatPreviewProfileFor(craftedItem{stats: itemStats{UseTime: 40}}, nil)

	if fast.loopTicks != 8 {
		t.Fatalf("fast.loopTicks = %d, want 8", fast.loopTicks)
	}
	if slow.loopTicks != 24 {
		t.Fatalf("slow.loopTicks = %d, want 24", slow.loopTicks)
	}
	if fast.loopTicks >= slow.loopTicks {
		t.Fatalf("loopTicks did not increase with use time: fast=%d slow=%d", fast.loopTicks, slow.loopTicks)
	}
}

func TestRenderCombatPreviewReturnsNonEmptyFrameWithItemSprite(t *testing.T) {
	itemPath := writeTestSprite(t, 8, 8, func(img *image.RGBA) {
		for y := 1; y < 7; y++ {
			for x := 2; x < 6; x++ {
				img.Set(x, y, color.RGBA{R: 60, G: 140, B: 255, A: 255})
			}
		}
	})

	rendered := renderCombatPreview(craftedItem{
		contentType: "Weapon",
		subType:     "Sword",
		stats:       itemStats{UseTime: 18},
		spritePath:  itemPath,
	}, nil, 0, 72)

	if rendered == "" {
		t.Fatal("renderCombatPreview returned empty frame")
	}
	if got := lipgloss.Width(rendered); got == 0 {
		t.Fatal("renderCombatPreview rendered zero-width output")
	}
}

func TestRenderCombatPreviewIncludesProjectileWhenAvailable(t *testing.T) {
	itemPath := writeTestSprite(t, 8, 8, func(img *image.RGBA) {
		for y := 1; y < 7; y++ {
			for x := 1; x < 7; x++ {
				img.Set(x, y, color.RGBA{R: 65, G: 135, B: 255, A: 255})
			}
		}
	})
	projPath := writeTestSprite(t, 4, 4, func(img *image.RGBA) {
		for y := 0; y < 4; y++ {
			for x := 0; x < 4; x++ {
				img.Set(x, y, color.RGBA{R: 255, G: 80, B: 40, A: 255})
			}
		}
	})

	item := craftedItem{
		contentType:    "Weapon",
		subType:        "Gun",
		stats:          itemStats{UseTime: 16},
		spritePath:     itemPath,
		projSpritePath: projPath,
	}
	profile := combatPreviewProfileFor(item, nil)
	renderedWithProjectile := renderCombatPreview(item, nil, profile.projectileDelayTicks+1, 72)
	renderedWithoutProjectile := renderCombatPreview(craftedItem{
		contentType:    item.contentType,
		subType:        item.subType,
		stats:          item.stats,
		spritePath:     item.spritePath,
		projSpritePath: "",
	}, nil, profile.projectileDelayTicks+1, 72)

	if renderedWithProjectile == renderedWithoutProjectile {
		t.Fatal("projectile sprite did not change rendered frame")
	}
}

func TestRenderCombatPreviewMissingSpritesDoesNotPanic(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("renderCombatPreview panicked: %v", r)
		}
	}()

	rendered := renderCombatPreview(craftedItem{
		contentType: "Weapon",
		subType:     "Sword",
		stats:       itemStats{UseTime: 20},
	}, nil, 3, 72)

	if rendered == "" {
		t.Fatal("missing sprites should still render a placeholder frame")
	}
}

func TestRenderCombatPreviewFrameChangesWithTick(t *testing.T) {
	itemPath := writeTestSprite(t, 10, 8, func(img *image.RGBA) {
		for y := 1; y < 7; y++ {
			for x := 2; x < 8; x++ {
				img.Set(x, y, color.RGBA{R: 100, G: 220, B: 120, A: 255})
			}
		}
	})

	item := craftedItem{
		contentType: "Weapon",
		subType:     "Sword",
		stats:       itemStats{UseTime: 18},
		spritePath:  itemPath,
	}

	early := renderCombatPreview(item, nil, 0, 72)
	later := renderCombatPreview(item, nil, 6, 72)

	if early == later {
		t.Fatal("rendered frame did not change with tick")
	}
}

func TestRenderCombatPreviewUsesFixedCanvasForWidthGuard(t *testing.T) {
	itemPath := writeTestSprite(t, 8, 8, func(img *image.RGBA) {
		for y := 1; y < 7; y++ {
			for x := 2; x < 6; x++ {
				img.Set(x, y, color.RGBA{R: 70, G: 170, B: 240, A: 255})
			}
		}
	})

	item := craftedItem{
		contentType: "Weapon",
		subType:     "Sword",
		stats:       itemStats{UseTime: 18},
		spritePath:  itemPath,
	}

	full := renderCombatPreview(item, nil, 0, 72)
	narrow := renderCombatPreview(item, nil, 0, 71)

	if full == "" {
		t.Fatal("full-width preview should render")
	}
	if narrow != "" {
		t.Fatalf("narrow preview should be empty, got %q", narrow)
	}
}
