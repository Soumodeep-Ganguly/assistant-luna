import speech_recognition as sr
from dotenv import load_dotenv
import time
from speech_listener import listen_for_command
from responder import respond
from tts_engine import speak
from database import init_db, get_config

load_dotenv()

def main():
    init_db()

    # Optional: Set initial config values
    # set_config("user_name", "Alex")
    # set_config("assistant_name", "Zira")
    user_name = get_config("user_name", "Soumodeep")
    assistant_name = get_config("assistant_name", "Misaki")

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