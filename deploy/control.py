"""Runpod management helper; reads .env without printing credentials."""
import json
import os
from pathlib import Path
import shlex
import sys
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
for line in (ROOT / ".env").read_text().splitlines():
    if line.strip() and not line.lstrip().startswith("#") and "=" in line:
        key, value = line.removeprefix("export ").split("=", 1)
        parts = shlex.split(value, comments=True)
        os.environ.setdefault(key.strip(), parts[0] if parts else "")


def request(path, data=None, base="https://api.runpod.io", method=None):
    req = urllib.request.Request(base + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": "Bearer " + os.environ["RUNPOD_API_KEY"], "Content-Type": "application/json", "User-Agent": "omnilingual-asr-deployer/1.0"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Runpod HTTP {exc.code}: {exc.read().decode()}") from None


if __name__ == "__main__":
    if sys.argv[1] == "catalog":
        print(json.dumps(request("/v2/catalog/gpus?include=AVAILABILITY&product=SERVERLESS"), indent=2))
    elif sys.argv[1] == "list":
        print(json.dumps(request("/v2/serverless"), indent=2))
    elif sys.argv[1] == "create":
        print(json.dumps(request("/v2/serverless", json.loads(Path(sys.argv[2]).read_text())), indent=2))
    elif sys.argv[1] == "get":
        print(json.dumps(request("/v2/serverless/" + sys.argv[2]), indent=2))
