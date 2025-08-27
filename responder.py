from tts_engine import speak
from ai_responder import ask_ai

# ---------------- Main Respond ---------------- #
def respond(command):
    parsed = ask_ai(command, provider="groq")

    print("DEBUG INFO ", parsed)

    reply = parsed.get("reply", "Sorry, I don't know how to respond.")
    speak(reply)