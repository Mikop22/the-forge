package main

import "github.com/charmbracelet/lipgloss"

var (
	colorBg       = lipgloss.Color("#000000")
	colorBgB      = lipgloss.Color("#0A0A0A")
	colorPanel    = lipgloss.Color("#0D0D0D")
	colorRune     = lipgloss.Color("#4DDB80")
	colorRuneHot  = lipgloss.Color("#7EE2A0")
	colorGold     = lipgloss.Color("#C8A14A")
	colorText     = lipgloss.Color("#FAFAFA")
	colorDim      = lipgloss.Color("#7B738F")
	colorError    = lipgloss.Color("#FF4D5A")
	colorSigilBg  = lipgloss.Color("#050505")
	colorSpriteBg = lipgloss.Color("#FFFFFF")
)

type uiStyles struct {
	FrameCalm    lipgloss.Style
	FrameCharged lipgloss.Style
	FrameCracked lipgloss.Style
	TitleRune    lipgloss.Style
	Subtitle     lipgloss.Style
	Hint         lipgloss.Style
	Error        lipgloss.Style
	Success      lipgloss.Style
	Progress     lipgloss.Style
	Inventory    lipgloss.Style
	Injecting    lipgloss.Style
	Pending      lipgloss.Style
	PromptInput  lipgloss.Style
	Ember        lipgloss.Style
	SigilColumn  lipgloss.Style
	Meta         lipgloss.Style
	Body         lipgloss.Style
	SpriteFrame  lipgloss.Style
	StatsFrame   lipgloss.Style
	StatsLabel   lipgloss.Style
	StatsValue   lipgloss.Style
	StatsTitle   lipgloss.Style
}

var styles = newStyles()

func newStyles() uiStyles {
	return uiStyles{
		FrameCalm: lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(colorRune).
			Background(colorPanel).
			Padding(1, 2),
		FrameCharged: lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(colorGold).
			Background(colorPanel).
			Padding(1, 2),
		FrameCracked: lipgloss.NewStyle().
			Border(lipgloss.DoubleBorder()).
			BorderForeground(colorRuneHot).
			Background(colorBgB).
			Padding(1, 2),
		TitleRune: lipgloss.NewStyle().
			Foreground(colorRune).
			Bold(true),
		Subtitle: lipgloss.NewStyle().
			Foreground(colorText),
		Hint: lipgloss.NewStyle().
			Foreground(colorDim),
		Error: lipgloss.NewStyle().
			Foreground(colorError).
			Bold(true),
		Success: lipgloss.NewStyle().
			Foreground(colorRuneHot).
			Bold(true),
		Progress: lipgloss.NewStyle().
			Foreground(colorGold).
			Bold(true),
		Inventory: lipgloss.NewStyle().
			Foreground(colorText),
		Injecting: lipgloss.NewStyle().
			Foreground(colorGold).
			Bold(true),
		Pending: lipgloss.NewStyle().
			Foreground(colorGold),
		PromptInput: lipgloss.NewStyle().
			Foreground(colorText),
		Ember: lipgloss.NewStyle().
			Foreground(colorGold),
		SigilColumn: lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(colorDim).
			Background(colorSigilBg).
			Padding(0, 1).
			Width(14),
		Meta: lipgloss.NewStyle().
			Foreground(colorGold),
		Body: lipgloss.NewStyle().
			Foreground(colorText),
		SpriteFrame: lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(colorDim).
			Background(colorSpriteBg).
			Padding(0, 1),
		StatsFrame: lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(colorGold).
			Padding(0, 1).
			Width(26),
		StatsLabel: lipgloss.NewStyle().
			Foreground(colorGold),
		StatsValue: lipgloss.NewStyle().
			Foreground(colorText),
		StatsTitle: lipgloss.NewStyle().
			Foreground(colorRune).
			Bold(true),
	}
}
