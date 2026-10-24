import json
import time
from collections import deque
from autogen_core.models import UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from ...hl_config import get as cfg
#function be called outsite this pyfile statr with "hl_" 
#functin contains "ws_" means it is for websurfer, "or_" means it is for orchestrator,
#variable start with "ws_" means it is for websurfer, "or_" means it is for orchestrator, 
cloud_model = cfg("cloud_model")
or_stall_limit = cfg("or_stall_limit")
or_idle_limit = cfg("or_idle_limit")
context_cap = cfg("context_cap")
ws_stuck_route_or = cfg("ws_stuck_route_or")
ws_noop_limit = cfg("ws_noop_limit")
ws_base_steps = cfg("ws_base_steps")
ws_extra_steps = cfg("ws_extra_steps")
or_auto_replan = cfg("or_auto_replan")
ws_loop_window = cfg("ws_loop_window")
ws_loop_distinct = cfg("ws_loop_distinct")
Trace_log = cfg("TRACE_LOG")
ws_route_on = False
or_force_pending = False
ws_reroute_count = 0
ws_step_count = 0
ws_reroute_prompt = None
counts = {}
counts["or_stalls"] = 0
counts["or_idle"] = 0
counts["ws_noops"] = 0
or_route_pending = False
ws_loop_history = deque(maxlen=ws_loop_window)
ws_som_image = None
api_key = cfg("OPENAI_API_KEY")
#reset or initialize the routing state, called once per task. 
def hl_or_reset_routing():
    global ws_route_on, ws_reroute_count, ws_step_count, ws_reroute_prompt, or_force_pending, or_route_pending, ws_som_image
    ws_route_on = False
    ws_reroute_count = 0
    ws_step_count = 0
    ws_reroute_prompt = None
    or_force_pending = False
    or_route_pending = False
    ws_som_image = None
    counts["or_stalls"] = 0
    counts["or_idle"] = 0
    counts["ws_noops"] = 0
    ws_loop_history.clear()
    append_trace("new task " + time.strftime("%Y-%m-%d %H:%M:%S"))

#the trigger for the ws route, if ws is already using the cloud model, then ws_reroute_count + 1, and set ws_reroute_prompt to the reason, when stroung model meet some barries it can see the prompt.
def hl_ws_route(reason):
    global ws_route_on, ws_reroute_count, ws_reroute_prompt, or_force_pending
    if ws_route_on:
        ws_reroute_count += 1
        ws_reroute_prompt = f"""Reroute #{ws_reroute_count}: no progress was detected again. Reason: {reason}.
You are already the strongest available model, so there's no further model to escalate to.
you need to change your strategy now: you can use a different tool or meethod, such as a targeted search or a direct URL. If you can't continue go further, explain exactly what is stucking you.]"""
        every = ws_stuck_route_or
        if every and ws_reroute_count % every == 0:
            or_force_pending = True
            trace_event(f"[MODEL_ROTATION]orchestrator reroute #{ws_reroute_count}")
        return
    ws_route_on = True
    trace_event(f"[MODEL_ROTATION] websurfer route ({reason})")


#set the orchestrator route true, and if it route, the websurfer will also route to the cloud model.
def or_route(reason):
    global or_route_pending
    or_route_pending = True
    hl_ws_route(reason)

# A counter can check its own count in counts,return true if the count reaches threshold, and reset the count to 0,otherwise return false
def counter(name, threshold):
    counts[name] += 1
    if counts[name] >= threshold:
        counts[name] = 0
        return True
    return False

#the monitor for orchestrator, if the orchestrator is stuck, then route the orchestrator and webserfer to the cloud model.
def hl_or_monitor(progress_ledger):
    if progress_ledger["need_to_replan"]["answer"] is True:
        counts["or_idle"] = 0
        if counter("or_stalls", or_stall_limit):
            or_route("stall: repeat replan")
        return
    counts["or_stalls"] = 0
    if progress_ledger["is_current_step_complete"]["answer"] is True:
        counts["or_idle"] = 0
        return
    if counter("or_idle", or_idle_limit):
        or_route("idle: step not complete")

#the monitor to monitor the nooperation of the websurfer
def hl_ws_noop_monitor(produced_action):
    if produced_action:
        counts["ws_noops"] = 0
        return
    if counter("ws_noops", ws_noop_limit):
        hl_ws_route("no-op: no action ")


