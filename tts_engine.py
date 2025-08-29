import sounddevice as sd
from kokoro import KPipeline
import numpy as np
from typing import Callable, Optional

# Initialize Kokoro TTS pipeline
pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')

def speak(text: str, voice='jf_alpha', speed=1.0, on_audio_chunk: Optional[Callable[[np.ndarray], None]] = None):
    """
    Speak text using Kokoro pipeline. If on_audio_chunk is provided, it will be called
    with each numpy audio chunk (float32) before playback so UI can visualize it.
    """
    
    print(text)  # Also print to console

    # Generate and play audio segments
    generator = pipeline(text, voice=voice, speed=speed)

    for i, (gs, ps, audio) in enumerate(generator):
        # audio is expected to be a numpy array (float32) or bytes.
        # Normalize to float32 numpy array if necessary
        try:
            arr = audio
            # If bytes, convert to numpy float32 assuming 16-bit PCM
            if isinstance(audio, (bytes, bytearray)):
                arr = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                # ensure numpy
                arr = np.asarray(audio, dtype=np.float32)
        except Exception:
            arr = None

        # Callback for UI visualization
        if on_audio_chunk is not None and arr is not None:
            try:
                on_audio_chunk(arr)
            except Exception:
                pass

        # Play
        try:
            sd.stop()
            sd.play(arr, 24000)
            sd.wait()
        except Exception as e:
            # if playback fails, ignore but print error
            print("Playback error in speak:", e)


# speak("Hello there! This is Kokoro speaking.")
