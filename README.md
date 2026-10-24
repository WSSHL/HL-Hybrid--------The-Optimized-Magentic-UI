# The-Optimized-Magentic-UI with Reliability layers for a local-LLM Magentic-UI web agent

A weak-validation + on-demand model-routing layer that lets the
[Magentic-UI](https://github.com/microsoft/magentic-ui) multi-agent web agent run on a
**local small model** (Qwen3 14B with thinking disabled, via Ollama) and borrow a cloud
model (o3) only when the local model is stuck.

> KCL Final Year Project · Author: **Haolun Shan** · Final submission, August 2026

![Accuracy against cost per task](docs/cost_vs_accuracy.png)

**HL-Hybrid** — the local model with this layer, borrowing o3 only when stuck — reaches
90% accuracy against o3's 91%, at 5.39× lower cost per task.

---

## Motivation

Magentic-UI (Microsoft's open-source implementation of *Magentic-One*) assumes the
backing LLM always emits **well-formed** output: structurally valid plan / progress
ledger JSON and tool-call arguments that match the executor's signature. When the
backend is swapped for a **local small model**, that assumption breaks —
mislabeled fields, a tool call written as prose, an empty plan — and the agent crashes
or spins.

This project adds a thin, mostly-**deterministic** layer on top of Magentic-UI that
catches and repairs these defects locally, and only borrows a strong cloud model when
the local model is genuinely stuck.

## Design principle

**Free-and-deterministic first, paid-and-stochastic last.**

| Mechanism | When | Cloud? | Handles |
|---|---|---|---|
| **Weak Validator** | before a tool call runs | No · deterministic | field-name drift, id coercion, a call written as prose; PASS / REPAIR / ESCALATE / SKIP, and an ESCALATE call is refused |
| **Consent Dismissal** | first visit to each URL | No · deterministic | cookie / consent banners that hide the elements the model needs; 10-second budget |
| **Text Fallback** | an explanation or answer is empty | No · deterministic | a default string instead of a blank |
| **Answer Verifier** | the last plan step claims completion | Yes · judge | a cloud judge checks the answer; a FAIL keeps the step open and routes the WebSurfer |
| **Model Routing** | sustained no-progress | Yes · decision | borrow o3 to re-decide; five escalation sources, one routing flag |

**Removed 2026-07-29.** Three mechanisms were dropped after measurement, because this
project only keeps a rule that a frequently observed error earns: an execution rescue
(reached 21 times, repaired 0), a cloud JSON rescue (never reached in 198 runs) and a
cloud text rescue (never reached in 109 opportunities). What replaced the last one is a
single default string, which covered all 64 of its real cases at zero cost.

## The weak validator in one idea

It does not enumerate "all the ways output can be wrong". It **rebuilds the output into
a single canonical form**, and the rebuild itself *is* the verdict:

```python
state = PASS if normalised_args == toolargs else REPAIR   # unchanged -> PASS, repaired -> REPAIR
# a required field that cannot be normalised (normalize_id -> None) -> ESCALATE
```

Examples (a click's `target_id`): `6` → PASS · `{"id":29}` / `"29"` → REPAIR ·
`[17,21]` / `"the blue button"` / missing → ESCALATE.

## Repository layout

```
contribution/
  src/magentic_ui/                 # NEW modules -- original work
    hl_config.py                   # every setting of this layer, in one dict
    teams/orchestrator/
      _weak_validator.py           # PASS/REPAIR/ESCALATE/SKIP; recovers a call written as text
      _model_rotation.py           # on-demand routing: five escalation sources, one flag
      _answer_verifier.py          # judges the final answer; a FAIL is a routing signal
    agents/web_surfer/
      _consent.py                  # cookie / consent banner dismissal, with a time budget
  patches/
    magentic-ui-0.1.6.patch        # the edits to six Magentic-UI files
  CORE_CHANGES.md                  # what each of the eleven changed files does
  eval_config.yaml                 # model config for the CLI runs
  qwen3-nothink.Modelfile          # builds qwen3-nothink from qwen3:14b
docs/
  FYP_report_stage5.pdf            # interim (stage 5) report, in Chinese
  HAOLUNSHAN_1908837_YALIDU_SupplementalFile_2025-26.zip   # the code package as submitted
LICENSE-magentic-ui                # Magentic-UI's MIT licence
NOTICE                             # attribution
```

The final report is not included in this repository.

## How to run

Requirements: Docker running, Anaconda, an NVIDIA GPU with 16 GB of VRAM (slower without).

```bash
conda create -n mgui python=3.12 -y
conda activate mgui
pip install "magentic-ui[ollama]==0.1.6"
playwright install chromium
```

Install the layer into the package, either way:

* replace the installed `magentic_ui/` folder with `src/magentic_ui/` from the zip in
  `docs/`, or
* apply the patch and copy the modules, as in
  [`contribution/CORE_CHANGES.md`](contribution/CORE_CHANGES.md).

`pip show magentic-ui` gives the install location.

Put your OpenAI API key in `magentic_ui/hl_config.py`, in the `OPENAI_API_KEY` field.

Start Ollama and build the no-thinking model:

```bash
docker run -d --gpus all -v ollama:/root/.ollama -p 11434:11434 --name ollama -e OLLAMA_FLASH_ATTENTION=1 -e OLLAMA_KV_CACHE_TYPE=q8_0 -e OLLAMA_CONTEXT_LENGTH=32768 ollama/ollama
docker exec ollama ollama pull qwen3:14b
docker cp contribution/qwen3-nothink.Modelfile ollama:/tmp/m
docker exec ollama ollama create qwen3-nothink -f /tmp/m
```

Run the web UI with `magentic-ui --port 8081`, then under Settings → Advanced settings
set the model to `qwen3-nothink` and `vision` to `false`.

Or run one task from the command line (PowerShell), with `eval_config.yaml` in the
current folder:

```powershell
$env:PYTHONIOENCODING="utf-8"
$task = "Please use Google Maps to check How long does it take to walk from King's College London's Strand Campus to Big Ben? (Answer Precise to minute)."
magentic-cli --work-dir ".\work_1" --config eval_config.yaml --autonomous --action-policy never --old-cli --task $task *> "run_1.log"
```

`--action-policy never` auto-approves every action, which turns off Magentic-UI's action
guard. `--autonomous` removes the user from the team, so a CAPTCHA cannot be handed off
during such a run.

## Configuration — `magentic_ui/hl_config.py`

| Key | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | `""` | used by routing and the answer verifier. Neither checks for an empty key, so with it empty they still attempt the cloud call. |
| `cloud_model` | `o3` | the model borrowed by routing and used by the answer verifier |
| `or_stall_limit` | 2 | repeated replan requests before the orchestrator is routed |
| `or_idle_limit` | 5 | rounds with the step still incomplete before the orchestrator is routed |
| `context_cap` | 12 | a routed call sees the first message plus the last 12 |
| `ws_stuck_route_or` | 2 | WebSurfer re-escalations that also route the orchestrator |
| `ws_noop_limit` | 2 | WebSurfer turns without an executable action before routing |
| `ws_base_steps` | 20 | cloud steps the WebSurfer may take once routed |
| `ws_extra_steps` | 15 | extra cloud steps per re-escalation |
| `or_auto_replan` | `True` | continue after a replan without waiting for the user to accept it |
| `Veri_ans` | `True` | turn the answer verifier on or off |
| `ws_loop_window` | 4 | recent WebSurfer actions the loop monitor looks at |
| `ws_loop_distinct` | 2 | at most this many distinct actions in the window counts as a loop |
| `TRACE_LOG` | next to `hl_config.py` | where `[MODEL_TRACE]` lines are appended |

## Attribution

Built on [Magentic-UI](https://github.com/microsoft/magentic-ui) by Microsoft (MIT). The
modules under `contribution/src/` are original work for a KCL FYP. See `NOTICE`.
