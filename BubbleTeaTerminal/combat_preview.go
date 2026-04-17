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
