# llm.py  — uses google-generativeai directly (no LangChain wrapper)
import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY is missing in .env")

# You can pin a model in .env (GEMINI_MODEL=...), but we also keep a fallback list.
ENV_MODEL = (os.getenv("GEMINI_MODEL") or "").strip()

# Known-good text chat models (will try in this order if ENV_MODEL is empty or fails)
CANDIDATE_MODELS = [
    # Newer ones first
    "gemini-1.5-flash",
    "gemini-1.5-flash-002",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    # Older but widely available
    "gemini-1.0-pro",
    "gemini-pro",
]

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "quiz_prompt.md")
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_MD = f.read()

genai.configure(api_key=API_KEY)

def _format_prompt(url: str, article_text: str) -> str:
    # We’ll send the system instructions + user content in one text prompt.
    return f"""{PROMPT_MD}

Article URL: {url}

Article text:
{article_text}
"""

class LLMError(Exception):
    pass

def _try_model_once(model_name: str, prompt_text: str) -> dict:
    model = genai.GenerativeModel(model_name)
    # Generate
    resp = model.generate_content(prompt_text)
    # Handle blocked/empty responses
    if not hasattr(resp, "text") or not resp.text:
        raise LLMError(f"Model {model_name} returned empty response.")
    content = resp.text.strip()

    # Some models wrap JSON in ``` blocks; strip if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]

    try:
        return json.loads(content)
    except Exception as e:
        raise LLMError(f"Model {model_name} returned non-JSON or bad JSON: {e}\nRaw: {content[:400]}")

def generate_quiz_payload(url: str, article_text: str) -> dict:
    """
    Builds the prompt and tries the env-selected model first, then fallbacks.
    Returns a Python dict (parsed JSON). Raises LLMError on failure.
    """
    prompt_text = _format_prompt(url, article_text)

    # Build the list to try
    models_to_try = []
    if ENV_MODEL:
        models_to_try.append(ENV_MODEL)
    models_to_try += [m for m in CANDIDATE_MODELS if m != ENV_MODEL]

    errors = []
    for name in models_to_try:
        try:
            print(f"[LLM] Trying model: {name}")
            return _try_model_once(name, prompt_text)
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue
    raise LLMError("All candidate models failed:\n" + "\n".join(errors))

# --- Simple ping for /api/llm-test
def ping_llm() -> dict:
    """
    Returns {"ok": True, "model": <model_used>, "content": "..."} on success,
            or {"ok": False, "error": "..."} on failure.
    """
    try_names = [ENV_MODEL] if ENV_MODEL else []
    try_names += [m for m in CANDIDATE_MODELS if m not in try_names and m]

    for name in try_names:
        try:
            model = genai.GenerativeModel(name)
            resp = model.generate_content("Reply with OK")
            text = (resp.text or "").strip()
            if text:
                return {"ok": True, "model": name, "content": text[:200]}
        except Exception as e:
            last_err = str(e)
            continue
    return {"ok": False, "error": last_err if 'last_err' in locals() else "Unknown error"}
