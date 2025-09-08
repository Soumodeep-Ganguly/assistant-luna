from PySide6.QtCore import QRect, QTimer, Qt, QPoint
from PySide6.QtGui import QColor, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import QLabel
import math

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

class Avatar(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scale = 1.0
        self.reverse = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setBrush(QColor("#007acc"))
        painter.setPen(Qt.PenStyle.NoPen)

        radius = 70*self.scale*math.sin(self.scale)


        mid_x = self.width()/2
        mid_y = self.height()/2
        topleft = QPoint(math.ceil(mid_x-radius), math.ceil(mid_y-radius))
        bottom_right = QPoint(math.ceil(mid_x+radius), math.ceil(mid_y+radius))

        size = QRect(topleft, bottom_right)

        painter.drawEllipse(size)
        painter.drawText(QRect(10, 10, 100, 30), "Listening...")



        self.timer = QTimer(self)
        self.timer.timeout.connect(self.timed_scale)
        self.timer.start(10)

    def timed_scale(self):
        if self.reverse == True:
            self.scale += 0.000002
        else:
            self.scale -= 0.000002

        if self.scale < 0.8:
            self.reverse = True
        elif self.scale > 0.99:
            self.reverse = False

        self.update()



