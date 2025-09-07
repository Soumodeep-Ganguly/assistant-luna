from PySide6.QtWidgets import QApplication
from app.ui.setup import SetupWindow
from app.state import AppState

def main():
    app = QApplication()
    state = AppState()

    with open("style.qss") as f:
        app.setStyleSheet(f.read())

    setup_win = SetupWindow(state)
    setup_win.show()

    app.exec()
    


if __name__ == "__main__":
    main()
