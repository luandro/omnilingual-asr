import ast
import base64
import json
import os
import time
from pathlib import Path

import gradio as gr
import requests
from dotenv import load_dotenv
from language_map import (
    CATALOG_PATH,
    MAP_CSS,
    MAP_JS,
    LLM_SUBMIT_JS,
    language_selection_event,
    render_language_map,
)

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "deployment-state.json"
LANG_IDS_PATH = ROOT / "src/omnilingual_asr/models/wav2vec2_llama/lang_ids.py"
CTC_MODEL = "omniASR_CTC_1B_v2"
LLM_MODEL = "omniASR_LLM_7B_v2"
MODELS = (CTC_MODEL, LLM_MODEL)
BASE_URL = "https://api.runpod.ai/v2/"

load_dotenv(ROOT / ".env")


def load_supported_languages():
    """Read the source's literal language list without importing model packages."""
    module = ast.parse(LANG_IDS_PATH.read_text(encoding="utf-8"))
    for statement in module.body:
        if isinstance(statement, ast.AnnAssign) and getattr(statement.target, "id", None) == "supported_langs":
            languages = ast.literal_eval(statement.value)
            if isinstance(languages, list) and all(isinstance(code, str) for code in languages):
                return languages
        if isinstance(statement, ast.Assign) and any(
            getattr(target, "id", None) == "supported_langs" for target in statement.targets
        ):
            languages = ast.literal_eval(statement.value)
            if isinstance(languages, list) and all(isinstance(code, str) for code in languages):
                return languages
    raise RuntimeError(f"Could not find a literal supported_langs list in {LANG_IDS_PATH}")


SUPPORTED_LANGUAGES = load_supported_languages()
LANGUAGE_CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
CATALOG_TOKENS = {entry["model_token"] for entry in LANGUAGE_CATALOG}
if CATALOG_TOKENS != set(SUPPORTED_LANGUAGES):
    raise RuntimeError("Local language catalog does not match the supported model allowlist")


def endpoint_for(model):
    if model not in MODELS:
        raise gr.Error(f"Unknown model: {model}")

    override = os.getenv("RUNPOD_ENDPOINT_ID" if model == CTC_MODEL else "RUNPOD_ENDPOINT_ID_7B")
    if override and override.strip():
        return override.strip()

    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise gr.Error(f"Cannot read {STATE_PATH.name}; configure the selected endpoint in .env") from exc

    endpoint = state.get("endpoints", {}).get(model)
    if model == CTC_MODEL and not endpoint:
        endpoint = state.get("endpoint_id")
    if not isinstance(endpoint, str) or not endpoint.strip():
        variable = "RUNPOD_ENDPOINT_ID" if model == CTC_MODEL else "RUNPOD_ENDPOINT_ID_7B"
        raise gr.Error(
            f"No Runpod endpoint is configured for {model}. Set {variable} in .env "
            "or add this model to deployment-state.json."
        )
    return endpoint.strip()


def transcribe(path, model=CTC_MODEL, language=None):
    if not path:
        raise gr.Error("Upload or record audio first")
    if model not in MODELS:
        raise gr.Error(f"Unknown model: {model}")

    endpoint_id = endpoint_for(model)
    audio = Path(path).read_bytes()
    if len(audio) > 6_000_000:
        raise gr.Error("Audio exceeds 6 MB; use a shorter recording")

    input_data = {"audio_base64": base64.b64encode(audio).decode("ascii")}
    if model == LLM_MODEL and language:
        if language not in SUPPORTED_LANGUAGES:
            raise gr.Error(f"Unsupported language code: {language}")
        input_data["language"] = language

    api_key = os.getenv("RUNPOD_API_KEY")
    if not api_key:
        raise gr.Error("Set RUNPOD_API_KEY in the local .env file")
    headers = {"Authorization": "Bearer " + api_key}
    base = BASE_URL + endpoint_id
    response = requests.post(base + "/run", headers=headers, json={"input": input_data}, timeout=60)
    response.raise_for_status()
    job_id = response.json()["id"]
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        response = requests.get(base + "/status/" + job_id, headers=headers, timeout=60)
        response.raise_for_status()
        job = response.json()
        if job["status"] == "COMPLETED":
            output = job.get("output") or {}
            actual_model = output.get("model")
            if actual_model != model:
                raise gr.Error(
                    f"Runpod returned model identity {actual_model!r}; expected {model!r}. "
                    "Check the selected endpoint configuration."
                )
            return output["text"]
        if job["status"] in {"FAILED", "CANCELLED", "TIMED_OUT"}:
            raise gr.Error(job.get("error", job["status"]))
        time.sleep(2)
    raise gr.Error("Waiting timed out. Job ID: " + job_id)


