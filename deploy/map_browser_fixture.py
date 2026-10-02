"""Run the real UI with fake external inference for unbilled browser checks.

Test-only server: localhost:7861. Never use this to assess speech accuracy.
"""
import json as jsonlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class FixtureResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


jobs = {}
endpoints = {app.endpoint_for(model): model for model in app.MODELS}


def post(url, *, headers, json, timeout):
    endpoint = url.removesuffix("/run").rsplit("/", 1)[-1]
    if endpoint not in endpoints or not url.startswith(app.BASE_URL):
        raise RuntimeError("Fixture refuses an unexpected external request")
    model = endpoints[endpoint]
    hint = json["input"].get("language")
    job_id = "fixture-" + str(len(jobs) + 1)
    jobs[job_id] = {
        "status": "COMPLETED",
        "output": {"model": model, "text": f"Browser fixture: {model}; language={hint}"},
    }
    print("fixture_submission=" + jsonlib.dumps({"model": model, "language": hint}), flush=True)
    return FixtureResponse({"id": job_id})


def get(url, *, headers, timeout):
    return FixtureResponse(jobs[url.rsplit("/", 1)[-1]])


if __name__ == "__main__":
    os.environ["RUNPOD_API_KEY"] = "browser-fixture-not-a-real-key"
    app.requests = SimpleNamespace(post=post, get=get)
    print("TEST ONLY: external inference is faked; port 7861", flush=True)
    app.create_ui().queue().launch(server_name="127.0.0.1", server_port=7861, share=False)
