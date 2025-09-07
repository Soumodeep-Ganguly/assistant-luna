from enum import Enum
from app.ai.chat import ChatHub
from PySide6.QtCore import QThread, Signal

class LabelVariants(Enum):
    HEADING = "heading"
    LABEL = "label"

class ModelFetcher(QThread):
    finished = Signal(list)
    error = Signal(Exception)  # custom error signal

    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self):
        try:
            ch = ChatHub(self.state)
            models = ch.list_models()  # blocking sync call
            self.finished.emit(models)
        except Exception as e:
            self.error.emit(e)  # send error to main thread

