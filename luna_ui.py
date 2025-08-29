import sys
import os
import threading
import asyncio
import time
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
import speech_recognition as sr
import sounddevice as sd

from responder import respond
from tts_engine import speak
from database import get_config

# App name fallback; will be overridden by DB name
APP_NAME = "Luna AI"

# ------------------------------
# Helpers (fonts & icons)
# ------------------------------
def load_custom_font():
    for fname in ["Orbitron-Regular.ttf", "Montserrat-Regular.ttf"]:
        if os.path.exists(fname):
            QtGui.QFontDatabase.addApplicationFont(fname)
            break

def make_icon(svg_path: str = None, fallback_char: str = "●", size: int = 24):
    if svg_path and os.path.exists(svg_path):
        icon = QtGui.QIcon(svg_path)
        return icon
    pix = QtGui.QPixmap(size, size)
    pix.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    font = QtGui.QFont()
    font.setPointSize(int(size * 0.75))
    p.setFont(font)
    p.setPen(QtGui.QPen(QtGui.QColor("#00e5ff")))
    p.drawText(pix.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, fallback_char)
    p.end()
    return QtGui.QIcon(pix)


@QtCore.Slot(float)
def update_wave_level(self, rms: float):
    self.wave.set_level(rms)


@QtCore.Slot(str)
def append_chat_message(self, msg: str):
    self.chat_append(msg)


# ensure UI returns to ready
@QtCore.Slot(bool)
def set_listening_state(self, state: bool):
    self._set_listening(state)
    

