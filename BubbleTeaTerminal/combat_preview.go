package main

import (
	"image"
	"image/color"
	"image/draw"
	_ "image/png"
	"math"
	"os"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

type combatPreviewKind int

const (
	combatPreviewSwing combatPreviewKind = iota
	combatPreviewThrust
	combatPreviewShoot
)

type combatPreviewProfile struct {
	kind                 combatPreviewKind
	loopTicks            int
	projectileDelayTicks int
	projectileSpeed      float64
}

func loadPreviewSprite(path string) (image.Image, bool) {
	if path == "" {
		return nil, false
	}
	f, err := os.Open(path)
	if err != nil {
		return nil, false
	}
	defer f.Close()

	img, _, err := image.Decode(f)
	if err != nil {
		return nil, false
	}

	bounds := img.Bounds()

	// Find the bounding box of non-transparent pixels to crop whitespace.
	minX, minY, maxX, maxY := bounds.Max.X, bounds.Max.Y, bounds.Min.X, bounds.Min.Y
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			if !isTransparent(img.At(x, y)) {
				if x < minX {
					minX = x
				}
				if y < minY {
					minY = y
				}
				if x > maxX {
					maxX = x
				}
				if y > maxY {
					maxY = y
				}
			}
		}
	}

	if maxX < minX || maxY < minY {
		return nil, false
	}

	cropRect := image.Rect(0, 0, maxX-minX+1, maxY-minY+1)
	cropped := image.NewRGBA(cropRect)
	draw.Draw(cropped, cropRect, img, image.Point{X: minX, Y: minY}, draw.Src)

	return cropped, true
}

func combatPreviewProfileFor(item craftedItem, manifest map[string]interface{}) combatPreviewProfile {
	kind := combatPreviewKindForItem(item, manifest)
	loopTicks := combatPreviewLoopTicks(item.stats.UseTime)
	delayTicks := combatPreviewDelayTicks(loopTicks, kind)

	return combatPreviewProfile{
		kind:                 kind,
		loopTicks:            loopTicks,
		projectileDelayTicks: delayTicks,
		projectileSpeed:      combatPreviewProjectileSpeed(kind),
	}
}

func combatPreviewKindForItem(item craftedItem, manifest map[string]interface{}) combatPreviewKind {
	if kind, ok := combatPreviewKindFromText(item.subType); ok {
		return kind
	}

	mechanics := combatPreviewMechanics(manifest)
	if kind, ok := combatPreviewKindFromMechanics(mechanics); ok {
		return kind
	}

	if kind, ok := combatPreviewKindFromText(item.contentType); ok {
		return kind
	}

	if strings.EqualFold(item.contentType, "Weapon") {
		return combatPreviewSwing
	}

	return combatPreviewShoot
}

func combatPreviewMechanics(manifest map[string]interface{}) map[string]interface{} {
	if manifest == nil {
		return nil
	}
	if mechanics, ok := manifest["mechanics"].(map[string]interface{}); ok {
		return mechanics
	}
	return manifest
}

func combatPreviewKindFromMechanics(mechanics map[string]interface{}) (combatPreviewKind, bool) {
	if mechanics == nil {
		return 0, false
	}

	useStyle := strings.ToLower(manifestString(mechanics, "use_style", "useStyle", "use_style_name"))
	switch {
	case useStyle == "shoot" || useStyle == "ranged" || useStyle == "magic" || useStyle == "gun" || useStyle == "bow" || useStyle == "staff":
		return combatPreviewShoot, true
	case useStyle == "thrust" || useStyle == "rapier":
		return combatPreviewThrust, true
	case useStyle == "swing" || useStyle == "melee" || useStyle == "slash":
		return combatPreviewSwing, true
	}

	damageClass := strings.ToLower(manifestString(mechanics, "damage_class", "damageClass", "damage_type"))
	switch {
	case strings.Contains(damageClass, "ranged") || strings.Contains(damageClass, "magic") || strings.Contains(damageClass, "summon"):
		return combatPreviewShoot, true
	case strings.Contains(damageClass, "thrust"):
		return combatPreviewThrust, true
	case strings.Contains(damageClass, "melee"):
		return combatPreviewSwing, true
	}

	if manifestString(mechanics, "shoot_projectile", "shootProjectile", "projectile") != "" {
		return combatPreviewShoot, true
	}

	return 0, false
}

