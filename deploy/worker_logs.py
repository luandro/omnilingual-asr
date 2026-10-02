"""Read a small worker-log snapshot without exposing the configured API key."""
import json
import os
import sys
import time

import requests
import control  # Loads local credentials without printing them.

url = f"https://api.runpod.io/v2/serverless/{sys.argv[1]}/workers/{sys.argv[2]}/logs"
key = os.environ["RUNPOD_API_KEY"]
deadline = time.monotonic() + 10
count = 0
try:
    with requests.get(url, headers={"Authorization": "Bearer " + key},
                      params={"source": "container", "tail": 12},
                      stream=True, timeout=(10, 3)) as response:
        response.raise_for_status()
        response.encoding = "utf-8"
        for line in response.iter_lines(chunk_size=1024, decode_unicode=True):
            if time.monotonic() > deadline:
                break
            if line.startswith("data:"):
                entry = json.loads(line[5:])
                text = entry.get("line", "").replace(key, "[REDACTED]").rsplit("\r", 1)[-1]
                print(text[:700])
                count += 1
                if count >= 12:
                    break
except requests.RequestException as exc:
    print("Log snapshot ended:", str(exc).replace(key, "[REDACTED]")[:300])
