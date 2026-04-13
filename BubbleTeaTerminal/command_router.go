package main

import (
	"strconv"
	"strings"
)

type commandAction string

const (
	commandActionNone        commandAction = ""
	commandActionForge       commandAction = "forge"
	commandActionVariants    commandAction = "variants"
	commandActionBench       commandAction = "bench"
	commandActionRestore     commandAction = "restore"
	commandActionTry         commandAction = "try"
	commandActionStatus      commandAction = "status"
	commandActionMemory      commandAction = "memory"
	commandActionWhatChanged commandAction = "what_changed"
	commandActionHelp        commandAction = "help"
	commandActionUnsupported commandAction = "unsupported"
)

type commandRoute struct {
	Action        commandAction
	Directive     string
	VariantID     string
	RestoreTarget string
}

func routeWorkshopCommand(input string, hasActiveBench bool, shelf []workshopVariant) commandRoute {
	text := strings.TrimSpace(input)
	if text == "" {
		return commandRoute{}
	}

	if !strings.HasPrefix(text, "/") {
		if hasActiveBench {
			return commandRoute{Action: commandActionVariants, Directive: text}
		}
		return commandRoute{Action: commandActionForge, Directive: text}
	}

	trimmed := strings.TrimSpace(strings.TrimPrefix(text, "/"))
	if trimmed == "" {
		return commandRoute{}
	}

	parts := strings.Fields(trimmed)
	if len(parts) == 0 {
		return commandRoute{}
	}

	name := strings.ToLower(parts[0])
	arg := strings.TrimSpace(trimmed[len(parts[0]):])

	switch name {
	case "forge":
		if strings.TrimSpace(arg) == "" {
			return commandRoute{Action: commandActionUnsupported}
		}
		return commandRoute{Action: commandActionForge, Directive: arg}
	case "variants":
		return commandRoute{Action: commandActionVariants, Directive: arg}
	case "bench":
		tokens := strings.Fields(arg)
		if len(tokens) != 1 {
			return commandRoute{Action: commandActionUnsupported, Directive: strings.TrimSpace(arg)}
		}
		raw := tokens[0]
		if idx, err := strconv.Atoi(raw); err == nil {
			zeroIdx := idx - 1
			if zeroIdx < 0 || zeroIdx >= len(shelf) {
				return commandRoute{Action: commandActionUnsupported, Directive: raw}
			}
			resolved := shelf[zeroIdx].VariantID
			return commandRoute{Action: commandActionBench, Directive: resolved, VariantID: resolved}
		}
		return commandRoute{Action: commandActionBench, Directive: raw, VariantID: raw}
	case "restore":
		target, ok := normalizeRestoreTarget(arg)
		if !ok {
			return commandRoute{Action: commandActionUnsupported, Directive: arg}
		}
		return commandRoute{Action: commandActionRestore, RestoreTarget: target}
	case "try":
		if strings.TrimSpace(arg) != "" {
			return commandRoute{Action: commandActionUnsupported, Directive: arg}
		}
		return commandRoute{Action: commandActionTry}
	case "status":
		if strings.TrimSpace(arg) != "" {
			return commandRoute{Action: commandActionUnsupported, Directive: arg}
		}
		return commandRoute{Action: commandActionStatus}
	case "memory":
		if strings.TrimSpace(arg) != "" {
			return commandRoute{Action: commandActionUnsupported, Directive: arg}
		}
		return commandRoute{Action: commandActionMemory}
	case "what-changed":
		if strings.TrimSpace(arg) != "" {
			return commandRoute{Action: commandActionUnsupported, Directive: arg}
		}
		return commandRoute{Action: commandActionWhatChanged}
	case "help":
		if strings.TrimSpace(arg) != "" {
			return commandRoute{Action: commandActionUnsupported, Directive: arg}
		}
		return commandRoute{Action: commandActionHelp}
	default:
		return commandRoute{Action: commandActionUnsupported, Directive: arg}
	}
}

func isLocalShellInfoAction(action commandAction) bool {
	switch action {
	case commandActionStatus, commandActionMemory, commandActionWhatChanged, commandActionHelp:
		return true
	default:
		return false
	}
}

func (m model) shellInfoResponse(route commandRoute) string {
	switch route.Action {
	case commandActionStatus:
		bench := strings.TrimSpace(m.workshop.Bench.Label)
		if bench == "" {
			bench = "none"
		}
		runtime := "runtime offline"
		if m.workshop.Runtime.BridgeAlive || m.bridgeAlive {
			runtime = "runtime online"
		}
		return "Status: bench " + bench + "; " + runtime
	case commandActionMemory:
		notes := loadPinnedMemoryNotes()
		if len(notes) == 0 {
			return "Memory: no pinned notes"
		}
		return "Memory: " + strings.Join(notes, "; ")
	case commandActionWhatChanged:
		if !m.hasActiveWorkshopBench() {
			return "What changed: no active bench"
		}
		return "What changed: bench " + m.workshop.Bench.Label + "; shelf variants " + strconv.Itoa(len(m.workshop.Shelf))
	case commandActionHelp:
		return "Commands: /forge, /variants, /bench, /try, /restore, /status, /memory, /what-changed, /help"
	default:
		return ""
	}
}

func isEmptyForgeCommand(input string) bool {
	trimmed := strings.TrimSpace(input)
	if !strings.HasPrefix(trimmed, "/") {
		return false
	}
	parts := strings.Fields(strings.TrimSpace(strings.TrimPrefix(trimmed, "/")))
	return len(parts) == 1 && strings.EqualFold(parts[0], "forge")
}

func normalizeRestoreTarget(raw string) (string, bool) {
	target := strings.ToLower(strings.TrimSpace(raw))
	switch target {
	case "baseline":
		return "baseline", true
	case "live":
		return "last_live", true
	default:
		return "", false
	}
}

func buildWorkshopRequestPayloadFromRoute(route commandRoute, sessionID, benchItemID string, snapshotID int) map[string]interface{} {
	payload := map[string]interface{}{
		"action":        string(route.Action),
		"session_id":    sessionID,
		"bench_item_id": benchItemID,
		"snapshot_id":   snapshotID,
	}

	switch route.Action {
	case commandActionVariants:
		payload["directive"] = route.Directive
	case commandActionBench:
		payload["variant_id"] = route.VariantID
	case commandActionRestore:
		payload["restore_target"] = route.RestoreTarget
	case commandActionForge, commandActionTry:
		if route.Directive != "" {
			payload["directive"] = route.Directive
		}
	default:
		if route.Directive != "" {
			payload["directive"] = route.Directive
		}
	}

	return payload
}
