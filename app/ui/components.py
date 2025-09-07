from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap, QTransform
from PySide6.QtWidgets import QLabel

class Loader(QLabel):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.original = QPixmap(path)
        self.angle = 0

        self.setFixedSize(50, 50)  # force a visible area
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotateStep)
        self.timer.start(30)

    def rotateStep(self):
        self.angle = (self.angle + 5) % 360
        transform = QTransform().rotate(self.angle)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        rotated = self.original.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Scale back into the label's fixed size and center it
        self.setPixmap(rotated.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        ))