func combatPreviewKindFromText(raw string) (combatPreviewKind, bool) {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case "sword", "melee", "slash", "shortsword", "broadsword", "axe", "hammer":
		return combatPreviewSwing, true
	case "spear", "rapier", "lance":
		return combatPreviewThrust, true
	case "gun", "bow", "staff", "cannon", "ranged", "magic", "shoot":
		return combatPreviewShoot, true
	default:
		return 0, false
	}
}

func combatPreviewLoopTicks(useTime int) int {
	if useTime <= 0 {
		return 16
	}

	ticks := int(math.Round(float64(useTime) * 0.75))
	if ticks < 8 {
		ticks = 8
	}
	if ticks > 24 {
		ticks = 24
	}
	return ticks
}

func combatPreviewDelayTicks(loopTicks int, kind combatPreviewKind) int {
	delay := loopTicks / 4
	switch kind {
	case combatPreviewThrust:
		delay = loopTicks / 5
	case combatPreviewShoot:
		delay = loopTicks / 3
	}
	if delay < 1 {
		delay = 1
	}
	return delay
}

func combatPreviewProjectileSpeed(kind combatPreviewKind) float64 {
	switch kind {
	case combatPreviewThrust:
		return 9.5
	case combatPreviewShoot:
		return 14
	default:
		return 7.5
	}
}

type previewCanvas struct {
	w, h   int
	bg     color.RGBA
	pixels []color.RGBA
}

func newPreviewCanvas(w, h int, bg color.RGBA) *previewCanvas {
	if w < 0 {
		w = 0
	}
	if h < 0 {
		h = 0
	}
	pixels := make([]color.RGBA, w*h)
	for i := range pixels {
		pixels[i] = bg
	}
	return &previewCanvas{
		w:      w,
		h:      h,
		bg:     bg,
		pixels: pixels,
	}
}

func (c *previewCanvas) index(x, y int) int {
	return y*c.w + x
}

func rgbaFromColor(px color.Color) color.RGBA {
	if px == nil {
		return color.RGBA{}
	}
	r, g, b, a := px.RGBA()
	return color.RGBA{
		R: uint8(r >> 8),
		G: uint8(g >> 8),
		B: uint8(b >> 8),
		A: uint8(a >> 8),
	}
}

func (c *previewCanvas) set(x, y int, px color.Color) {
	if c == nil || x < 0 || y < 0 || x >= c.w || y >= c.h || isTransparent(px) {
		return
	}
	c.pixels[c.index(x, y)] = rgbaFromColor(px)
}

func (c *previewCanvas) drawSprite(img image.Image, centerX, centerY float64, scale float64, rotationRad float64) {
	if c == nil || img == nil || c.w == 0 || c.h == 0 || scale <= 0 {
		return
	}

	bounds := img.Bounds()
	if bounds.Empty() {
		return
	}

	srcCenterX := float64(bounds.Min.X) + float64(bounds.Dx()-1)/2.0
	srcCenterY := float64(bounds.Min.Y) + float64(bounds.Dy()-1)/2.0
	sinRot := math.Sin(rotationRad)
	cosRot := math.Cos(rotationRad)
	invScale := 1.0 / scale

	for y := 0; y < c.h; y++ {
		fy := (float64(y) - centerY) * invScale
		for x := 0; x < c.w; x++ {
			fx := (float64(x) - centerX) * invScale

			srcRelX := fx*cosRot + fy*sinRot
			srcRelY := -fx*sinRot + fy*cosRot

			sampleX := int(math.Floor(srcCenterX + srcRelX + 0.5))
			sampleY := int(math.Floor(srcCenterY + srcRelY + 0.5))
			if sampleX < bounds.Min.X || sampleX >= bounds.Max.X || sampleY < bounds.Min.Y || sampleY >= bounds.Max.Y {
				continue
			}

			c.set(x, y, img.At(sampleX, sampleY))
		}
	}
}

