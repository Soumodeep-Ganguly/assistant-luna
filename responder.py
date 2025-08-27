from tts_engine import speak
from handler import handle_change_user_name, handle_change_assistant_name, handle_get_user_name, handle_get_assistant_name, handle_shutdown, handle_open_app, handle_search_web, handle_open_tab, handle_close_tab
from ai_responder import ask_ai


# Action registry for scalability
ACTION_HANDLERS = {
    "change_user_name": handle_change_user_name,
    "change_assistant_name": handle_change_assistant_name,
    "get_user_name": handle_get_user_name,
    "get_assistant_name": handle_get_assistant_name,
    "shutdown": handle_shutdown,
    "open_app": handle_open_app,
    "search_web": handle_search_web,
    "open_tab": handle_open_tab,
    "close_tab": handle_close_tab,
}


# ---------------- Main Respond ---------------- #
def respond(command):
    parsed = ask_ai(command, provider="groq")

    print("DEBUG INFO ", parsed)

    reply = parsed.get("reply", "Sorry, I don't know how to respond.")
    action = parsed.get("action", "none")
    params = parsed.get("parameters", {})

    # Speak the AI-generated reply
    speak(reply)

    # Dispatch to handler if available
    handler = ACTION_HANDLERS.get(action)
    if handler:
        handler(params)