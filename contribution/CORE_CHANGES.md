# What this project changes in Magentic-UI 0.1.6

Eleven files differ from `magentic-ui==0.1.6`: five are new, six are upstream files
with small edits. This is the complete list — every other file in the package is
unmodified.

## New modules — `contribution/src/magentic_ui/`

| File | Lines | What it does |
|---|---:|---|
| `hl_config.py` | 31 | Every setting of the layer in one dict. `OPENAI_API_KEY` ships empty, which keeps the run fully local. |
| `teams/orchestrator/_weak_validator.py` | 190 | Checks `click`, `input_text` and `web_search` calls before they run and returns PASS / REPAIR / ESCALATE / SKIP. `hl_recover_call` rebuilds a tool call that the model wrote as text. |
| `teams/orchestrator/_model_rotation.py` | 223 | On-demand routing. Five escalation sources set one flag: orchestrator stall, orchestrator idle, WebSurfer no-op, WebSurfer loop, and a failed answer check. Cloud calls use a capped context and a step budget. |
| `teams/orchestrator/_answer_verifier.py` | 59 | A cloud judge for the answer at the last plan step. A FAIL keeps the step open and routes the WebSurfer. |
| `agents/web_surfer/_consent.py` | 41 | Clicks the first visible cookie / consent button, within a 10-second budget. |

## Patched upstream files — `contribution/patches/magentic-ui-0.1.6.patch`

| File | Lines | Changes |
|---|---|---|
| `agents/web_surfer/_web_surfer.py` | +154 −32 | See below. |
| `teams/orchestrator/_orchestrator.py` | +64 −17 | See below. |
| `tools/playwright/playwright_controller.py` | +28 −2 | Clicks the first client rectangle of a link that wraps over two lines. Select-all + delete runs only when focus is in an editable element. |
| `tools/playwright/page_script.js` | +22 −2 | An element with no accessible name falls back to `placeholder`, `name`, `alt`, `title`, or its children's `aria-label`s before its inner text, so icon controls get a usable label in the Set-of-Marks list. |
| `teams/orchestrator/_prompts.py` | +5 −1 | The `need_to_replan` guidance says to switch method after repeated grounding failures. `validate_plan_json` rejects a `steps` value that is not a list. |
| `backend/web/managers/connection.py` | +1 −1 | Skips a message-content row that is not a dict instead of failing on it. |

**`_web_surfer.py`**

* Imports the consent, validator and routing modules.
* Searches through DuckDuckGo's no-JavaScript endpoint, `html.duckduckgo.com/html/`.
* Runs the consent dismissal once per new URL and clears that state on reset.
* Executes at most one tool call per turn.
* Passes every tool call through `hl_validate_call`. PASS, REPAIR and SKIP run with the
  returned arguments; ESCALATE is refused before execution.
* Feeds the no-op monitor, and the loop monitor for every call that was not refused.
* Replaces an empty explanation, or an empty `stop_action` answer, with `"None"`.
* Keeps a page that refuses the automation script but can still be screenshotted, and
  tells the model to ask the user to solve the CAPTCHA there instead of navigating away.
* Sends every WebSurfer model call through `hl_ws_call`. When the local model is
  text-only and the call is routed, the Set-of-Marks screenshot is attached.
* Recovers a tool call written as text with `hl_recover_call`.
* A failed `history_back` points the model to `switch_tab`.
* `answer_question` attaches the page image only for a multimodal model.

**`_orchestrator.py`**

* Sends the orchestrator's JSON calls and its final-answer call through `hl_or_call`.
* Resets the routing state at the start of each run.
* Calls `hl_or_monitor` on every progress ledger.
* Holds a replan request until the stall threshold is reached, and replaces that
  round's instruction with one to continue the current step with a different action.
* At the last plan step, checks the answer with `hl_verify_answer`, with a screenshot
  attached. A FAIL keeps the step open and re-instructs the WebSurfer.
* Continues after a replan without waiting for the user to accept it, when
  `or_auto_replan` is set.
* Flattens two `else` branches in the JSON retry loop. Behaviour is unchanged.

## Applying it

```bash
pip install "magentic-ui[ollama]==0.1.6"
cd <site-packages>          # the folder that contains magentic_ui/ -- see: pip show magentic-ui
git apply --ignore-whitespace <repo>/contribution/patches/magentic-ui-0.1.6.patch
cp -r <repo>/contribution/src/magentic_ui/* magentic_ui/
```

`--ignore-whitespace` is needed on Windows, where the installed files use CRLF and the
patch uses LF.

Applying the patch to a clean 0.1.6 gives the six submitted files byte for byte
(compared with LF line endings). Reversing it with `git apply -R` gives 0.1.6 back.