func (c *previewCanvas) pixelAt(x, y int) color.RGBA {
	if c == nil || x < 0 || y < 0 || x >= c.w || y >= c.h {
		return c.bg
	}
	return c.pixels[c.index(x, y)]
}

func renderPreviewCell(top, bottom, bg color.RGBA) string {
	switch {
	case top == bg && bottom == bg:
		return " "
	case top == bottom:
		return lipgloss.NewStyle().
			Foreground(lipgloss.Color(colorToHex(top))).
			Background(lipgloss.Color(colorToHex(bottom))).
			Render("▀")
	case top == bg:
		return lipgloss.NewStyle().
			Foreground(lipgloss.Color(colorToHex(bottom))).
			Background(lipgloss.Color(colorToHex(bg))).
			Render("▄")
	case bottom == bg:
		return lipgloss.NewStyle().
			Foreground(lipgloss.Color(colorToHex(top))).
			Background(lipgloss.Color(colorToHex(bg))).
			Render("▀")
	default:
		return lipgloss.NewStyle().
			Foreground(lipgloss.Color(colorToHex(top))).
			Background(lipgloss.Color(colorToHex(bottom))).
			Render("▀")
	}
}

func (c *previewCanvas) renderHalfBlocks() string {
	if c == nil || c.w <= 0 || c.h <= 0 {
		return ""
	}

	var out strings.Builder
	rows := (c.h + 1) / 2
	for row := 0; row < rows; row++ {
		if row > 0 {
			out.WriteByte('\n')
		}

		y := row * 2
		for x := 0; x < c.w; x++ {
			top := c.pixelAt(x, y)
			bottom := c.bg
			if y+1 < c.h {
				bottom = c.pixelAt(x, y+1)
			}
			out.WriteString(renderPreviewCell(top, bottom, c.bg))
		}
	}

	return out.String()
}

func renderCombatPreview(item craftedItem, manifest map[string]interface{}, tick int, maxWidth int) string {
	const (
		previewCanvasWidth  = 72
		previewCanvasHeight = 32
		minUsefulWidth      = 18
	)

	if maxWidth > 0 && maxWidth < minUsefulWidth {
		return ""
	}

	canvasWidth := previewCanvasWidth
	if maxWidth > 0 && maxWidth < canvasWidth {
		canvasWidth = maxWidth
	}
	if canvasWidth <= 0 {
		return ""
	}

	canvas := newPreviewCanvas(canvasWidth, previewCanvasHeight, color.RGBA{R: 14, G: 18, B: 24, A: 255})
	combatPreviewPaintArena(canvas)

	profile := combatPreviewProfileFor(item, manifest)
	loopTicks := profile.loopTicks
	if loopTicks <= 0 {
		loopTicks = 16
	}
	normalizedTick := combatPreviewNormalizeTick(tick, loopTicks)
	phase := float64(normalizedTick) / float64(loopTicks)

	handX := float64(canvasWidth) * 0.23
	handY := float64(canvas.h) - 11
	playerX := handX - 7
	playerTop := handY - 9
	playerBottom := float64(canvas.h) - 7

	combatPreviewDrawPlayer(canvas, playerX, playerTop, playerBottom, handX, handY, phase)

	itemImg, ok := loadPreviewSprite(item.spritePath)
	if !ok {
		itemImg = combatPreviewPlaceholderSprite(profile.kind)
	}
	combatPreviewDrawItem(canvas, itemImg, handX, handY, profile, normalizedTick, phase)

	if profile.kind == combatPreviewShoot {
		combatPreviewDrawMuzzleFlash(canvas, handX, handY, profile, normalizedTick, phase)
	}

	if projImg, ok := loadPreviewSprite(item.projSpritePath); ok {
		combatPreviewDrawProjectile(canvas, projImg, handX, handY, profile, normalizedTick, phase)
	}

	return canvas.renderHalfBlocks()
}

func combatPreviewNormalizeTick(tick int, loopTicks int) int {
	if loopTicks <= 0 {
		return 0
	}
	t := tick % loopTicks
	if t < 0 {
		t += loopTicks
	}
	return t
}

