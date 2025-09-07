from PySide6.QtGui import Qt
from PySide6.QtWidgets import QComboBox, QCompleter, QLineEdit, QMainWindow, QProgressDialog, QVBoxLayout, QWidget, QPushButton, QLabel
from app.ai.chat import ChatHub, Provider
from app.state import AppState
from app.ui.components import Loader
from app.ui.helpers import LabelVariants, ModelFetcher
from typing import cast
from PySide6.QtCore import Qt

class SetupWindow():
    def __init__(self, state: AppState):
        self.state = state 
        self.window = QMainWindow()
        self.api_input = None
        self.window.setFixedWidth(400)
        self.window.setFixedHeight(600)
        self.container = QWidget()
        self.layout = QVBoxLayout()
        self.window.setCentralWidget(self.container)
        self.container.setLayout(self.layout)

        self.render()
        self.update_models()


    def render(self):
        heading = QLabel("Configure Luna")
        heading.setProperty("variant", LabelVariants.HEADING.value)
        self.layout.addWidget(heading)

        self.loader = Loader("assets/loading.png")
        self.loader.setParent(self.window)
        self.loader.move((self.window.width()-self.loader.width())//2,
                    (self.window.height()-self.loader.height())//2)
        self.loader.raise_()
        self.loader.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.loader)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #ff0000")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.error_label)
        providers = [member.value for member in Provider]
        provider_input = self._create_combobox("provider","Provider", providers)
        self.layout.addWidget(provider_input)
        self.api_input = self._create_input("api_key", "Api Key", "Enter the API KEY")
        self.api_key_lineinput = None
        self.models_input = self._create_combobox("model", "Model", [])
        self.layout.addWidget(self.api_input)
        self.layout.addWidget(self.models_input)

        if self.state.provider == "Ollama":
            self.api_input.setDisabled(True)

        btn = QPushButton()
        btn.setText("Save")
        btn.clicked.connect(self.handle_save)
        self.layout.addWidget(btn)

    def show(self):
        self.window.show()

    def update_models(self):
        self.model_fetcher = None
        self.loader.show()
        self.error_label.setText("")
        wrapper_layout = cast(QVBoxLayout, self.models_input.layout()) 
        combo_item =  wrapper_layout.itemAt(1)
        combo_widget = cast(QComboBox, combo_item.widget())

        combo_widget.clear()

        def manage_success(models):
            if self.api_key_lineinput:
                self.api_key_lineinput.clear()
            self.loader.hide()
            combo_widget.addItems(models)

        self.fetcher = ModelFetcher(self.state)  # pass the state instance
        self.fetcher.finished.connect(manage_success)
        self.fetcher.error.connect(lambda e: self.error_label.setText(str(e)))
        self.fetcher.finished.connect(self.fetcher.deleteLater)

        self.fetcher.start()

        if self.api_key_lineinput:
            self.api_key_lineinput.setText("")

    def _create_combobox(self, name, label, items, default_value: str | None = None):
        wrapper = QWidget()
        container = QVBoxLayout()
        container.setContentsMargins(0,0,0,10)
        wrapper.setMaximumHeight(70)
        wrapper.setLayout(container)

        
        lbl = QLabel(label)
        combo = QComboBox()
        # combo.setEditable(True)
        # completer = QCompleter(combo.model(), combo)
        # completer.setFilterMode(Qt.MatchFlag.MatchContains)  # search anywhere in text
        # completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        # combo.setCompleter(completer)
        combo.addItems(items)
        if default_value is not None:
            combo.setCurrentIndex(items.index(default_value))
        combo.currentTextChanged.connect(self.handle_change(name))
        container.addWidget(lbl, stretch=0)
        container.addWidget(combo, stretch=0)

        return wrapper

    def handle_save(self):
        self.state.save()

    def _create_input(self, name, label, placeholder):
        wrapper = QWidget()
        container = QVBoxLayout()
        container.setContentsMargins(0,0,0,10)
        wrapper.setMaximumHeight(70)
        wrapper.setLayout(container)

        lbl = QLabel(label)
        self.api_key_lineinput = QLineEdit()
        self.api_key_lineinput.setPlaceholderText(placeholder)
        self.api_key_lineinput.textChanged.connect(self.handle_change(name))

        container.addWidget(lbl, stretch=0)
        container.addWidget(self.api_key_lineinput, stretch=0)

        return wrapper

    def handle_change(self, field_name: str):
        def handler(value: str):
            if field_name == "api_key":
                self.state.set_api_key(value)
                self.update_models()
            elif field_name == "provider":
                self.state.set_provider(value)
                if self.api_input == None:
                    return
                if value != "Ollama":
                    self.api_input.setDisabled(False)
                else:
                    self.api_input.setDisabled(True)
                    self.update_models()

        return handler


