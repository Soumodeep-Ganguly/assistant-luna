import speech_recognition as sr
from dotenv import load_dotenv
import time
import threading
import asyncio
from speech_listener import listen_for_command
from responder import respond
from tts_engine import speak
from database import init_db, get_config


# ---------------- MCP ---------------- #
from mcp.server import Server

server = Server("luna-mcp")

@server.tool()
def open_app(app_name: str):
    """Open a local application"""
    return f"App '{app_name}' opened."

@server.tool()
def search_web(query: str):
    """Search something on the web"""
    return f"Results for '{query}' (stubbed)."

@server.tool()
def open_tab(url: str):
    """Open a browser tab"""
    return f"Opened new tab: {url}"

@server.tool()
def close_tab(tab_id: str):
    """Close a browser tab"""
    return f"Closed tab {tab_id}"

def run_mcp_server():
    asyncio.run(server.run("localhost", 3001))  # serves on http://localhost:3001

def start_mcp_background():
    thread = threading.Thread(target=run_mcp_server, daemon=True)
    thread.start()
    print("✅ MCP server started on http://localhost:3001")


# ---------------- Main Assistant ---------------- #
load_dotenv()

def main():
    init_db()

    # Optional: Set initial config values
    # set_config("user_name", "Alex")
    # set_config("assistant_name", "Zira")
    user_name = get_config("user_name", "Soumodeep")
    assistant_name = get_config("assistant_name", "Misaki")

    # Start MCP server in background
    start_mcp_background()

    print("Voice assistant activated")
    recognizer = sr.Recognizer()

    with sr.Microphone() as mic:
        print("Adjusting for background noise... Please wait.")
        recognizer.adjust_for_ambient_noise(mic, duration=1)
        speak(f"Hi {user_name}. I am {assistant_name}, your personal assistant.")

        try:
            silent_mode = False
            while True:
                command = listen_for_command(recognizer, mic, silent=silent_mode)
                if command:
                    silent_mode = False
                    if any(word in command for word in ["shutdown yourself", "stop listening"]):
                        speak("Shutting down. Goodbye.")
                        break
                    respond(command)
                else:
                    silent_mode = True
                    time.sleep(0.5)
        except KeyboardInterrupt:
            speak("Interrupted by user. Exiting.")

if __name__ == "__main__":
    main()