#the monitor to monitor the loop of the websurfer 
def hl_ws_loop_monitor(tool_name, args):
    ws_loop_history.append(ws_loop_signature(tool_name, args))
    w = ws_loop_window
    if len(ws_loop_history) >= w and len(set(ws_loop_history)) <= ws_loop_distinct:
        evidence = sorted(set(ws_loop_history))
        trace_event("[Loop_break] stuck")
        hl_ws_route(f"found repeat actions: {evidence}")
        ws_loop_history.clear()
        return True
    return False

#get the signature of the tool call
def ws_loop_signature(tool_name, args):
    rest = {k: v for k, v in args.items() if k != "explanation"}
    body = json.dumps(rest, sort_keys=True, ensure_ascii=False, default=str)
    return f"{tool_name}({body})"


#cap the latest context_cap massage and the first massage, if the massage length is larger than context_cap
def cap_msgs(messages):
    cap = context_cap
    n = len(messages)
    if n <= cap + 1:
        return messages
    capmsg = list(messages[:1]) + list(messages[-cap:])
    return capmsg

#create a cloud client
def cloud_client(model):
    return OpenAIChatCompletionClient(model=model, api_key=api_key, max_retries=2)

#Call the local modle
async def local_call(local_client, component, mode, messages, create_kwargs):
    response = await local_client.create(messages, **create_kwargs)
    log_model_trace(component, mode, local_client, response)
    return response

#the call to the orchestrator 
async def hl_or_call(agent,messages,**create_kwargs,):
    global or_route_pending, or_force_pending
    local_client = agent._model_client

    or_forced = or_force_pending
    or_force_pending = False
    or_routing = or_forced or or_route_pending
    if not or_routing:
        return await local_call(local_client, "orchestrator", "configured", messages, create_kwargs)

    or_route_pending = False
    model = cloud_model
    strong_client = cloud_client(model)

    try:
        capped = cap_msgs(messages)
        response = await strong_client.create(capped, **create_kwargs)
        log_model_trace("orchestrator", "one-shot-strong", strong_client, response)
        return response
    finally:
        await strong_client.close()


#the model call to the websurfer
async def hl_ws_call(agent,messages,**create_kwargs,):
    global ws_reroute_prompt
    local_client = agent._model_client
    if not ws_route_on:
        return await local_call(local_client, "websurfer", "configured", messages, create_kwargs)

    global ws_step_count, ws_som_image
    budget = ws_base_steps + ws_extra_steps * ws_reroute_count
    if ws_step_count >= budget:
        return await local_call(local_client, "websurfer", "budget-exhausted", messages, create_kwargs)
    ws_step_count += 1
    model = cloud_model
    strong_client = cloud_client(model)

    strong_kwargs = dict(create_kwargs)
    if strong_kwargs.get("tools"):
        extra = dict(strong_kwargs.get("extra_create_args") or {})
        extra.setdefault("tool_choice", "required")
        strong_kwargs["extra_create_args"] = extra

    try:
        capped = cap_msgs(messages)
        if ws_reroute_prompt:
            note = UserMessage(content=ws_reroute_prompt, source="escalation_notice")
            capped =  [capped[0], note] + list(capped[1:])
            ws_reroute_prompt = None
        if ws_som_image is not None:
            last_message = capped[-1]
            new_last_message = type(last_message)(
                content=[last_message.content, ws_som_image],
                source=last_message.source,
            )
            capped = list(capped[:-1]) + [new_last_message]
            ws_som_image = None
        response = await strong_client.create(capped, **strong_kwargs)
        log_model_trace("websurfer", "strong", strong_client, response)
        return response
    finally:
        await strong_client.close()



# log trace
def append_trace(text):
    with open(Trace_log, "a", encoding="utf-8") as f:
        f.write(text + "\n")
def trace_event(line):
    print(line)
    append_trace(time.strftime("%Y-%m-%d %H:%M:%S") + " " + line)
def log_model_trace(component, mode, client, response):
    model = client._create_args["model"]
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens
    log_msg = f"[MODEL_TRACE] component={component} | mode={mode} | model={model} | prompt_tokens={prompt_tokens} | completion_tokens={completion_tokens}"
    trace_event(log_msg)

