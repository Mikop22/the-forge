package main

import (
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textinput"
)

type screen int

const (
	screenMode screen = iota
	screenWizard
	screenInput
	screenForge
	screenStaging
)

type forgeDoneMsg struct{}
type forgeErrMsg struct{ message string }
type bridgeStatusMsg struct{ alive bool }

type animTickMsg time.Time
type connectorStatusMsg struct {
	status string
	detail string
}
type runtimeSummaryMsg struct {
	banner workshopRuntimeBanner
}

type operationKind string

const (
	operationIdle      operationKind = ""
	operationForging   operationKind = "forging"
	operationDirector  operationKind = "director"
	operationInjecting operationKind = "injecting"
)

type previewMode int

const (
	previewModeActions previewMode = iota
	previewModeReprompt
	previewModeStats
)

type optionItem struct {
	title string
	desc  string
}

func (i optionItem) Title() string       { return i.title }
func (i optionItem) Description() string { return i.desc }
func (i optionItem) FilterValue() string { return i.title }

type itemStats struct {
	Damage     int     `json:"damage"`
	Knockback  float64 `json:"knockback"`
	CritChance int     `json:"crit_chance"`
	UseTime    int     `json:"use_time"`
	Rarity     string  `json:"rarity"`
}

type craftedItem struct {
	label           string
	tier            string
	contentType     string
	subType         string
	craftingStation string
	stats           itemStats
	spritePath      string
	projSpritePath  string
}

type statField struct {
	key     string
	label   string
	step    float64
	minimum float64
}

type wizardStep struct {
	question string
	options  []optionItem
}

var contentTypeOptions = []optionItem{
	{title: "Weapon", desc: "Melee, ranged, and magic armaments"},
	{title: "Accessory", desc: "Passive mobility, defense, and buffs"},
	{title: "Summon", desc: "Minion staves with persistent companions"},
	{title: "Consumable", desc: "Potions, ammo, and thrown items"},
	{title: "Tool", desc: "Hooks and fishing gear"},
}

var tierOptions = []optionItem{
	{title: "Starter", desc: "Early game balance and simple effects"},
	{title: "Dungeon", desc: "Midgame utility with stronger scaling"},
	{title: "Hardmode", desc: "High pressure combat and synergy hooks"},
	{title: "Endgame", desc: "Peak-tier stats and complex behavior"},
}

var subTypeOptions = map[string][]optionItem{
	"Weapon": {
		{title: "Sword", desc: "Broad melee arc with direct contact"},
		{title: "Bow", desc: "Ranged weapon built around arrows"},
		{title: "Staff", desc: "Magic focus with projectile casting"},
		{title: "Gun", desc: "Fast ranged weapon with bullet fire"},
		{title: "Cannon", desc: "Heavy launcher with loud impact"},
		{title: "Spear", desc: "Reach-focused thrusting weapon"},
	},
	"Accessory": {
		{title: "Wings", desc: "Flight time and aerial mobility"},
		{title: "Shield", desc: "Defense, dash, and survivability"},
		{title: "Movement", desc: "Speed and traversal boosts"},
		{title: "StatBoost", desc: "Passive combat enhancement"},
	},
	"Summon": {
		{title: "MinionStaff", desc: "Summons a persistent helper minion"},
	},
	"Consumable": {
		{title: "HealPotion", desc: "Restores life on use"},
		{title: "ManaPotion", desc: "Restores mana on use"},
		{title: "BuffPotion", desc: "Applies a temporary buff"},
		{title: "ThrownWeapon", desc: "Consumable damage item"},
		{title: "Ammo", desc: "Stackable ammunition"},
	},
	"Tool": {
		{title: "Hook", desc: "Grapple through terrain with a tether"},
		{title: "FishingRod", desc: "Fishing utility with power scaling"},
	},
}

var previewStatFields = []statField{
	{key: "damage", label: "Damage", step: 1, minimum: 1},
	{key: "use_time", label: "Use Time", step: 1, minimum: 1},
	{key: "knockback", label: "Knockback", step: 0.5, minimum: 0},
}

type model struct {
	state        screen
	width        int
	height       int
	contentWidth int

	craftedItems   []craftedItem
	generatedItems []libraryItem
	workshop       workshopState

	textInput    textinput.Model
	previewInput textinput.Model
	commandInput textinput.Model
	modeList     list.Model
	wizardList   list.Model
	spinner      spinner.Model
	sessionShell sessionShellState

	prompt              string
	tier                string
	contentType         string
	contentTypeExplicit bool
	subType             string
	damageClass         string
	styleChoice         string
	projectile          string
	craftingStation     string

	wizardIndex   int
	errMsg        string
	injecting     bool
	animTick      int
	heat          int
	revealPhase   int
	lastForgeVerb int
	termCompact   bool

	forgeItemName  string
	forgeErr       string
	stageLabel     string
	stageTargetPct int

	forgeManifest map[string]interface{}
	forgeSprPath  string
	forgeProjPath string
	previewMode   previewMode
	previewItem   *craftedItem
	statEditIndex int

	bridgeAlive        bool
	injectErr          string
	injectStatus       string
	injectDetail       string
	commandMode        bool
	autocompleteIndex  int
	workshopNotice     string
	shellNotice        string
	shellError         string
	pendingManifest    map[string]interface{}
	pendingArtFeedback string
	operationKind      operationKind
	operationLabel     string
	operationStartedAt time.Time
	operationStale     bool
	forgePollCount     int
}

const (
	compactWidthThreshold  = 84
	compactHeightThreshold = 24
)

var forgeVerbs = []string{"Tempering", "Binding", "Etching", "Awakening"}
var wizardGlyphs = []string{"\u26e8", "\u2694", "\u2736", "\u27b6"}

func (m model) hasActiveWorkshopBench() bool {
	return strings.TrimSpace(m.workshop.Bench.ItemID) != "" || m.workshop.Bench.Manifest != nil
}

func (m model) shellSuggestion() string {
	if strings.TrimSpace(m.commandInput.Value()) != "" {
		return ""
	}

	if !m.hasActiveWorkshopBench() {
		return "/forge <prompt>"
	}

	if len(m.workshop.Shelf) > 0 {
		return "/bench <variant-id-or-number>"
	}

	return "/variants <direction>"
}

