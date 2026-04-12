# Weapon Lab System Diagram

## Full System

```mermaid
flowchart TD
    U[User Prompt in TUI] --> WR[user_request.json]
    WR --> O[orchestrator.py]

    O --> A1[Architect: thesis prompt + research evidence]
    A1 --> T[Hidden Thesis Batch]
    T --> TJ[Bounded thesis judges + hard gates]
    TJ --> RF[Ranked finalists]

    RF --> FE[Finalist expansion to package-first manifests]
    FE --> CM[Runtime capability matrix check]

    CM --> P1[Pixelsmith art-direction mapping]
    P1 --> P2[Multi-candidate sprite generation]
    P2 --> SG[Deterministic sprite gates]
    SG --> VS[Variant selection: motif + family coherence]
    VS --> ART[Art-scored finalists]

    ART --> CC[Cross-consistency gate]
    CC -->|reject| ARC[WeaponLabArchive]
    CC -->|pass| HL[Hidden runtime lab gate]

    HL --> HREQ[forge_lab_hidden_request.json]
    HREQ --> FC[ForgeConnector runtime]
    FC --> TEL[forge_lab_runtime_events.jsonl]
    FC --> HRES[forge_lab_hidden_result.json]
    HRES --> HLG[BehaviorContract evaluation]

    HLG -->|fail| ARC
    HLG -->|pass| WIN[Single winner]

    WIN --> CODE[Forge Master codegen]
    WIN --> ARTREADY[Winning art paths]
    CODE --> GK[Gatekeeper build and stage]
    GK --> READY[generation_status.json ready]
    ARTREADY --> READY

    READY --> TUI[Reveal only winner in TUI]
    TUI --> INJ[Accept and inject]
    INJ --> FI[forge_inject.json]
    FI --> FC
    FC --> STAT[forge_connector_status.json]
    STAT --> TUI

    ARC --> OFF[Offline eval + stress suites]
    OFF --> REROLL[Recovery mode]
    REROLL --> T
```

## Validation Layers

```mermaid
flowchart LR
    P[Prompt] --> TH[Thesis Validation]
    TH --> MF[Manifest Validation]
    MF --> AR[Art Validation]
    AR --> RT[Runtime Validation]
    RT --> RV[Reveal Winner]

    TH -->|fail| RR[Reroll / wild recovery]
    MF -->|fail| RR
    AR -->|fail| RR
    RT -->|fail| RR
    RR --> P
```

## Runtime Evidence Path

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant M as ModSources
    participant F as ForgeConnector
    participant G as ForgeItem/Projectile globals

    O->>M: write forge_lab_hidden_request.json
    F->>M: read hidden request
    F->>G: register candidate telemetry context
    G->>M: append forge_lab_runtime_events.jsonl
    G->>M: write forge_lab_hidden_result.json
    O->>M: poll hidden result
    O->>O: evaluate BehaviorContract
    O->>O: pass/fail runtime gate
```

## Key Files

- `agents/orchestrator.py`
- `agents/architect/research_evidence.py`
- `agents/architect/weapon_thesis_prompt.py`
- `agents/architect/thesis_generator.py`
- `agents/core/runtime_capabilities.py`
- `agents/core/weapon_lab_archive.py`
- `agents/core/weapon_lab_ranking.py`
- `agents/core/cross_consistency.py`
- `agents/core/runtime_contracts.py`
- `agents/core/recovery_mode.py`
- `agents/pixelsmith/art_direction.py`
- `agents/pixelsmith/sprite_gates.py`
- `agents/pixelsmith/pixelsmith.py`
- `mod/ForgeConnector/ForgeLabTelemetry.cs`
- `mod/ForgeConnector/ForgeConnectorSystem.cs`
- `mod/ForgeConnector/ForgeItemGlobal.cs`
- `mod/ForgeConnector/ForgeProjectileGlobal.cs`
