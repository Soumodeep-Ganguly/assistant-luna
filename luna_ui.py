# luna_ui.py
import os
import sys
import time
import queue
import threading
import asyncio
import numpy as np

from PySide6 import QtCore, QtGui, QtWidgets

import sounddevice as sd
import speech_recognition as sr

from database import get_config, set_config
from responder import respond
from tts_engine import speak
from ai_responder import ask_ai


# ------------------------------
# Visual / color constants
# ------------------------------
NEON = "#7C3AED"
NEON_CYAN = "#00E5FF"
TEXT = "#D7E1EE"
MUTED = "#9AA6B2"


# ------------------------------
# Helpers
# ------------------------------
def ensure_provider_env():
    """Ensure environment variables reflect the provider/key saved in the DB."""
    provider = get_config("provider", "ollama")
    api_key = get_config("api_key", "")

    for var in ("OPENAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        os.environ.pop(var, None)

    if provider == "openai" and api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    elif provider == "groq" and api_key:
        os.environ["GROQ_API_KEY"] = api_key
    elif provider == "openrouter" and api_key:
        os.environ["OPENROUTER_API_KEY"] = api_key
    # ollama: no env key required


def nice_name(raw: str, fallback="Luna"):
    raw = (raw or fallback).strip()
    return raw[0].upper() + raw[1:] if raw else fallback


# ------------------------------
# Waveform widget (FFT-based bars)
# ------------------------------
class WaveBars(QtWidgets.QWidget):
    def __init__(self, bars=32, parent=None):
        super().__init__(parent)
        self._bars = bars
        self._levels = np.zeros(self._bars, dtype=float)
        self._active = False
        self._fade = 0.15
        self.setMinimumHeight(80)

    def set_active(self, on: bool):
        self._active = on
        if not on:
            self._levels[:] = 0.0
            self.update()

    def set_levels(self, arr: np.ndarray):
        if arr is None or not self._active:
            return
        # resample arr to self._bars length
        if len(arr) != self._bars:
            arr = np.interp(np.linspace(0, 1, self._bars),
                            np.linspace(0, 1, len(arr)), arr)
        # smoothing
        self._levels = (1 - self._fade) * self._levels + self._fade * np.clip(arr, 0.0, 1.0)
        self.update()

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect().adjusted(8, 8, -8, -8)
        w, h = r.width(), r.height()
        gap = 4
        barw = max(2, (w - gap * (self._bars - 1)) // self._bars)

        # light background
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(255, 255, 255, 14))
        p.drawRoundedRect(r, 8, 8)

        grad = QtGui.QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        grad.setColorAt(0, QtGui.QColor(NEON_CYAN))
        grad.setColorAt(1, QtGui.QColor(NEON))
        p.setBrush(grad)

        for i, v in enumerate(self._levels):
            bh = int(v * h)
            rect = QtCore.QRect(r.left() + i * (barw + gap), r.bottom() - bh, barw, bh)
            p.drawRoundedRect(rect, 4, 4)


# ------------------------------
# Mic level worker: emits FFT / band values
# ------------------------------
class MicLevelWorker(QtCore.QThread):
    levels = QtCore.Signal(np.ndarray)

    def __init__(self, bars=32, parent=None, device=None):
        super().__init__(parent)
        self._bars = bars
        self._stop = threading.Event()
        self._device = device

    def stop(self):
        self._stop.set()

    def run(self):
        def callback(indata, frames, t, status):
            if self._stop.is_set():
                return
            try:
                mono = np.mean(indata, axis=1)
                spec = np.abs(np.fft.rfft(mono))
                if spec.size == 0:
                    return
                spec = spec / (spec.max() + 1e-9)
                # map to bars (log spacing)
                bins = np.logspace(0, np.log10(len(spec)), self._bars + 1, base=10.0) - 1
                bins = np.clip(bins.astype(int), 0, len(spec) - 1)
                out = []
                for i in range(self._bars):
                    a = bins[i]
                    b = bins[i + 1] if i + 1 < len(bins) else len(spec) - 1
                    out.append(float(np.max(spec[a:b + 1])) if b >= a else 0.0)
                self.levels.emit(np.array(out, dtype=float))
            except Exception:
                pass

        try:
            with sd.InputStream(callback=callback, channels=1, samplerate=16000, blocksize=1024,
                                device=self._device):
                while not self._stop.is_set():
                    time.sleep(0.05)
        except Exception:
            # device busy or unavailable -> silent exit
            pass


# ------------------------------
# SettingsDialog (provider + API key) with robust validation
# ------------------------------
class SettingsDialog(QtWidgets.QDialog):
    validationResult = QtCore.Signal(bool, str)  # emitted from worker thread -> _on_validation_result

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings - Provider & API Key")
        self.setModal(True)
        self.setFixedWidth(480)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Select provider and add API key (if required)"))

        self.provider = QtWidgets.QComboBox()
        self.provider.addItems(["ollama", "openai", "groq", "openrouter"])
        self.provider.setCurrentText(get_config("provider", "ollama"))
        layout.addWidget(QtWidgets.QLabel("Provider:"))
        layout.addWidget(self.provider)

        self.api_key = QtWidgets.QLineEdit()
        self.api_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("API key (leave blank for Ollama)")
        self.api_key.setText(get_config("api_key", ""))
        layout.addWidget(QtWidgets.QLabel("API Key:"))
        layout.addWidget(self.api_key)

        self.info = QtWidgets.QLabel("")
        self.info.setStyleSheet(f"color: {MUTED}")
        layout.addWidget(self.info)

        btns = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Validate & Save")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        btns.addStretch(1)
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)
        layout.addLayout(btns)

        self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn.clicked.connect(self.reject)
        self.validationResult.connect(self._on_validation_result)

    def _on_save(self):
        provider = self.provider.currentText()
        key = self.api_key.text().strip()

        self.info.setText("Validating…")
        self.save_btn.setEnabled(False)

        def worker():
            prev_env = dict(os.environ)
            try:
                # set env for ask_ai to pick up
                for v in ("OPENAI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
                    os.environ.pop(v, None)
                if provider == "openai" and key:
                    os.environ["OPENAI_API_KEY"] = key
                elif provider == "groq" and key:
                    os.environ["GROQ_API_KEY"] = key
                elif provider == "openrouter" and key:
                    os.environ["OPENROUTER_API_KEY"] = key

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # ask_ai is used for validation as requested
                    result = loop.run_until_complete(ask_ai("ping", provider=provider, model=None))
                finally:
                    loop.close()

                # result must be dict and have a non-error reply
                ok = False
                msg = "Validation failed"
                if isinstance(result, dict) and "reply" in result:
                    reply = (result.get("reply") or "").strip()
                    rlow = reply.lower()
                    # treat typical error phrases as failure
                    bad_phrases = [
                        "there was an error", "sorry, i didn't understand", "invalid", "could not",
                        "error", "no response", "invalid json", "invalid json returned"
                    ]
                    if reply and not any(b in rlow for b in bad_phrases) and len(reply) > 2:
                        ok = True
                        msg = f"Validated — provider '{provider}' looks good."
                    else:
                        msg = f"Validation failed: assistant reply: '{reply}'"
                else:
                    msg = f"Validation failed: unexpected response."

                if ok:
                    # Save
                    set_config("provider", provider)
                    set_config("api_key", key if provider != "ollama" else "")
                self.validationResult.emit(ok, msg)
            except Exception as e:
                self.validationResult.emit(False, f"Validation exception: {e}")
            finally:
                os.environ.clear()
                os.environ.update(prev_env)

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.Slot(bool, str)
    def _on_validation_result(self, ok: bool, msg: str):
        self.save_btn.setEnabled(True)
        self.info.setText(msg)
        if ok:
            self.accept()


# ------------------------------
# Main LunaUI
# ------------------------------
class LunaUI(QtWidgets.QMainWindow):
    # thread-safe UI signals
    appendChat = QtCore.Signal(str)
    setListening = QtCore.Signal(bool)
    setSpeaking = QtCore.Signal(bool)
    setMicLevels = QtCore.Signal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.resize(1000, 680)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowSystemMenuHint
        )

        assistant = nice_name(get_config("assistant_name", "Luna"), "Luna")
        self.setWindowTitle(f"{assistant} AI")

        # UI layout (keeps the futuristic look you already had)
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        v = QtWidgets.QVBoxLayout(root)
        v.setContentsMargins(12, 12, 12, 12)

        # title row
        tr = QtWidgets.QHBoxLayout()
        self.settingsBtn = QtWidgets.QPushButton("⚙")
        self.settingsBtn.setFixedSize(34, 34)
        self.settingsBtn.clicked.connect(self.open_settings)

        self.titleLabel = QtWidgets.QLabel(assistant)
        self.titleLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setObjectName("title")

        self.closeBtn = QtWidgets.QPushButton("✕")
        self.closeBtn.setFixedSize(34, 34)
        self.closeBtn.clicked.connect(self._close_app)

        tr.addWidget(self.settingsBtn)
        tr.addWidget(self.titleLabel, 1)
        tr.addWidget(self.closeBtn)

        v.addLayout(tr)

        # chat
        self.chat = QtWidgets.QTextEdit()
        self.chat.setReadOnly(True)
        v.addWidget(self.chat, 1)

        # input
        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText("Type here and press Enter…")
        self.input.returnPressed.connect(self._send_text)
        v.addWidget(self.input)

        # controls (mute + mic)
        controls = QtWidgets.QHBoxLayout()
        controls.addStretch(1)
        self.muteBtn = QtWidgets.QPushButton()
        self.muteBtn.setFixedSize(48, 48)
        self.muteBtn.clicked.connect(self.on_mic_muted)
        controls.addWidget(self.muteBtn)
        self.manualMicBtn = QtWidgets.QPushButton("🎤")
        self.manualMicBtn.setFixedSize(56, 56)
        self.manualMicBtn.clicked.connect(self._manual_capture)
        controls.addWidget(self.manualMicBtn)
        controls.addStretch(1)
        v.addLayout(controls)

        # waveform
        self.wave = WaveBars(bars=32)
        v.addWidget(self.wave)

        # style (keeps neon look)
        self.setStyleSheet(f"""
            #title {{ color: {NEON_CYAN}; font: 700 26px 'Orbitron'; text-shadow: 0 0 10px {NEON_CYAN}; }}
            QTextEdit {{ background: rgba(255,255,255,0.04); color: {TEXT}; border-radius: 10px; padding: 10px; }}
            QLineEdit {{ background: rgba(255,255,255,0.03); color: {TEXT}; border-radius: 8px; padding: 10px; }}
            QPushButton {{ background: rgba(255,255,255,0.03); color: {TEXT}; border-radius: 10px; }}
            QPushButton:hover {{ border: 1px solid {NEON_CYAN}; }}
        """)

        # internal state / threads
        self._stt_queue = queue.Queue()
        self._stt_running = True
        self._bg_stop = None
        self._mic_worker = None
        self._stt_thread = threading.Thread(target=self._stt_processor, daemon=True)
        self._stt_thread.start()

        # signals
        self.appendChat.connect(self.chat.append)
        self.setListening.connect(self._apply_listening)
        self.setSpeaking.connect(self._apply_speaking)
        self.setMicLevels.connect(self.wave.set_levels)

        # initialize mute state and start always-listen if not muted
        muted = get_config("muted", False)
        self._apply_mute_ui(muted)
        if not muted:
            # ensure provider env is set first
            if get_config("provider"):
                ensure_provider_env()
            self.start_background_listening()

        # welcome
        user = nice_name(get_config("user_name", "User"), "User")
        self.appendChat.emit(f"✨ Welcome, {user}. Listening automatically (unless muted).")

    # ------------------------------
    # settings dialog
    # ------------------------------
    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # refresh provider env if saved
            ensure_provider_env()
            # if not muted, ensure background listening is running
            if not get_config("muted", False):
                self.start_background_listening()

    # ------------------------------
    # background listening control
    # ------------------------------
    def start_background_listening(self):
        if self._bg_stop is not None:
            return  # already running
        try:
            self._bg_recognizer = sr.Recognizer()
            self._bg_mic = sr.Microphone()
            # start mic worker for waveform
            self._start_mic_worker()
            # start background listener; returned function stops it
            self._bg_stop = self._bg_recognizer.listen_in_background(self._bg_mic,
                                                                      self._bg_callback,
                                                                      phrase_time_limit=8)
            self.setListening.emit(True)
        except Exception as e:
            self.appendChat.emit(f"⚠️ Cannot start background listening: {e}")

    def stop_background_listening(self):
        if self._bg_stop is None:
            return
        try:
            self._bg_stop(wait_for_stop=False)
        except Exception:
            try:
                self._bg_stop()
            except Exception:
                pass
        self._bg_stop = None
        self.setListening.emit(False)
        # clear queue (optional)
        with self._stt_queue.mutex:
            self._stt_queue.queue.clear()

    def _bg_callback(self, recognizer, audio):
        # called on listen_in_background thread; push audio to queue for sequential processing
        try:
            self._stt_queue.put(audio)
        except Exception:
            pass

    # ------------------------------
    # STT processing worker
    # ------------------------------
    def _stt_processor(self):
        """Background thread: read audio from queue, recognition + respond sequentially."""
        while self._stt_running:
            try:
                audio = None
                try:
                    audio = self._stt_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if audio is None:
                    continue
                # recognition (use a fresh Recognizer instance to be safe)
                r = sr.Recognizer()
                try:
                    text = r.recognize_google(audio)
                except sr.UnknownValueError:
                    self.appendChat.emit("⚠️ Could not understand audio.")
                    continue
                except sr.RequestError as e:
                    self.appendChat.emit(f"⚠️ STT request failed: {e}")
                    continue

                # push user text to chat
                self.appendChat.emit(f"🧑 You (voice): {text}")

                # call backend (use saved provider env)
                try:
                    ensure_provider_env()
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        reply = loop.run_until_complete(respond(text))
                    finally:
                        loop.close()
                except Exception as e:
                    self.appendChat.emit(f"⚠️ Assistant error: {e}")
                    continue

                self.appendChat.emit(f"🤖 {nice_name(get_config('assistant_name', 'Luna'))}: {reply}")

                # visualize speaking and speak
                self.setSpeaking.emit(True)
                try:
                    # If your tts_engine.speak provides audio-chunk callback you can hook it here
                    speak(reply)
                except Exception as e:
                    self.appendChat.emit(f"⚠️ TTS error: {e}")
                finally:
                    self.setSpeaking.emit(False)

            except Exception:
                # safety: don't let thread die
                time.sleep(0.1)
                continue

    # ------------------------------
    # mic worker control (waveform)
    # ------------------------------
    def _start_mic_worker(self):
        if self._mic_worker is not None:
            return
        self._mic_worker = MicLevelWorker(bars=32)
        self._mic_worker.levels.connect(lambda arr: self.setMicLevels.emit(arr))
        self._mic_worker.start()

    def _stop_mic_worker(self):
        if self._mic_worker is None:
            return
        try:
            self._mic_worker.stop()
            self._mic_worker.wait(500)
        except Exception:
            pass
        self._mic_worker = None
        # flatten bars
        self.wave.set_active(False)

    # ------------------------------
    # UI slots
    # ------------------------------
    @QtCore.Slot(bool)
    def _apply_listening(self, on: bool):
        # start/stop mic worker according to listening state
        if on:
            self.wave.set_active(True)
            if self._mic_worker is None:
                self._start_mic_worker()
            self.muteBtn.setToolTip("Mute (stop automatic listening)")
        else:
            # stop mic worker
            self.wave.set_active(False)
            self._stop_mic_worker()
            self.muteBtn.setToolTip("Unmute (resume automatic listening)")

    @QtCore.Slot(bool)
    def _apply_speaking(self, on: bool):
        self.wave.set_active(on or (self._bg_stop is not None))

    # ------------------------------
    # manual mic button (one-shot)
    # ------------------------------
    def _manual_capture(self):
        # if background listening active, do nothing (to avoid duplicate)
        if self._bg_stop is not None:
            self.appendChat.emit("ℹ️ Always-listen is active — manual capture skipped.")
            return

        def one_shot():
            r = sr.Recognizer()
            with sr.Microphone() as src:
                r.adjust_for_ambient_noise(src, duration=0.5)
                self.appendChat.emit("🎧 Listening (manual)…")
                try:
                    audio = r.listen(src, timeout=6, phrase_time_limit=8)
                except Exception as e:
                    self.appendChat.emit(f"⚠️ Manual capture failed: {e}")
                    return

            try:
                text = r.recognize_google(audio)
                self.appendChat.emit(f"🧑 You (manual): {text}")
            except sr.UnknownValueError:
                self.appendChat.emit("⚠️ Could not understand audio.")
                return
            except sr.RequestError as e:
                self.appendChat.emit(f"⚠️ STT request failed: {e}")
                return

            # respond
            ensure_provider_env()
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    reply = loop.run_until_complete(respond(text))
                finally:
                    loop.close()
            except Exception as e:
                self.appendChat.emit(f"⚠️ Assistant error: {e}")
                return

            self.appendChat.emit(f"🤖 {nice_name(get_config('assistant_name','Luna'))}: {reply}")
            self.setSpeaking.emit(True)
            try:
                speak(reply)
            finally:
                self.setSpeaking.emit(False)

        threading.Thread(target=one_shot, daemon=True).start()

    # ------------------------------
    # mute toggle (persisted)
    # ------------------------------
    def on_mic_muted(self):
        current = get_config("muted", False)
        new = not current
        set_config("muted", new)
        self._apply_mute_ui(new)
        if new:
            # stop auto-listen
            self.stop_background_listening()
            self.appendChat.emit("🔇 Microphone muted. Automatic listening stopped.")
        else:
            # resume
            ensure_provider_env()
            self.start_background_listening()
            self.appendChat.emit("🔊 Microphone unmuted. Automatic listening resumed.")

    def _apply_mute_ui(self, muted: bool):
        if muted:
            self.muteBtn.setText("🔇")
            self.muteBtn.setToolTip("Unmute")
        else:
            self.muteBtn.setText("🔊")
            self.muteBtn.setToolTip("Mute")

    # ------------------------------
    # send typed text
    # ------------------------------
    def _send_text(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.appendChat.emit(f"🧑 You: {text}")

        def worker():
            try:
                ensure_provider_env()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    reply = loop.run_until_complete(respond(text))
                finally:
                    loop.close()
                self.appendChat.emit(f"🤖 {nice_name(get_config('assistant_name','Luna'))}: {reply}")
                # speaking animation
                self.setSpeaking.emit(True)
                try:
                    speak(reply)
                finally:
                    self.setSpeaking.emit(False)
            except Exception as e:
                self.appendChat.emit(f"⚠️ Assistant error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------
    # clean shutdown
    # ------------------------------
    def _close_app(self):
        # stop background listener + workers + stt thread
        self._stt_running = False
        try:
            self.stop_background_listening()
        except Exception:
            pass
        try:
            self._stop_mic_worker()
        except Exception:
            pass
        # clear queue to let thread exit faster
        with self._stt_queue.mutex:
            self._stt_queue.queue.clear()
        QtWidgets.QApplication.quit()

    def closeEvent(self, e):
        self._close_app()
        return super().closeEvent(e)


# ------------------------------
# Entrypoint
# ------------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    win = LunaUI()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()