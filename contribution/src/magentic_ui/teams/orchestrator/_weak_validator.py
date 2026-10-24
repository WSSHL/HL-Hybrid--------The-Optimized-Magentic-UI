import json
import re
#STATES
PASS = "PASS"
REPAIR = "REPAIR"
ESCALATE = "ESCALATE"
SKIP = "SKIP"
#function be called outsite this pyfile statr with "hl_" 

# normalize integer, numeric string and nested id to integer
def normalize_id(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str):          
        s = value.strip()
        if s.lstrip("-").isdigit():
            return int(s)
        return None
    if isinstance(value, dict):         
        for k in ("id", "target_id", "input_field_id", "element_id", "value"):
            if k in value:
                inner = normalize_id(value[k])
                if inner is not None:
                    return inner
                
    return None

#validate and repair 3 kinds of tool call send them to separator small checker
def hl_validate_call( tool_name, toolargs):
    if tool_name == "input_text":
        return check_input_text(toolargs)
    if tool_name == "click":
        return check_click(toolargs)
    if tool_name == "web_search":
        return check_web_search(toolargs)
    return SKIP, dict(toolargs), ""

#give the default explanation if origion explaination is none
def default_explanation(toolargs, default):
    expl = toolargs.get("explanation")
    return expl if isinstance(expl, str) and expl.strip() else default


# validate and normalize a input text tool call the, deterministic appiled
def check_input_text(toolargs):
    normalised_args = dict(toolargs)
    normalised_args["explanation"] = default_explanation(toolargs, "type text into field")
    for old_name in ("target_id", "target", "element_id", "id"):
        if (normalised_args.get("input_field_id") is None and normalised_args.get(old_name) is not None):
            normalised_args["input_field_id"] = normalised_args[old_name]
        normalised_args.pop(old_name, None)
    field_id = normalize_id(normalised_args.get("input_field_id"))
    if field_id is None:
        return ESCALATE, dict(toolargs), "input_text missing or invalid input_field_id"
    normalised_args["input_field_id"] = field_id
    for old_name in ("text", "value"):
        if (normalised_args.get("text_value") is None and normalised_args.get(old_name) is not None ):
            normalised_args["text_value"] = normalised_args[old_name]
        normalised_args.pop(old_name, None)
    if "text_value" not in normalised_args:
        return ESCALATE, dict(toolargs), "input_text missing text_value"
 
    text_val = normalised_args["text_value"]
    if not isinstance(text_val, str):
        text_val = str(text_val)
    normalised_args["text_value"] = text_val
    if text_val == "" and not toolargs.get("press_enter", True):
        return ESCALATE, dict(toolargs), "input_text text_value is empty"
    state = PASS if normalised_args == toolargs else REPAIR
    return state, normalised_args, ""



# validate and normalize a click tool call, deterministic appiled
def check_click(toolargs):
    normalised_args = dict(toolargs)
    normalised_args["explanation"] = default_explanation(toolargs, "click target")
    for old_name in ("target", "id", "element_id"):
        if (normalised_args.get("target_id") is None and normalised_args.get(old_name) is not None):
            normalised_args["target_id"] = normalised_args[old_name]
        normalised_args.pop(old_name, None)
    target_id = normalize_id(normalised_args.get("target_id"))
    if target_id is None:
        return ESCALATE, dict(toolargs), "click missing or invalid target_id"
    normalised_args["target_id"] = target_id
    state = PASS if normalised_args == toolargs else REPAIR
    return state, normalised_args, ""


#unnest the query from nested argument
def unnest_first_query(items):
    if not isinstance(items, (list, tuple)):
        return None
    for item in items:
        if isinstance(item, str) and item.strip():
            return item.strip()
        
        if isinstance(item, dict):
            for k in ("query", "q", "text", "search_query"):
                v = item.get(k)

                if isinstance(v, str) and v.strip():
                    return v.strip()            
    return None


# validate and normalize a websearch tool call, deterministic appiled
def check_web_search(toolargs):
    normalised_args = {}
    expl = toolargs.get("explanation")
    if isinstance(expl, str) and expl.strip():
        normalised_args["explanation"] = expl
    query = None
    for k in ("query", "text"):
        v = toolargs.get(k)
        if v is None:
            continue
        if isinstance(v, str) and v.strip():
            query = v.strip()
        elif isinstance(v, (list, tuple)):
            query = unnest_first_query(v)
        elif isinstance(v, dict):
            query = unnest_first_query([v])
        if query:
            break
    if not isinstance(query, str) or not query.strip():
        return ESCALATE, dict(toolargs), "web_search missing query"
    normalised_args["query"] = query.strip()
    state = PASS if normalised_args == toolargs else REPAIR
    return state, normalised_args, ""



#find and decoded json object hide in the text
def iter_json_objects(text):
    decoder = json.JSONDecoder()
    found = []
    pos = 0
    while pos < len(text):
        pos = text.find("{", pos)
        if pos == -1:
            break
        try:
            obj, consumed = decoder.raw_decode(text[pos:])
            found.append((obj, pos))
            pos += consumed
        except json.JSONDecodeError:
            pos += 1
    return found
NAME_KEYS = ("name", "tool_name", "tool", "action")
PAREN_PREFIX_RE = re.compile(r"([A-Za-z_]\w*)\s*\(\s*$")



# recover a valid tool name and its argument from model text
def hl_recover_call(text, tool_names):
    if "{" not in text:
        return None
    best = None
    for obj, pos in iter_json_objects(text):
        if not isinstance(obj, dict):
            continue
        name = None
        for k in NAME_KEYS:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                name = v.strip()
                break

        if name is None:
            m = PAREN_PREFIX_RE.search(text[:pos])
            name = m.group(1) if m else None

        if name not in tool_names:
            continue
        toolargs = obj.get("arguments")

        if not isinstance(toolargs, dict):
            toolargs = obj.get("tool_args")

        if isinstance(toolargs, dict):
            toolargs = dict(toolargs)
        else:
            toolargs = {k: v for k, v in obj.items() if k not in NAME_KEYS}


        if isinstance(obj.get("explanation"), str) and "explanation" not in toolargs:
            toolargs["explanation"] = obj["explanation"]
        best = (name, toolargs)
    return best
