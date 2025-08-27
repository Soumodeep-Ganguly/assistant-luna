import json
import re
import os
from database import get_config

# Import only when needed (lazy imports to avoid unused deps)
import ollama

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# ---------------- JSON Handling ---------------- #
def normalize_response(parsed):
    if "reply" not in parsed:
        parsed["reply"] = "Sorry, I didn't understand."

    if "parameters" not in parsed or not parsed.get("parameters"):
        parsed["parameters"] = {}
        parsed["action"] = "none"

    if "action" not in parsed:
        parsed["action"] = "none"

    return parsed


def extract_json(text):
    """Attempt to extract and fix JSON from model output."""
    # Strip markdown/code block fencing and thinking tags
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"^```(?:json)?\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text.strip())

    # Extract JSON block
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {
            "reply": "Invalid JSON returned by the assistant.",
            "action": "none",
            "parameters": {}
        }

    json_text = match.group(0)

    # Try parsing as valid JSON
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        pass

    # Fallback fixes
    json_text = re.sub(r"(?<![a-zA-Z])'([^']*?)':", r'"\1":', json_text)
    json_text = re.sub(
        r':\s*\'(.*?)\'',
        lambda m: ': "' + m.group(1).replace('"', '\\"') + '"',
        json_text
    )

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print("JSON decoding error:", e)
        print("Faulty JSON:", json_text)
        return {
            "reply": "Invalid JSON returned by the assistant.",
            "action": "none",
            "parameters": {}
        }


# ---------------- Generic AI Query ---------------- #
def ask_ai(command, provider="ollama", model=None):
    """
    Query AI provider and return normalized JSON response.
    provider: "ollama" | "openai" | "groq" | "openrouter"
    """
    try:
        user_name = get_config("user_name", "Soumodeep")
        assistant_name = get_config("assistant_name", "Misaki")

        prompt = (
            "You are a voice assistant. Respond ONLY with a valid JSON object.\n\n"
            "Your response must include:\n"
            "- 'reply': a natural language response\n"
            "- 'action': one of:\n"
            "     'change_user_name', 'change_assistant_name', 'get_user_name', 'get_assistant_name', "
            "     'shutdown', 'open_app', 'search_web', 'open_tab', 'close_tab', 'none'\n"
            "- 'parameters': dictionary of needed data, or {} if none.\n\n"
            f"User name is '{user_name}'. Assistant name is '{assistant_name}'.\n"
            "Rules:\n"
            "- DO NOT include explanations or markdown.\n"
            "- DO NOT invent unknown values.\n"
            "- ALWAYS return a single valid JSON object with double quotes.\n"
            f"User command: {command}"
        )

        messages = [{"role": "user", "content": prompt}]

        # ---------------- Provider routing ---------------- #
        if provider == "ollama":
            model = model or "gemma3:1b"
            result = ollama.chat(model=model, messages=messages)
            content = result["message"]["content"]

        elif provider == "openai":
            if OpenAI is None:
                raise ImportError("openai package not installed")
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = model or "gpt-4o-mini"
            resp = client.chat.completions.create(model=model, messages=messages)
            content = resp.choices[0].message.content

        elif provider == "groq":
            if OpenAI is None:
                raise ImportError("openai package not installed")
            client = OpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1")
            model = model or "openai/gpt-oss-20b"
            resp = client.chat.completions.create(model=model, messages=messages)
            content = resp.choices[0].message.content

        elif provider == "openrouter":
            if OpenAI is None:
                raise ImportError("openai package not installed")
            client = OpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")
            model = model or "anthropic/claude-3.5-sonnet"
            resp = client.chat.completions.create(model=model, messages=messages)
            content = resp.choices[0].message.content

        else:
            return {"reply": "Unknown provider.", "action": "none", "parameters": {}}

        # ---------------- Parse JSON ---------------- #
        parsed = normalize_response(extract_json(content))
        return parsed

    except Exception as e:
        print(f"Error communicating with {provider}: {e}")
        return {"reply": "There was an error understanding you.", "action": "none", "parameters": {}}