func combatPreviewPaintArena(canvas *previewCanvas) {
	if canvas == nil || canvas.w <= 0 || canvas.h <= 0 {
		return
	}

	backWall := color.RGBA{R: 22, G: 28, B: 36, A: 255}
	floor := color.RGBA{R: 26, G: 34, B: 28, A: 255}
	line := color.RGBA{R: 78, G: 88, B: 92, A: 255}

	for y := 0; y < canvas.h; y++ {
		for x := 0; x < canvas.w; x++ {
			switch {
			case y >= canvas.h-5:
				canvas.set(x, y, floor)
			case y == canvas.h-6:
				canvas.set(x, y, line)
			default:
				canvas.set(x, y, backWall)
			}
		}
	}

	horizonY := canvas.h/2 - 2
	for x := 0; x < canvas.w; x += 4 {
		canvas.set(x, horizonY, color.RGBA{R: 34, G: 42, B: 50, A: 255})
	}
}

func combatPreviewDrawPlayer(canvas *previewCanvas, playerX, playerTop, playerBottom, handX, handY, phase float64) {
	if canvas == nil {
		return
	}

	body := color.RGBA{R: 61, G: 68, B: 81, A: 255}
	shadow := color.RGBA{R: 28, G: 31, B: 39, A: 255}
	skin := color.RGBA{R: 214, G: 188, B: 150, A: 255}
	outline := color.RGBA{R: 96, G: 103, B: 117, A: 255}

	px := int(math.Round(playerX))
	py := int(math.Round(playerTop))
	pb := int(math.Round(playerBottom))
	hx := int(math.Round(handX))
	hy := int(math.Round(handY))

	combatPreviewFillRect(canvas, px+2, py+4, 5, 7, body)
	combatPreviewFillRect(canvas, px+1, py+5, 7, 1, shadow)
	combatPreviewFillRect(canvas, px+3, py+1, 3, 3, skin)
	combatPreviewFillRect(canvas, px, py+5, 2, 5, outline)
	combatPreviewFillRect(canvas, px+7, py+5, 2, 5, outline)
	combatPreviewDrawLine(canvas, px+4, py+6, hx, hy, skin)
	combatPreviewDrawLine(canvas, px+4, py+7, px+2, pb-1, shadow)
	combatPreviewDrawLine(canvas, px+5, py+7, px+7, pb-1, shadow)

	if phase > 0.5 {
		canvas.set(hx, hy, skin)
		canvas.set(hx+1, hy, skin)
	} else {
		canvas.set(hx, hy, skin)
	}
}

func combatPreviewDrawItem(canvas *previewCanvas, itemImg image.Image, handX, handY float64, profile combatPreviewProfile, tick int, phase float64) {
	if canvas == nil || itemImg == nil {
		return
	}

	// The item is animated around the hand anchor and rotated to suggest the
	// current attack style without trying to reproduce Terraria's full arm math.
	var (
		centerX  = handX + 6
		centerY  = handY
		scale    = 1.0
		rotation = 0.0
	)

	switch profile.kind {
	case combatPreviewSwing:
		swing := -1.65 + math.Sin(phase*math.Pi*2)*1.25
		reach := 6.0 + math.Sin(phase*math.Pi)*2.5
		centerX = handX + math.Cos(swing)*reach
		centerY = handY + math.Sin(swing)*reach*0.72
		rotation = swing + 0.65
		scale = 1.08
	case combatPreviewThrust:
		thrust := 0.5 - 0.5*math.Cos(phase*math.Pi*2)
		centerX = handX + 2.5 + thrust*10.5
		centerY = handY - 0.3 + math.Sin(phase*math.Pi*2)*0.8
		rotation = 0.16 + thrust*0.2
		scale = 1.02 + thrust*0.08
	case combatPreviewShoot:
		recoil := math.Sin(phase * math.Pi * 2)
		centerX = handX + 5.2 + recoil*0.8
		centerY = handY - 1.2 + math.Sin(phase*math.Pi*2)*0.4
		rotation = -0.12 + recoil*0.07
		scale = 0.98
	default:
		centerX = handX + 4.8
		centerY = handY - 0.8
	}

	canvas.drawSprite(itemImg, centerX, centerY, scale, rotation)
	combatPreviewDrawItemAccent(canvas, centerX, centerY, rotation, profile, phase)
}

