# Architecture · One experiment, traceable boundaries

[← Documentation](README.md) · [Valency Bond](VALENCY_BOND.md) · [Evidence](EVIDENCE.md)

## The path from an idea to a run

```mermaid
flowchart LR
    Q[Research question] --> B[Valency Bond\nLiterature discovery]
    P[Uploaded paper] --> X[Source extraction]
    B --> S[Selected source\nMethod review]
    S --> X
    X --> A[AI interpretation\nTyped experiment plan]
    A --> C[Deterministic compiler\nVolumes and native commands]
    C --> V[CubOS offline validation]
    V --> O[Operator setup and loading]
    O --> R[CubOS execution]
    R --> E[Events · video · images]
    E --> I[Observation and analysis]

    classDef research fill:#D7E1F2,stroke:#233C78,color:#172137;
    classDef runtime fill:#233C78,stroke:#233C78,color:#fff;
    classDef evidence fill:#EDF3EE,stroke:#32745B,color:#172137;
    class Q,P,B,S,X,A research;
    class C,V,O,R runtime;
    class E,I evidence;
```

## Who owns what

| Component | Responsibility | Boundary |
|---|---|---|
| React workbench | Source selection, draft inspection, loading instructions, evidence views | Does not implement instrument drivers |
| FastAPI backend | Uploads, artifacts, model requests, Bond connection, protocol preparation | Credentials stay server-side |
| Valency Bond | Literature retrieval through MCP | Discovery does not certify a protocol |
| Ollama model | Source interpretation, structured proposals, review assistance | Output is validated; missing facts remain explicit |
| Deterministic compiler | Supported transfer/mix operations, exact volume splitting, tip allocation | Does not silently invent new instrument capabilities |
| CubOS validator | Command, geometry, fluid and routing checks for the supplied setup | Offline validation does not establish physical calibration |
| CubOS runtime | Instrument state, motion, protocol execution, run events | Live state is read from its owning service |
| Vision layer | Tip/liquid predictions and recorded observations | Predictions are not calibrated measurements or confirmed errors |

## What travels with an experiment

| Artifact | Purpose |
|---|---|
| Source identifiers and page-linked text | Inspect what the paper says |
| Bond retrieval receipt | Inspect how the literature was found |
| Objective and declared materials | Preserve the intended scope |
| Typed plan and adaptation notes | Separate source facts from local decisions |
| Setup snapshot and protocol hash | Identify the exact proposed configuration and command sequence |
| Validation results | Inspect software checks for that revision |
| Operator confirmations | Record the checks actually performed before execution |
| Controller events and camera evidence | Inspect what happened during the run |

Setup snapshots describe a draft's inputs. They are not a mirrored live inventory and must not be used to reset an interrupted workcell without reconciliation.

## AI and deterministic code have different jobs

The model helps interpret the paper and propose a structured plan. Code validates that structure and compiles supported operations. Large additions are split into valid strokes while preserving the total volume. Tip exhaustion, unsupported operations, unavailable quantities, and capacity conflicts remain explicit failures.

The current Picus 120 profile uses **5–120 µL strokes in 0.1 µL increments**. A total addition larger than 120 µL is not itself a pipette-limit violation when the emitted strokes satisfy the limits. Physical accuracy and liquid immersion still require independent checks.

AI review can make mistakes, including confusing total additions with individual strokes. Original findings are retained where review history is available; a model assessment is never treated as physical evidence.

## Source map

| File | Role |
|---|---|
| [`app.py`](../src/paper_to_plate/app.py) | API boundary and artifact operations |
| [`bond.py`](../src/paper_to_plate/bond.py) | OAuth and MCP literature client |
| [`llm.py`](../src/paper_to_plate/llm.py) | Server-side model calls and structured output handling |
| [`pipeline.py`](../src/paper_to_plate/pipeline.py) | Extraction, generation, review and validation orchestration |
| [`models.py`](../src/paper_to_plate/models.py) | Typed contracts |
| [`compiler.py`](../src/paper_to_plate/compiler.py) | Native liquid-handling compilation |
| [`validation.py`](../src/paper_to_plate/validation.py) | Installed CubOS offline validator integration |
| [`handoff.py`](../src/paper_to_plate/handoff.py) | Explicit operator handoff to CubOS |
| [`preparation.py`](../src/paper_to_plate/preparation.py) | Loading instructions and demand calculations |
| [`vision_service.py`](../src/paper_to_plate/vision_service.py) | Local observation and recording service |

The question explorer and recorded-workcell integration continue to evolve. This document describes the system boundaries; [the evidence guide](EVIDENCE.md) separates published artifacts, demonstrated local behavior, and remaining validation work.
