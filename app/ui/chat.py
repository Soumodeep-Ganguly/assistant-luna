from PySide6.QtCore import Qt
from PySide6.QtGui import QWindow
from app.state import AppState
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from app.ui.components import Avatar


class SetupChat():
    def __init__(self, state: AppState):
        self.window = QMainWindow()
        self.container = QWidget()
        self.layout = QVBoxLayout()
        self.window.setCentralWidget(self.container)
        self.container.setLayout(self.layout)
        self.window.setFixedHeight(600)
        self.window.setFixedWidth(600)
        self.window.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.avatar = self.create_avatar()

        self.layout.addWidget(self.avatar)

    def create_avatar(self):
        avatar = Avatar("assets/loading.png")
        return avatar
        
    def show(self):
        self.window.show()