func combatPreviewDrawProjectile(canvas *previewCanvas, projImg image.Image, handX, handY float64, profile combatPreviewProfile, tick int, phase float64) {
	if canvas == nil || projImg == nil || profile.kind != combatPreviewShoot {
		return
	}

	delay := profile.projectileDelayTicks
	if tick < delay {
		return
	}

	flightTicks := profile.loopTicks - delay
	if flightTicks < 4 {
		flightTicks = 4
	}
	flightPhase := float64(tick-delay) / float64(flightTicks)
	if flightPhase > 1 {
		flightPhase = math.Mod(flightPhase, 1)
	}

	startX := handX + 6
	startY := handY - 0.4
	maxTravel := math.Min(float64(canvas.w)-startX-3, profile.projectileSpeed*3.2)
	if maxTravel < 2 {
		maxTravel = 2
	}

	projectileX := startX + flightPhase*maxTravel
	projectileY := startY - math.Sin(flightPhase*math.Pi)*1.25
	rotation := math.Atan2(-math.Sin(flightPhase*math.Pi)*0.28, profile.projectileSpeed)
	scale := 0.78
	if profile.projectileSpeed > 10 {
		scale = 0.9
	}

	canvas.drawSprite(projImg, projectileX, projectileY, scale, rotation)
	combatPreviewDrawProjectileTrail(canvas, projectileX, projectileY, profile, phase)

	if flightPhase < 0.18 {
		combatPreviewDrawSpark(canvas, int(math.Round(projectileX))+1, int(math.Round(projectileY)), color.RGBA{R: 255, G: 214, B: 122, A: 255})
	}
}

func combatPreviewDrawMuzzleFlash(canvas *previewCanvas, handX, handY float64, profile combatPreviewProfile, tick int, phase float64) {
	if canvas == nil || profile.kind != combatPreviewShoot {
		return
	}

	if tick < profile.projectileDelayTicks-1 || tick > profile.projectileDelayTicks+1 {
		return
	}

	baseX := int(math.Round(handX + 5))
	baseY := int(math.Round(handY - 1))
	combatPreviewEraseHorizontalMark(canvas, baseX-1, baseY, 4)
	combatPreviewEraseHorizontalMark(canvas, baseX, baseY-1, 2)
	if math.Sin(phase*math.Pi*2) > 0 {
		combatPreviewEraseHorizontalMark(canvas, baseX+1, baseY+1, 3)
	}
}

func combatPreviewDrawSpark(canvas *previewCanvas, x, y int, px color.RGBA) {
	if canvas == nil {
		return
	}

	canvas.set(x, y, px)
	canvas.set(x-1, y, px)
	canvas.set(x+1, y, px)
	canvas.set(x, y-1, px)
	canvas.set(x, y+1, px)
}

func combatPreviewDrawHorizontalMark(canvas *previewCanvas, x, y, length int, px color.RGBA) {
	if canvas == nil || length <= 0 {
		return
	}
	for i := 0; i < length; i++ {
		canvas.set(x+i, y, px)
	}
}

func combatPreviewEraseHorizontalMark(canvas *previewCanvas, x, y, length int) {
	if canvas == nil || length <= 0 {
		return
	}
	for i := 0; i < length; i++ {
		canvas.set(x+i, y, canvas.bg)
	}
}

