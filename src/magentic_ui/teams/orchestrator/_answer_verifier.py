
import json
from autogen_core.models import SystemMessage, UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from . import _model_rotation as rotation
from ...hl_config import get as cfg

api_key = cfg("OPENAI_API_KEY")

def hl_verify_on():
    return cfg("Veri_ans")

# the prompt used by the cloud verifier
SYSTEM_PROMPT = """You are a verifier for a web-browsing agent.
Given a user task, the agent's reported answer, and evidence,The evidence include an attached screenshot.
Your goal is to check whether the reported answer addresses the given task.
You should be lenient to avoid rejecting a correct answer.
You should focus on the reported answer, not how the answer was obtained.
You should default to PASS.
You should return FAIL only when there is a clear problem with the answer, such as a factual error, a missing requested answer field, an answer to a different question, or a clear contradiction with the available evidence.
The evidence and screenshot can help you identify clear errors, but you should not return FAIL only because the evidence is missing or incomplete.
If the user task asks for a website or source name as part of the reported answer, that information must be present.
You shouldn't demand more detail or precision than the user task requests.
Return only a JSON object: {"judgment": "PASS" | "FAIL", "reason": "<one short sentence>"}."""

#Get the judeg answer and prevent the model invalid output
def parse_judge(text):
    try:
        result = json.loads(text.strip())
        judgment = str(result.get("judgment", "")).strip().upper()
    except Exception:
        return True

    if judgment == "FAIL":
        return False
    return True

# verify the answer using o3
async def hl_verify_answer(task, evidence, cancellation_token, image):
    if not cfg("Veri_ans"):
        return True
    if rotation.ws_route_on:
        print("[Verif_answer] skipped", flush=True)
        return True
    model = cfg("cloud_model")
    client = OpenAIChatCompletionClient(model=model, api_key=api_key, max_retries=2)
    user = f"TASK:\n{task}\nAGENT'S ANSWER / EVIDENCE:\n{str(evidence)[:6000]}\n Has this task been completed thoroughly?"
    user_content = [user, image]
    try:
        result = await client.create([SystemMessage(content=SYSTEM_PROMPT), UserMessage(content=user_content, source="verifier")],cancellation_token=cancellation_token,)
    finally:
        await client.close()
    rotation.log_model_trace("answer_verify", "strong", client, result)
    if parse_judge(result.content):
        print("[Verif_answer] PASS", flush=True)
        return True
    print("[Verif_answer] FAIL", flush=True)
    rotation.hl_ws_route("answer verifier: report answer fail verification")
    return False