# ------------------------------
# Waveform widget (driven by RMS)
# ------------------------------
class WaveformBars(QtWidgets.QWidget):
    def __init__(self, bars=8, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumHeight(48)
        self.bars = bars
        self._values = [0.0] * bars
        self._target = [0.0] * bars
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(60)  # 60 ms update
        self.setVisible(True)

    def start(self):
        # handled externally; we just ensure timer runs
        self.setVisible(True)

    def stop(self):
        self._target = [0.0] * self.bars

    def set_level(self, rms: float):
        # map rms (0..1) to bar targets: create a small random distribution around rms
        base = float(min(max(rms, 0.0), 1.0))
        for i in range(self.bars):
            jitter = (i - self.bars/2) / (self.bars*2)
            self._target[i] = max(0.0, min(1.0, base + jitter * 0.25))

    def _tick(self):
        # smooth towards target
        for i in range(self.bars):
            self._values[i] += (self._target[i] - self._values[i]) * 0.25
            if abs(self._values[i]) < 0.001:
                self._values[i] = 0.0
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        gap = max(2, int(w * 0.008))
        bar_w = max(4, (w - gap*(self.bars-1)) // self.bars)
        x = 0
        for v in self._values:
            bh = int(h * v)
            rect = QtCore.QRect(x, h - bh, bar_w, bh)
            grad = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0, QtGui.QColor(0, 229, 255, 220))
            grad.setColorAt(1, QtGui.QColor(167, 139, 250, 200))
            p.setBrush(QtGui.QBrush(grad))
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            r = min(bar_w, 10)
            p.drawRoundedRect(rect, r, r)
            x += bar_w + gap
        p.end()

# ------------------------------
# Main Window
# ------------------------------
class LunaUI(QtWidgets.QMainWindow):
    micPressed = QtCore.Signal()
    micMuted = QtCore.Signal()
    micStopped = QtCore.Signal()

    def __init__(self):
        super().__init__()

        # Load assistant name from DB (capitalize first char)
        assistant_name = get_config("assistant_name", "Luna") or "Luna"
        assistant_name = assistant_name.strip()
        if assistant_name:
            title_name = assistant_name[0].upper() + assistant_name[1:]
        else:
            title_name = "Luna"

        self.setWindowTitle(title_name + " AI")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowSystemMenuHint
            | QtCore.Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.resize(980, 640)

        # central widget
        self.bg = QtWidgets.QWidget()
        self.bg.setObjectName("bg")
        self.setCentralWidget(self.bg)
        self.vbox = QtWidgets.QVBoxLayout(self.bg)
        self.vbox.setContentsMargins(18, 18, 18, 18)
        self.vbox.setSpacing(10)

        # title + close button row
        titleRow = QtWidgets.QHBoxLayout()
        self.title = QtWidgets.QLabel(title_name)
        self.title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.title.setObjectName("title")
        self.title.setMinimumHeight(56)

        # close button top-right
        self.closeBtn = QtWidgets.QPushButton()
        self.closeBtn.setFixedSize(30, 30)
        self.closeBtn.setIcon(make_icon(fallback_char="✕", size=18))
        self.closeBtn.setObjectName("closeBtn")
        self.closeBtn.setToolTip("Close")
        self.closeBtn.clicked.connect(self._close_pressed)

        titleRow.addWidget(self.title, 1)
        titleRow.addWidget(self.closeBtn, 0, QtCore.Qt.AlignmentFlag.AlignRight)

        # Chat area + input
        self.chat = QtWidgets.QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setObjectName("chat")
        self.chat.setPlaceholderText("Conversation will appear here...")

        self.input = QtWidgets.QLineEdit()
        self.input.setObjectName("input")
        self.input.setPlaceholderText("Type to Luna and press Enter…")
        self.input.returnPressed.connect(self._send_text)

        # Listening status + waveform
        self.listeningRow = QtWidgets.QHBoxLayout()
        self.listeningLbl = QtWidgets.QLabel("Ready.")
        self.listeningLbl.setObjectName("listening")
        self.wave = WaveformBars()
        self.wave.setFixedHeight(48)
        self.listeningRow.addWidget(self.listeningLbl, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.listeningRow.addWidget(self.wave, 1)

        # Bottom controls
        self.controls = QtWidgets.QWidget()
        self.controls.setObjectName("controls")
        self.controlsLayout = QtWidgets.QHBoxLayout(self.controls)
        self.controlsLayout.setContentsMargins(0, 6, 0, 0)
        self.controlsLayout.addStretch(1)

        self.micBtn = QtWidgets.QPushButton()
        self.micBtn.setObjectName("micBtn")
        self.micBtn.setIcon(make_icon(fallback_char="🎤"))
        self.micBtn.setIconSize(QtCore.QSize(36, 36))
        self.micBtn.setFixedSize(80, 80)
        self.micBtn.clicked.connect(self.on_mic_pressed)

        self.muteBtn = QtWidgets.QPushButton()
        self.muteBtn.setObjectName("muteBtn")
        self.muteBtn.setIcon(make_icon(fallback_char="🔇"))
        self.muteBtn.setIconSize(QtCore.QSize(22, 22))
        self.muteBtn.setFixedSize(48, 48)
        self.muteBtn.clicked.connect(self.on_mic_muted)

        self.stopBtn = QtWidgets.QPushButton()
        self.stopBtn.setObjectName("stopBtn")
        self.stopBtn.setIcon(make_icon(fallback_char="⏹"))
        self.stopBtn.setIconSize(QtCore.QSize(24, 24))
        self.stopBtn.setFixedSize(48, 48)
        self.stopBtn.clicked.connect(self.on_mic_stopped)

        self.controlsLayout.addWidget(self.muteBtn)
        self.controlsLayout.addWidget(self.micBtn)
        self.controlsLayout.addWidget(self.stopBtn)
        self.controlsLayout.addStretch(1)

        # layout add
        self.vbox.addLayout(titleRow)
        self.vbox.addWidget(self.chat, 1)
        self.vbox.addWidget(self.input)
        self.vbox.addLayout(self.listeningRow)
        self.vbox.addWidget(self.controls)

        # Drag to move
        self._drag_pos = None

        # audio monitoring state
        self._listening_stream = None
        self._listening_lock = threading.Lock()
        self._current_rms = 0.0
        self._running = True
        self._is_listening = False
        self._is_speaking = False

        # animations & style
        self._init_animations()
        load_custom_font()
        self._apply_style()

    # ------------------------------
    # Close handling
    # ------------------------------
    def _close_pressed(self):
        self._running = False
        # stop any running streams
        try:
            if self._listening_stream is not None:
                self._listening_stream.stop()
                self._listening_stream.close()
        except Exception:
            pass
        QtWidgets.QApplication.quit()

    # ------------------------------
    # Integration Hooks (connect your backend here)
    # ------------------------------
    def on_mic_pressed(self):
        # Start visualization stream
        self._start_mic_stream()
        self._set_listening(True)
        self._pulse_on(True)
        self.chat_append("🟣 Luna: Listening…")

        # Speech recognition happens in a background thread (blocking)
        def run_stt():
            recognizer = sr.Recognizer()
            with sr.Microphone() as mic:
                try:
                    audio = recognizer.listen(mic, timeout=6, phrase_time_limit=12)
                    # stop mic stream after capture so RMS resets when not speaking
                    self._stop_mic_stream()
                    command = recognizer.recognize_google(audio)
                    QtCore.QMetaObject.invokeMethod(
                        self,
                        lambda: self.chat_append(f"🧑 You: {command}"),
                        QtCore.Qt.ConnectionType.QueuedConnection
                    )
                    # Send to backend asyncio respond
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    res = loop.run_until_complete(respond(command))
                    loop.close()
                    QtCore.QMetaObject.invokeMethod(
                        self,
                        lambda: self.chat_append(f"🟣 {get_config('assistant_name','Luna').capitalize()}: {res}"),
                        QtCore.Qt.ConnectionType.QueuedConnection
                    )
                    # While speaking, pass audio chunks callback to animate bars
                    def ui_chunk_callback(arr):
                        # compute RMS of TTS audio chunk
                        rms = float(np.sqrt(np.mean(np.square(arr))))
                        QtCore.QMetaObject.invokeMethod(self, lambda: self.wave.set_level(rms), QtCore.Qt.ConnectionType.QueuedConnection)

                    # call speak (synchronous) but with visualization callback
                    speak(res, on_audio_chunk=ui_chunk_callback)
                except sr.WaitTimeoutError:
                    # no speech captured
                    self._stop_mic_stream()
                    QtCore.QMetaObject.invokeMethod(self, lambda: self.chat_append("⚠️ No speech detected."), QtCore.Qt.ConnectionType.QueuedConnection)
                except sr.UnknownValueError:
                    self._stop_mic_stream()
                    QtCore.QMetaObject.invokeMethod(
                        self, "append_chat_message",
                        QtCore.Qt.ConnectionType.QueuedConnection,
                        QtCore.Q_ARG(str, "⚠️ Could not understand audio.")
                    )
                except sr.RequestError as e:
                    self._stop_mic_stream()
                    QtCore.QMetaObject.invokeMethod(self, lambda: self.chat_append(f"⚠️ STT error: {e}"), QtCore.Qt.ConnectionType.QueuedConnection)
                except Exception as e:
                    self._stop_mic_stream()
                    QtCore.QMetaObject.invokeMethod(self, lambda: self.chat_append(f"⚠️ Error: {e}"), QtCore.Qt.ConnectionType.QueuedConnection)
                finally:
                    QtCore.QMetaObject.invokeMethod(
                        self, "set_listening_state",
                        QtCore.Qt.ConnectionType.QueuedConnection,
                        QtCore.Q_ARG(bool, False)
                    )
                    QtCore.QMetaObject.invokeMethod(self, lambda: self._pulse_on(False), QtCore.Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=run_stt, daemon=True).start()

    def on_mic_muted(self):
        self._set_listening(False)
        self._pulse_on(False)
        self._stop_mic_stream()
        self.chat_append("🔕 Mic muted.")
        self.micMuted.emit()

    def on_mic_stopped(self):
        self._set_listening(False)
        self._pulse_on(False)
        self._stop_mic_stream()
        self.chat_append("⏹️ Stopped listening.")
        self.micStopped.emit()

    def _send_text(self):
        text = self.input.text().strip()
        if not text:
            return
        self.chat_append(f"🧑 You: {text}")
        self.input.clear()

        def run_backend():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(respond(text))
                loop.close()

                QtCore.QMetaObject.invokeMethod(
                    self, 
                    lambda: self.chat_append(f"🟣 {get_config('assistant_name','Luna').capitalize()}: {result}"),
                    QtCore.Qt.ConnectionType.QueuedConnection
                )

                # visualize TTS by receiving audio chunks from speak()
                def ui_chunk_callback(arr):
                    rms = float(np.sqrt(np.mean(np.square(arr))))
                    QtCore.QMetaObject.invokeMethod(self, lambda: self.wave.set_level(rms), QtCore.Qt.ConnectionType.QueuedConnection)

                speak(result, on_audio_chunk=ui_chunk_callback)
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(self, lambda: self.chat_append(f"⚠️ Error: {e}"), QtCore.Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=run_backend, daemon=True).start()

    # ------------------------------
    # Mic visualization stream
    # ------------------------------
    def _start_mic_stream(self):
        if self._listening_stream is not None:
            return
        try:
            # callback receives indata (numpy array), frames, time, status
            def cb(indata, frames, time_info, status):
                if status:
                    pass  # you could log status
                # compute RMS of input (mono)
                try:
                    if indata.ndim > 1:
                        mono = np.mean(indata, axis=1)
                    else:
                        mono = indata
                    rms = float(np.sqrt(np.mean(np.square(mono))))
                except Exception:
                    rms = 0.0
                
                QtCore.QMetaObject.invokeMethod(
                    self, "update_wave_level",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(float, rms)
                )

            self._listening_stream = sd.InputStream(callback=cb, channels=1, samplerate=16000)
            self._listening_stream.start()
        except Exception as e:
            print("Failed to start mic stream:", e)
            self._listening_stream = None

    def _stop_mic_stream(self):
        try:
            if self._listening_stream is not None:
                self._listening_stream.stop()
                self._listening_stream.close()
        except Exception:
            pass
        finally:
            self._listening_stream = None
            # ensure bars flatten
            self.wave.stop()

    # ------------------------------
    # UI State
    # ------------------------------
    def chat_append(self, line: str):
        self.chat.append(line)
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())

    def _set_listening(self, on: bool):
        if on:
            self.listeningLbl.setText("Listening…")
            self.wave.start()
        else:
            self.listeningLbl.setText("Ready.")
            self.wave.stop()

    # ------------------------------
    # Window Dragging
    # ------------------------------
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ------------------------------
    # Animations
    # ------------------------------
    def _init_animations(self):
        self.anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(700)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutQuad)
        self.anim.start()

        self.pulseShadow = QtWidgets.QGraphicsDropShadowEffect(self.micBtn)
        self.pulseShadow.setBlurRadius(0)
        self.pulseShadow.setOffset(0, 0)
        self.pulseShadow.setColor(QtGui.QColor("#00e5ff"))
        self.micBtn.setGraphicsEffect(self.pulseShadow)

        self.pulse = QtCore.QPropertyAnimation(self.pulseShadow, b"blurRadius")
        self.pulse.setDuration(800)
        self.pulse.setStartValue(10)
        self.pulse.setEndValue(35)
        self.pulse.setEasingCurve(QtCore.QEasingCurve.Type.InOutQuad)
        self.pulse.setLoopCount(-1)

    def _pulse_on(self, on: bool):
        if on and self.pulse.state() != QtCore.QAbstractAnimation.State.Running:
            self.pulse.start()
        elif not on and self.pulse.state() == QtCore.QAbstractAnimation.State.Running:
            self.pulse.stop()
            self.pulseShadow.setBlurRadius(0)

    # ------------------------------
    # Styling
    # ------------------------------
    def _apply_style(self):
        self.setStyleSheet("""
            QWidget#bg {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(20, 20, 35, 220),
                    stop:1 rgba(10, 6, 18, 180)
                );
                border: 1px solid rgba(255,255,255,30);
                border-radius: 14px;
            }
            QLabel#title {
                color: #ccf9ff;
                font-size: 30px;
                font-weight: 700;
                font-family: "Orbitron", "Montserrat", "Segoe UI", Arial;
                letter-spacing: 1px;
            }
            QTextEdit#chat {
                color: rgba(240, 248, 255, 230);
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 13px;
            }
            QLineEdit#input {
                color: rgba(240, 248, 255, 230);
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 13px;
            }
            QLabel#listening {
                color: #aab7ff;
                font-size: 13px;
            }
            QPushButton#micBtn {
                color: #00e5ff;
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                    fx:0.5, fy:0.5,
                    stop:0 rgba(0, 229, 255, 120),
                    stop:1 rgba(167, 139, 250, 90)
                );
                border: 1px solid rgba(255,255,255, 40);
                border-radius: 40px;
            }
            QPushButton#closeBtn {
                background: rgba(255,255,255,0.03);
                border: none;
                border-radius: 6px;
            }
            QPushButton#closeBtn:hover {
                background: rgba(255,50,50,0.18);
            }
            QPushButton#muteBtn, QPushButton#stopBtn {
                color: #c8a6ff;
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 10px;
            }
        """)

# ------------------------------
# App Entry
# ------------------------------
def main():
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling)

    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(make_icon(fallback_char="◌", size=64))

    win = LunaUI()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()