import os
import webbrowser
from tts_engine import speak
from database import get_config, set_config


# ---------------- Action Handlers ---------------- #
def handle_change_user_name(params):
    new_name = params.get("new_name")
    if new_name:
        set_config("user_name", new_name)
        speak(f"Okay, I'll call you {new_name} now.")


def handle_change_assistant_name(params):
    new_name = params.get("new_name")
    if new_name:
        set_config("assistant_name", new_name)
        speak(f"My new name is {new_name}.")


def handle_get_user_name(_):
    user_name = get_config("user_name", "Soumodeep")
    speak(f"Your name is {user_name}.")


def handle_get_assistant_name(_):
    assistant_name = get_config("assistant_name", "Misaki")
    speak(f"My name is {assistant_name}.")


def handle_shutdown(_):
    speak("Okay, shutting down.")
    exit(0)


def handle_open_app(params):
    app = params.get("app")
    if app:
        try:
            os.system(f"start {app}")  # Windows
            speak(f"Opening {app}.")
        except Exception as e:
            speak(f"Sorry, I couldn't open {app}. Error: {e}")


def handle_search_web(params):
    query = params.get("query")
    if query:
        url = f"https://www.google.com/search?q={query}"
        webbrowser.open(url)
        speak(f"Here are the search results for {query}.")


def handle_open_tab(params):
    url = params.get("url")
    if url:
        webbrowser.open(url)
        speak(f"Opening {url} in a new tab.")


def handle_close_tab(_):
    # Needs automation via Selenium/Playwright or browser extension
    speak("Closing tabs is not supported yet. You may need a browser extension.")