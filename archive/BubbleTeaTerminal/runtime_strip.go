package main

import (
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"theforge/internal/ipc"
)

const runtimeSummaryFreshnessWindow = 10 * time.Second

func runtimeSummaryCmd() tea.Cmd {
	return tea.Tick(time.Second, func(time.Time) tea.Msg {
		return readRuntimeSummaryMsg(time.Now().UTC())
	})
}

func runtimeSummaryNowCmd() tea.Cmd {
	return func() tea.Msg {
		return readRuntimeSummaryMsg(time.Now().UTC())
	}
}

func readRuntimeSummaryMsg(now time.Time) tea.Msg {
	summary := ipc.ReadRuntimeSummary()
	status, detail := ipc.ReadConnectorStatusPayload()
	banner := resolveRuntimeBanner(summary, ipc.ReadBridgeHeartbeat(), status, detail, now)
	return runtimeSummaryMsg{banner: banner}
}

func (m *model) applyRuntimeSummaryBanner(banner workshopRuntimeBanner) {
	m.workshop.Runtime = banner
	m.bridgeAlive = banner.BridgeAlive
	m.injectStatus = banner.LastInjectStatus
	if banner.LastInjectStatus == "" {
		m.injectDetail = ""
	} else {
		m.injectDetail = banner.LastRuntimeNote
	}
}

func resolveRuntimeBanner(summary ipc.RuntimeSummary, heartbeatAlive bool, status string, detail string, now time.Time) workshopRuntimeBanner {
	if !heartbeatAlive {
		return workshopRuntimeBanner{
			BridgeAlive:     false,
			WorldLoaded:     false,
			LastRuntimeNote: "Runtime Offline",
		}
	}

	banner := workshopRuntimeBanner{
		BridgeAlive: true,
	}

	if runtimeSummaryIsFresh(summary, now) {
		banner.WorldLoaded = summary.WorldLoaded
		banner.LiveItemName = summary.LiveItemName
		banner.LastInjectStatus = summary.LastInjectStatus
		banner.LastRuntimeNote = summary.LastRuntimeNote

		if banner.LastInjectStatus == "" {
			banner.LastInjectStatus = status
		}
		if banner.LastRuntimeNote == "" {
			banner.LastRuntimeNote = detail
		}
		if banner.LastRuntimeNote == "" {
			if banner.WorldLoaded {
				banner.LastRuntimeNote = "World loaded."
			} else {
				banner.LastRuntimeNote = "At main menu."
			}
		}
		return banner
	}

	banner.WorldLoaded = false
	if summary.WorldLoaded {
		banner.LastRuntimeNote = "Runtime status stale."
	} else {
		banner.LastRuntimeNote = "At main menu."
	}
	return banner
}

func runtimeSummaryIsFresh(summary ipc.RuntimeSummary, now time.Time) bool {
	if summary.UpdatedAt == "" {
		return false
	}
	updatedAt, ok := parseRuntimeSummaryUpdatedAt(summary.UpdatedAt)
	if !ok {
		return false
	}
	if updatedAt.After(now) {
		return true
	}
	return now.Sub(updatedAt) <= runtimeSummaryFreshnessWindow
}

func parseRuntimeSummaryUpdatedAt(raw string) (time.Time, bool) {
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339} {
		if parsed, err := time.Parse(layout, raw); err == nil {
			return parsed.UTC(), true
		}
	}
	return time.Time{}, false
}
