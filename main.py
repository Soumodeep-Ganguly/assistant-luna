from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication
from app.ui.chat import SetupChat
from app.ui.setup import SetupWindow
from app.state import AppState

def main():
    app = QApplication()
    state = AppState()

    with open("style.qss") as f:
        app.setStyleSheet(f.read())

    if state.provider == None:
        setup_win = SetupWindow(state)
        setup_win.show()
    else:
        chat_ui = SetupChat(state)
        chat_ui.show()

    app.exec()

if __name__ == "__main__":
    main()
