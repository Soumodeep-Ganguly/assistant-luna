import sounddevice as sd
from kokoro import KPipeline

# Initialize Kokoro TTS pipeline
pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')

def speak(text: str, voice='af_heart', speed=1.0):
    print(text)  # Also print to console

    # Generate and play audio segments
    generator = pipeline(text, voice=voice, speed=speed)

    for i, (gs, ps, audio) in enumerate(generator):
        sd.stop()
        sd.play(audio, 24000)
        sd.wait()


# speak("Hello there! This is Kokoro speaking.")