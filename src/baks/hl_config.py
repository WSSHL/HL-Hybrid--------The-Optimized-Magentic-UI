import os

current_dir = os.path.dirname(os.path.abspath(__file__))

config = {
    # SECRET -- set to "" before sharing this package. Empty means no cloud call
    # is ever made and the run stays fully local.
    "OPENAI_API_KEY": "",
    # routing
    "cloud_model": "o3",
    "or_stall_limit": 2,       
    "or_idle_limit": 5,             
    "context_cap": 12,          
    "ws_stuck_route_or": 2,
    "ws_noop_limit": 2,
    "ws_base_steps": 20,
    "ws_extra_steps": 15,
    "or_auto_replan": True,
    # answer verifier 
    "Veri_ans": True,
    # loop breaker
    "ws_loop_window": 4,
    "ws_loop_distinct": 2,
    "TRACE_LOG": os.path.join(current_dir, "model_trace.log"),
}

def get(name):
    return config[name]