def _transcribe_ctc(path):
    return transcribe(path, model=CTC_MODEL)


def _transcribe_llm(path, language):
    return transcribe(path, model=LLM_MODEL, language=language)


def _select_language(event: gr.EventData):
    return language_selection_event(event, LANGUAGE_CATALOG)


def _select_ctc_tab(event: gr.SelectData):
    return CTC_MODEL


def _select_llm_tab(event: gr.SelectData):
    return LLM_MODEL


def create_ui():
    with gr.Blocks(title="Omnilingual ASR") as demo:
        gr.Markdown(
            "# Omnilingual ASR\n"
            "Transcribe audio with the local Runpod endpoints. Long audio is split into 30-second chunks."
        )
        audio = gr.Audio(sources=["upload", "microphone"], type="filepath", format="wav", label="Audio", recording=True)
        model = gr.Dropdown(
            choices=[("Small — CTC 1B v2", CTC_MODEL), ("Large — LLM 7B v2", LLM_MODEL)],
            value=CTC_MODEL,
            label="Model",
            visible="hidden",
        )
        language = gr.Dropdown(
            choices=[("Automatic / no hint", None)] + [
                (f"{entry['name']} — {entry['model_token']}", entry["model_token"])
                for entry in LANGUAGE_CATALOG
            ],
            value=None,
            label="Language hint (LLM only)",
            visible="hidden",
        )
        with gr.Tabs(selected="small", overflow_behavior="wrap"):
            with gr.Tab("Small · CTC 1B v2", id="small") as small_tab:
                gr.Markdown("Automatic language recognition with the smaller CTC model.")
                ctc_submit = gr.Button("Transcribe with Small", variant="primary")
            with gr.Tab("Large · LLM 7B v2", id="large") as large_tab:
                language_map = gr.HTML(
                    render_language_map(LANGUAGE_CATALOG) + MAP_CSS,
                    js_on_load=MAP_JS,
                    apply_default_css=False,
                    elem_id="language-map-control",
                    min_height=560,
                )
                llm_submit = gr.Button("Transcribe with Large", variant="primary")

        transcript = gr.Textbox(label="Transcript", lines=6)
        api_submit = gr.Button("API transcribe", visible="hidden")

        small_tab.select(_select_ctc_tab, outputs=model, api_name=False)
        large_tab.select(_select_llm_tab, outputs=model, api_name=False)
        language_map.click(
            _select_language,
            outputs=language,
            api_name=False,
        )
        ctc_submit.click(_transcribe_ctc, inputs=audio, outputs=transcript, api_name=False)
        llm_submit.click(
            _transcribe_llm,
            inputs=[audio, language],
            outputs=transcript,
            api_name=False,
            js=LLM_SUBMIT_JS,
        )
        api_submit.click(
            transcribe,
            inputs=[audio, model, language],
            outputs=transcript,
            api_name="transcribe",
        )
    return demo


if __name__ == "__main__":
    # Default to localhost so plain `python app.py` is safe on a single machine.
    # Set HOST=0.0.0.0 (or SERVER_NAME=0.0.0.0) to expose the UI on the LAN.
    host = os.getenv("HOST") or os.getenv("SERVER_NAME") or "127.0.0.1"
    create_ui().queue().launch(server_name=host, share=False)
