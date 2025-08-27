import speech_recognition as sr

def listen_for_command(recognizer, mic, silent=False):
    if not silent:
        print("Listening for speech...")
    try:
        audio = recognizer.listen(mic, timeout=5, phrase_time_limit=7)
        # print("Audio captured")  # Debug: confirm audio is captured
    except sr.WaitTimeoutError:
        # Don’t log anything — just wait again silently
        return None

    try:
        command = recognizer.recognize_google(audio)
        print("You said:", command)
        return command.lower()
    except sr.UnknownValueError:
        # print("Speech not understood")  # Debug: audio captured but not recognizedh
        return None
    except sr.RequestError as e:
        print(f"Error with Google API: {e}")
        return None
    


# import vosk
# import pyaudio
# import json

# model_path = "./vosk_models/vosk-model-en-us-0.22"  # Ensure the correct path to your model
# model = vosk.Model(model_path)
# recognizer = vosk.KaldiRecognizer(model, 16000)
# recognizer.SetWords(True)

# p = pyaudio.PyAudio()
# stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)

# def listen_for_command(silent=False):
#     if not silent:
#         print("Listening for speech...")

#     data = stream.read(8000)
#     if recognizer.AcceptWaveform(data):
#         result = recognizer.Result()
#         result_dict = json.loads(result)  # Convert to a dictionary
#         recognized_text = result_dict.get("text", "")  # Extract the recognized text

#         if recognized_text:
#             print(f"You said: {recognized_text}")
#             return recognized_text.lower()  # Return the command in lowercase
#         else:
#             print("No speech detected or recognized.")
#             return None
#     return None