func combatPreviewDrawItemAccent(canvas *previewCanvas, centerX, centerY, rotation float64, profile combatPreviewProfile, phase float64) {
	if canvas == nil {
		return
	}

	switch profile.kind {
	case combatPreviewSwing:
		accentX := int(math.Round(centerX + math.Cos(rotation-0.9)*5.2))
		accentY := int(math.Round(centerY + math.Sin(rotation-0.9)*4.4))
		if phase < 0.5 {
			accentY--
		} else {
			accentY++
		}
		if accentY%2 != 0 {
			accentY--
		}
		combatPreviewEraseHorizontalMark(canvas, accentX-2, accentY, 5)
		combatPreviewEraseHorizontalMark(canvas, accentX-1, accentY-1, 3)
	case combatPreviewThrust:
		accentX := int(math.Round(centerX + math.Cos(rotation)*6.0))
		accentY := int(math.Round(centerY + math.Sin(rotation)*4.0))
		if accentY%2 != 0 {
			accentY--
		}
		combatPreviewEraseHorizontalMark(canvas, accentX-1, accentY, 4)
	case combatPreviewShoot:
		accentX := int(math.Round(centerX - 3 + math.Cos(phase*math.Pi*2)*2.2))
		accentY := int(math.Round(centerY - 1 + math.Sin(phase*math.Pi*2)*1.2))
		if accentY%2 != 0 {
			accentY--
		}
		combatPreviewEraseHorizontalMark(canvas, accentX-1, accentY, 3)
	}
}

func combatPreviewDrawProjectileTrail(canvas *previewCanvas, projectileX, projectileY float64, profile combatPreviewProfile, phase float64) {
	if canvas == nil || profile.kind != combatPreviewShoot {
		return
	}

	headX := int(math.Round(projectileX))
	headY := int(math.Round(projectileY))
	if headY%2 != 0 {
		headY--
	}
	combatPreviewEraseHorizontalMark(canvas, headX-1, headY, 4)
	if phase < 0.5 {
		combatPreviewEraseHorizontalMark(canvas, headX-2, headY+1, 3)
	} else {
		combatPreviewEraseHorizontalMark(canvas, headX-2, headY-1, 3)
	}
}

func combatPreviewFillRect(canvas *previewCanvas, x, y, w, h int, px color.RGBA) {
	if canvas == nil || w <= 0 || h <= 0 {
		return
	}
	for yy := 0; yy < h; yy++ {
		for xx := 0; xx < w; xx++ {
			canvas.set(x+xx, y+yy, px)
		}
	}
}

func combatPreviewDrawLine(canvas *previewCanvas, x0, y0, x1, y1 int, px color.RGBA) {
	if canvas == nil {
		return
	}

	dx := int(math.Abs(float64(x1 - x0)))
	sx := -1
	if x0 < x1 {
		sx = 1
	}
	dy := -int(math.Abs(float64(y1 - y0)))
	sy := -1
	if y0 < y1 {
		sy = 1
	}
	err := dx + dy
	for {
		canvas.set(x0, y0, px)
		if x0 == x1 && y0 == y1 {
			break
		}
		e2 := 2 * err
		if e2 >= dy {
			err += dy
			x0 += sx
		}
		if e2 <= dx {
			err += dx
			y0 += sy
		}
	}
}

func combatPreviewPlaceholderSprite(kind combatPreviewKind) image.Image {
	img := image.NewRGBA(image.Rect(0, 0, 10, 10))

	switch kind {
	case combatPreviewThrust:
		for x := 1; x < 9; x++ {
			img.Set(x, 4, color.RGBA{R: 232, G: 219, B: 179, A: 255})
		}
		for y := 2; y < 8; y++ {
			img.Set(7, y, color.RGBA{R: 142, G: 91, B: 58, A: 255})
		}
		img.Set(8, 3, color.RGBA{R: 255, G: 228, B: 160, A: 255})
	case combatPreviewShoot:
		for y := 4; y < 8; y++ {
			for x := 1; x < 8; x++ {
				img.Set(x, y, color.RGBA{R: 94, G: 107, B: 125, A: 255})
			}
		}
		for x := 3; x < 9; x++ {
			img.Set(x, 5, color.RGBA{R: 190, G: 205, B: 224, A: 255})
		}
		img.Set(8, 4, color.RGBA{R: 255, G: 205, B: 88, A: 255})
	default:
		for i := 1; i < 9; i++ {
			img.Set(i, i-1, color.RGBA{R: 211, G: 226, B: 245, A: 255})
			if i < 7 {
				img.Set(i, i, color.RGBA{R: 108, G: 138, B: 191, A: 255})
			}
		}
		img.Set(2, 6, color.RGBA{R: 255, G: 248, B: 227, A: 255})
	}

	return img
}
