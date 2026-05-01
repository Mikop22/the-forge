package main

import (
	"theforge/internal/ipc"
	"theforge/internal/modsources"
)

type pipelineStatus struct {
	status               string
	itemName             string
	errMsg               string
	stagePct             int
	stageLabel           string
	manifest             map[string]interface{}
	spritePath           string
	projectileSpritePath string
	injectMode           bool
}

func parseDotEnv(path string) []string {
	return ipc.ParseDotEnv(path)
}

func modSourcesDir() string {
	return modsources.Dir()
}

func readBridgeHeartbeat() bool {
	return ipc.ReadBridgeHeartbeat()
}

func readOrchestratorHeartbeat() bool {
	return ipc.ReadOrchestratorHeartbeat()
}

func writeUserRequest(prompt, tier, contentType, subType, craftingStation string, contentTypeExplicit bool, extra map[string]interface{}) error {
	return ipc.WriteUserRequest(prompt, tier, contentType, subType, craftingStation, contentTypeExplicit, extra)
}

func readGenerationStatus() pipelineStatus {
	status := ipc.ReadGenerationStatus()
	return pipelineStatus{
		status:               status.Status,
		itemName:             status.ItemName,
		errMsg:               status.ErrMsg,
		stagePct:             status.StagePct,
		stageLabel:           status.StageLabel,
		manifest:             status.Manifest,
		spritePath:           status.SpritePath,
		projectileSpritePath: status.ProjectileSpritePath,
		injectMode:           status.InjectMode,
	}
}
