"""Deploy the worker on a public, digest-pinned PyTorch runtime.

This avoids a large local image upload. True cold starts install dependencies
and download the checkpoint; FlashBoot can retain the initialized worker.
"""
import base64
import json
import shlex
import sys

from control import ROOT, request

IMAGE = "pytorch/pytorch@sha256:dab81780fd94483b67b4b5679cc0024939b08e48540d39476d284cb29002ed69"
REVISION = "81f51e224ce9e74b02cc2a3eaf21b2d91d743455"


def configuration(config_path=None):
    from pathlib import Path
    config = json.loads(Path(config_path or ROOT / "deploy/endpoint.json").read_text())
    config["image"] = IMAGE
    config["entrypoint"] = ["/bin/bash", "-lc"]
    project = "git+https://github.com/facebookresearch/omnilingual-asr.git@" + REVISION
    script = "\n".join([
        "set -euo pipefail",
        "export DEBIAN_FRONTEND=noninteractive",
        "apt-get update",
        "apt-get install -y --no-install-recommends git libsndfile1 build-essential cmake",
        "python -m pip install --no-cache-dir torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126",
        "python -m pip install --no-cache-dir 'fairseq2[arrow]==0.6.0' --extra-index-url https://fair.pkg.atmeta.com/fairseq2/whl/pt2.8.0/cu126",
        "python -m pip install --no-cache-dir " + shlex.quote(project) + " runpod==1.8.1 soundfile==0.13.1",
        "python -m pip check",
        "exec python -u -c " + shlex.quote(
            'import base64,os; exec(compile(base64.b64decode(os.environ["ASR_HANDLER_B64"]), "handler.py", "exec"))'
        ),
    ])
    config["cmd"] = [script]
    config["env"]["ASR_HANDLER_B64"] = base64.b64encode((ROOT / "deploy/handler.py").read_bytes()).decode()
    return config


if __name__ == "__main__":
    config_path = (sys.argv[3] if len(sys.argv) > 3 else None) if sys.argv[1] == "update" else (sys.argv[2] if len(sys.argv) > 2 else None)
    config = configuration(config_path)
    if sys.argv[1] == "update":
        # Names and routing type are unchanged; PATCH accepts the relevant fields.
        config.pop("name")
        config.pop("type")
        result = request("/v2/serverless/" + sys.argv[2], config, method="PATCH")
    elif sys.argv[1] == "create":
        result = request("/v2/serverless", config)
    else:
        raise SystemExit("Usage: bootstrap.py create [CONFIG_PATH] | update ENDPOINT_ID [CONFIG_PATH]")
    print(json.dumps({k: result[k] for k in ["id", "image", "workers", "gpu"]}, indent=2))
