"""Real 7B speech check, preserving job ID across local waiting deadlines."""
import base64
import json
import sys
import time
from pathlib import Path

from control import ROOT, request

MODEL = "omniASR_LLM_7B_v2"
state = json.loads((ROOT / "deployment-state.json").read_text())
prefix = "/v2/" + state["endpoints"][MODEL]
payload = {"audio_base64": base64.b64encode(Path(sys.argv[1]).read_bytes()).decode(),
           "language": "eng_Latn"}
job = request(prefix + "/run", {"input": payload}, base="https://api.runpod.ai")
print("Submitted", job["id"], flush=True)
deadline = time.monotonic() + 1200
previous = None
while time.monotonic() < deadline:
    result = request(prefix + "/status/" + job["id"], base="https://api.runpod.ai")
    if result["status"] != previous:
        print(result["status"], flush=True)
        previous = result["status"]
    if result["status"] == "COMPLETED":
        print(json.dumps(result, indent=2), flush=True)
        output = result["output"]
        if output.get("model") != MODEL or "fellow americans" not in output.get("text", "").casefold():
            raise SystemExit("Wrong model or unrecognizable speech")
        break
    if result["status"] in {"FAILED", "CANCELLED", "TIMED_OUT"}:
        raise SystemExit(json.dumps(result))
    time.sleep(5)
else:
    raise SystemExit("Polling deadline exceeded; preserve job ID and inspect status, do not resubmit")
