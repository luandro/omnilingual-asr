"""Submit a WAV/FLAC file, poll the deployed endpoint, and print its result."""
import base64
import json
from pathlib import Path
import sys
import time

from control import request

state = json.loads(Path("deployment-state.json").read_text())
prefix = "/v2/" + state["endpoint_id"]
audio = Path(sys.argv[1]).read_bytes()
job = request(prefix + "/run", {"input": {
    "audio_base64": base64.b64encode(audio).decode(),
}}, base="https://api.runpod.ai")
print("Submitted", job["id"], flush=True)
deadline = time.monotonic() + 1200
previous = None
while time.monotonic() < deadline:
    result = request(prefix + "/status/" + job["id"], base="https://api.runpod.ai")
    if result["status"] != previous:
        print(result["status"], flush=True)
        previous = result["status"]
    if result["status"] == "COMPLETED":
        print(json.dumps(result, indent=2))
        if not result.get("output", {}).get("text", "").strip():
            raise SystemExit("No transcript returned")
        if len(sys.argv) > 2 and sys.argv[2].casefold() not in result["output"]["text"].casefold():
            raise SystemExit("Transcript did not contain the expected speech phrase")
        break
    if result["status"] in {"FAILED", "CANCELLED", "TIMED_OUT"}:
        raise SystemExit(json.dumps(result))
    time.sleep(5)
else:
    raise SystemExit("Polling deadline exceeded; job may still be running")
