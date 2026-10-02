"""Verify audio upload and remote inference through the running local app."""
import argparse
import json
import os
import time
from pathlib import Path

from gradio_client import Client, handle_file

from control import ROOT, request

CTC_MODEL = "omniASR_CTC_1B_v2"
LLM_MODEL = "omniASR_LLM_7B_v2"


def endpoint_for(model):
    variable = "RUNPOD_ENDPOINT_ID" if model == CTC_MODEL else "RUNPOD_ENDPOINT_ID_7B"
    endpoint = os.getenv(variable)
    if endpoint:
        return endpoint
    state = json.loads((ROOT / "deployment-state.json").read_text(encoding="utf-8"))
    endpoint = state.get("endpoints", {}).get(model)
    if model == CTC_MODEL and not endpoint:
        endpoint = state.get("endpoint_id")
    if not endpoint:
        raise SystemExit(f"No endpoint configured for {model}; set {variable} in .env")
    return endpoint


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", help="Audio file to submit through the local Gradio app")
    parser.add_argument("preceding_job", nargs="?", help="Wait for this API job ID before testing Gradio")
    parser.add_argument("expected_phrase", nargs="?", help="Phrase expected in the returned transcript")
    parser.add_argument("--model", choices=(CTC_MODEL, LLM_MODEL), default=CTC_MODEL)
    parser.add_argument("--language", help="Optional supported language code (LLM only)")
    return parser.parse_args()


def main():
    args = parse_args()
    endpoint = endpoint_for(args.model)
    if args.preceding_job:
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            job = request(
                f"/v2/{endpoint}/status/{args.preceding_job}",
                base="https://api.runpod.ai",
            )
            if job["status"] == "COMPLETED":
                break
            if job["status"] in {"FAILED", "CANCELLED", "TIMED_OUT"}:
                raise SystemExit("Preceding API smoke job failed")
            time.sleep(2)
        else:
            raise SystemExit("Preceding API job did not complete in time")

    client = Client("http://127.0.0.1:7860", verbose=False)
    text = client.predict(
        handle_file(str(Path(args.audio).resolve())),
        args.model,
        args.language,
        api_name="/transcribe",
    )
    if not isinstance(text, str) or not text.strip():
        raise SystemExit("Gradio returned no transcript")
    if args.expected_phrase and args.expected_phrase.casefold() not in text.casefold():
        raise SystemExit("Gradio transcript did not contain the expected speech phrase")
    print("Gradio transcript:", text)


if __name__ == "__main__":
    main()
