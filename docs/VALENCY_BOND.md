# Valency Bond · From a question to a physical sample

[← Project](../README.md) · [Demo](DEMO.md) · [Architecture](ARCHITECTURE.md) · [Evidence](EVIDENCE.md)

<img src="assets/valency-path.svg" alt="Ask, retrieve with Bond, choose a source, adapt to the bench, execute and record" width="100%" />

## The experiment starts with a better question

> “I have a single-channel liquid handler, a camera, and red, yellow, and blue dyes. What experiment could I explore?”

Paper to Plate uses **Valency Bond as the literature layer before protocol generation**. Bond turns an open-ended idea into identifiable research. The selected method then gives the AI and compiler something concrete to work from: a scientific objective, a procedure, a measurement strategy, and the boundaries of an adaptation.

This makes literature discovery part of the experiment's construction. The paper, the proposed design, the compiled protocol, and the eventual recording can be inspected together.

## What is implemented

| Layer | Concrete behavior | Evidence |
|---|---|---|
| Connection | OAuth authorization-code flow with PKCE; refresh access stays on the backend | [`bond.py`](../src/paper_to_plate/bond.py) |
| Retrieval | Real MCP initialization and `semantic_search_papers` calls | Same client; query receipts retained with designs |
| Interpretation | Retrieved sources are passed to the configured AI model | [`design_api.py`](../src/paper_to_plate/design_api.py) |
| Source checks | Returned paper IDs are retained; quoted claims are checked against supplied source text | Design records and explicit unresolved items |
| Recipe generation | Supported templates use deterministic arithmetic and native compilation | [`experiment_design.py`](../src/paper_to_plate/experiment_design.py), [`compiler.py`](../src/paper_to_plate/compiler.py) |
| Traceability | Queries, paper links, design assumptions, protocol hashes, and observations remain inspectable | Exported experiment artifacts |

The current client uses Bond's semantic-search tool. Related-paper, citation, author, and trend tools are possible extensions; they are not claimed as implemented features here.

## A real call, not a simulated search

**Endpoint:** `https://mcp.valency.io/`  
**Transport:** MCP over HTTP  
**Authentication:** OAuth 2.0 with PKCE

After initialization, the application calls the actual Bond tool:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "semantic_search_papers",
    "arguments": {
      "query": "autonomous laboratory color matching red yellow blue dye mixtures camera RGB target color optimization liquid handling",
      "limit": 6,
      "max_authors": 3,
      "enrich_citations": false
    }
  }
}
```

The response contains paper identifiers, titles, abstracts, source URLs, and request metadata. The application retains those identifiers instead of inventing references from model memory.

An actual saved search is included in [`examples/bond-color-search.json`](../examples/bond-color-search.json), with request ID `12342d8431ca4081a5ba1f85f02646bd`. It is a **recorded receipt**, not a live endpoint or a current-search claim.

## Case study 01 · Bradford, translated into a demo

**Research objective:** quantify protein in an unknown sample using a standard curve.

**Selected source:** [Ernst & Zor, *Linearization of the Bradford Protein Assay*](https://pmc.ncbi.nlm.nih.gov/articles/PMC3164080/), DOI `10.3791/1918`.

**Bench adaptation:** preserve the preparation structure using red standard surrogate, yellow unknown surrogate, blue working-reagent surrogate, and water. The full example contains six standard levels, a diluted unknown, and separate water blanks in triplicate.

**What this demonstrates:** converting a source-specific liquid workflow into a bounded, reviewable preparation plan. It does not reproduce protein-binding chemistry or calculate protein concentration from colored water.

Broad Bradford queries also retrieved camera-based RGBradford papers. The implementation keeps those methods distinct from the selected two-wavelength protocol. An apparently relevant paper is not silently substituted for a different method.

[Inspect the Bradford liquid workflow →](../examples/bradford-color-demo/README.md)

## Case study 02 · A question becomes a physical mixture screen

**Research objective:** explore colored mixtures and identify candidates near a target color.

**Bond result:** [Ginsburg et al., *Exploring Benchmarks for Self-Driving Labs using Color Matching*](https://arxiv.org/abs/2310.00510).

**Bench adaptation:** the paper's CMYK/camera workflow informed a locally calculated RYB screen using available stocks. Ten wells cover single-color references, binary mixtures, repeated centers, and a water blank.

**Execution evidence:** an operator-supervised run completed 94 commands across ten wells, with camera recording and controller events retained. The footage is real; delivered volumes and color accuracy were not independently measured.

<img src="assets/color-run.webp" alt="Real recorded CubOS color-mixture execution, time-compressed to 15 seconds" width="100%" />

*Recorded execution, approximately 80.8× time compression. The initial screen is not the paper's iterative optimizer.*

## The boundary that makes the integration useful

| Bond supplies | The AI proposes | Code checks | The operator establishes |
|---|---|---|---|
| Research candidates and source identity | Interpretation, possible adaptations, questions | Types, arithmetic, tip demand, configured limits, motion feasibility | Actual loading, calibration, immersion, and physical execution readiness |

Scientific fidelity and physical validity remain separate questions. Abstracts are useful for discovery; numerical methods require full-source review. Search relevance is not equipment compatibility, and a citation does not validate an adaptation.

## Live, recorded, and physical mean different things

- **Live Bond:** a new request to the connected service, with its returned sources and receipt.
- **Recorded example:** a saved real retrieval replayed for inspection; labeled as recorded.
- **Generated draft:** proposed instructions and initial loading, not an observation of live inventory.
- **Physical run:** a separately authorized CubOS execution with controller records and recorded evidence.
- **Measured scientific result:** requires an appropriate readout and independent validation; controller completion alone is insufficient.

## Try the Valency path

1. Start the app using the [setup guide](GETTING_STARTED.md).
2. Open the question-led experiment flow and select **Connect Bond**.
3. Describe the scientific objective and the resources you have.
4. Inspect the retrieved papers and the chosen method.
5. Inspect the proposed experiment, source references, recipe quantities, and unresolved requirements.
6. Generate and validate the supported protocol. Physical execution remains an operator action through CubOS.

An equipment-aware paper-selection interface is under active refinement. The demonstrated prototype supports bounded method families rather than arbitrary autonomous experimentation.

## Why this matters for scientific agents

The useful endpoint of literature search can be a testable physical proposal. Paper to Plate makes that transition inspectable: **which paper, which interpretation, which quantities, which execution, and which evidence**.

Our next step is to evaluate that chain against human-verified reference protocols and physical measurements. Bond supplies the research starting point; the evaluation will test how faithfully and reliably the rest of the system uses it.

[Valency Bond product information](https://www.valency.io/bond/) · [Project evidence and evaluation plan](EVIDENCE.md)
