from PySide6.QtCore import QSettings

class AppState():
    def __init__(self):
        self.settings = QSettings("Luna", "Luna")

        self.api_key = self.settings.value("api_key")
        self.provider = self.settings.value("provider") or "Ollama"
        self.model = self.settings.value("model")

    def set_api_key(self, key: str):
        self.api_key = key

    def set_provider(self, provider: str):
        self.provider = provider

    def set_model(self, model: str):
        self.model = model

    def save(self):
        self.settings.setValue("provider", self.provider)
        self.settings.setValue("api_key", self.api_key)
        self.settings.setValue("model", self.model)
