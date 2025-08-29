import json
import re
import os

from fastmcp import Client
from database import get_config

# Lazy import heavy deps
import ollama
from openai import OpenAI

MCP_SERVER_URL = "http://127.0.0.1:3001"  # wherever your MCP server runs

mcp_client = Client(MCP_SERVER_URL)



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
async def ask_ai(command, provider="ollama", model=None):
    """
    Query AI provider and return normalized JSON response.
    provider: "ollama" | "openai" | "groq" | "openrouter"
    """
    try:
        async with mcp_client:
            user_name = get_config("user_name", "Soumodeep")
            assistant_name = get_config("assistant_name", "Luna")

            # Prompt is split: JSON-only for Ollama, tool-aware for others
            if provider == "ollama":
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
                    "- ALWAYS return a single valid JSON object with double quotes.\n"
                    f"User command: {command}"
                )
            else:
                prompt = (
                    "You are a voice assistant. You can call tools if needed.\n\n"
                    f"User name is '{user_name}'. Assistant name is '{assistant_name}'.\n"
                    f"User command: {command}"
                )

            messages = [{"role": "user", "content": prompt}]

            # ---------------- Provider routing ---------------- #
            if provider == "ollama":
                model = model or "gemma3:1b"
                result = ollama.chat(model=model, messages=messages)
                content = result["message"]["content"]
                parsed = normalize_response(extract_json(content))

                # If Ollama suggests an action, run it via MCP
                if parsed["action"] != "none":
                    try:
                        tool_call = { "name": parsed["action"], "arguments": parsed["parameters"] }
                        result = mcp_client.execute_tool(tool_call)
                        parsed["reply"] = str(result)
                    except Exception as e:
                        parsed["reply"] = f"Failed to execute {parsed['action']}: {e}"

                return parsed

            elif provider in ("openai", "groq", "openrouter"):
                if OpenAI is None:
                    raise ImportError("openai package not installed")

                if provider == "openai":
                    api_key = os.getenv("OPENAI_API_KEY")
                    base_url = None
                    model = model or "gpt-4o-mini"
                elif provider == "groq":
                    api_key = os.getenv("GROQ_API_KEY")
                    base_url = "https://api.groq.com/openai/v1"
                    model = model or "openai/gpt-oss-20b"
                elif provider == "openrouter":
                    api_key = os.getenv("OPENROUTER_API_KEY")
                    base_url = "https://openrouter.ai/api/v1"
                    model = model or "anthropic/claude-3.5-sonnet"

                client = OpenAI(api_key=api_key, base_url=base_url)

                tools_list = await mcp_client.list_tools()
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tools_list if mcp_client else None,
                    tool_choice="auto" if mcp_client else None,
                )

                msg = response.choices[0].message

                # Check if AI made a tool call
                if msg.tool_calls:
                    tool_call = msg.tool_calls[0]
                    result = mcp_client.execute_tool(tool_call)
                    return {
                        "reply": str(result),
                        "action": tool_call.name,
                        "parameters": tool_call.arguments,
                    }

                # Fallback normal reply
                return {
                    "reply": msg.content,
                    "action": "none",
                    "parameters": {},
                }
            
            else:
                return {"reply": "Unknown provider.", "action": "none", "parameters": {}}

    except Exception as e:
        print(f"Error communicating with {provider}: {e}")
        return {
            "reply": "There was an error understanding you.",
            "action": "none",
            "parameters": {},
        }
