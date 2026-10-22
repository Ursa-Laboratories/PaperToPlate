# Get from checkout to your first draft

[← Documentation](README.md) · [Demo guide](DEMO.md) · [Valency Bond](VALENCY_BOND.md)

You can inspect Paper to Plate without connecting a robot. Add model access for generation, Bond for live literature, and a compatible CubOS installation for native validation and an operator-controlled physical run.

## 1. Install the local workbench

Use Python **3.11 or newer** and a Node.js version compatible with Vite 7 (Node **20.19+ or 22.12+**).

```bash
git clone https://github.com/Ursa-Laboratories/PaperToPlate.git
cd PaperToPlate
./setup.sh
```

The setup script creates this repository's `.venv`, installs the Python dependencies, installs the frontend dependencies, and builds the UI. Keep dependencies in this project's environments.

## 2. Configure the backend

On a fresh checkout:

```bash
cp .env.example .env
```

If `.env` already exists, edit it instead of replacing it.

```dotenv
OLLAMA_API_KEY=your_ollama_key
OLLAMA_URL=https://ollama.com
OLLAMA_MODEL=gpt-oss:120b

# Absolute path to an interpreter with a compatible installed cubos package.
CUBOS_VALIDATOR_PYTHON=/absolute/path/to/cubos-environment/bin/python

# Your authorized operator station or existing local tunnel.
CUBOS_API_URL=http://localhost:8742
PAPER_TO_PLATE_PORT=8785
```

`CUBOS_API_TOKEN` is optional when the station requires authentication. Never place these keys in frontend variables. `.env`, runtime data, and Bond tokens are ignored by Git.

The shipped default uses Ollama Cloud; an OpenAI key is not required. For an existing local Ollama service, set its URL and an installed model. Model availability and account limits depend on your provider account. Missing credentials and provider failures remain visible.

## 3. Start the app

```bash
./start.sh
```

Open **http://127.0.0.1:8785/**. Keep the server running during generation. Restart it after editing `.env`.

| What you want | What you need |
|---|---|
| Inspect bundled reference drafts | Local app only |
| Generate from an uploaded paper | Configured model service |
| Search the literature live | **Connect Bond** and complete Valency sign-in |
| Validate a native protocol | Compatible installed CubOS package via `CUBOS_VALIDATOR_PYTHON` |
| Operate a physical station | Commissioned station, correct configuration, and operator-confirmed loading |

## 4. Try a source or a question

**Start from a paper:** upload a PDF, text file, or Markdown method excerpt; state the objective and select a lab setup. The app extracts source text with page provenance and generates a draft.

**Start from a question:** describe the experiment, search through Bond, and inspect the literature-backed proposal. Supported design families have deterministic recipe generation. Broader goals remain research briefs until a method can be reviewed and supported.

**Recorded examples:** these replay saved real retrievals. They are explicitly labeled and do not require a fresh Bond call. They are useful for examining the interface, not for claiming a new search occurred.

The question-to-paper-selection interface is being refined alongside the demonstrated workcell prototype. Labels and entry points may change; the underlying source, design, validation, and operator boundaries remain the same.

## 5. Inspect before execution

Check the selected source, proposed adaptations, stock instructions, source/destination locations, volume calculations, tip allocation, and native validation. Physical calibration and actual liquid immersion require an operator at the station.

Use the CubOS operator interface for live robot control. Do not replay an interrupted protocol or reset live inventory from a draft's proposed initial state without reconciliation.

## Troubleshooting

<details>
<summary><strong>The app says model setup is needed</strong></summary>

Confirm the backend `.env` contains the provider key, then restart the app. The status indicator checks configuration; a successful request establishes actual account/model access. No key belongs in the browser.

</details>

<details>
<summary><strong>Bond sign-in expired or live search failed</strong></summary>

Use **Connect Bond** again. The app uses its own OAuth session and refresh token. It does not extract another application's credentials. Access tokens are stored locally with owner-only permissions under the ignored data directory. A recorded example stays labeled recorded.

</details>

<details>
<summary><strong>Native validation is unavailable</strong></summary>

Set `CUBOS_VALIDATOR_PYTHON` to a Python interpreter that imports a compatible installed `cubos` package. The supplied routing configuration requires a runtime that supports it. Do not substitute source-path or `PYTHONPATH` hacks. Draft inspection remains available while native validation is unavailable.

</details>

<details>
<summary><strong>The PDF has little or no extracted text</strong></summary>

Image-only PDFs need OCR or an accompanying text version. Figures, tables, supplements, and omitted source pages require explicit review. Discovery metadata or an abstract does not replace full methods.

</details>

## Developer checks

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend run build
```

Optional vision dependencies and models live in the dedicated vision environment. Follow [Vision setup](vision/README.md) before running ML-specific checks.
