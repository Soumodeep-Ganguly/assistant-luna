from enum import Enum
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic.types import SecretStr
from openai import OpenAI
from typing import List
from typing import cast
import ollama

from app.state import AppState

GROQ_API_URL = "https://api.groq.com/openai/v1/"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/"

class Provider(Enum):
    OLLAMA = "Ollama"
    OPENAI = "OpenAI"
    GROQ = "Groq"
    OPEN_ROUTER = "OpenRouter"
    GEMINI = "Gemini"

BASE_URL = {
    Provider.GROQ.value: "https://api.groq.com/openai/v1/",
    Provider.OPEN_ROUTER.value: "https://openrouter.ai/api/v1/"
}

class ChatHub():
    def __init__(self, state: AppState):
        self.provider = state.provider or Provider.OLLAMA
        self.state = state

        api_key = SecretStr(self.state.api_key or "")
        model_name = self.state.model
        api_url = ""

        if self.provider == Provider.OLLAMA:
            self.model = ChatOllama(model=model_name)
            return
        elif self.provider == Provider.GEMINI:
            self.model = ChatGoogleGenerativeAI()
            return
        elif self.provider == Provider.GROQ:
            api_url = GROQ_API_URL
        elif self.provider == Provider.OPEN_ROUTER:
            api_url = OPENROUTER_API_URL
        elif self.provider == Provider.OPENAI:
            api_url = self.state.api_key

        if self.state.model is None:
            return

        self.model = ChatOpenAI(model=self.state.model, api_key=api_key, base_url=api_url)

    def generate(self, messages: list[BaseMessage]):
        res = self.model.invoke(messages)
        return res.content

    def list_models(self):
        if self.provider == Provider.OLLAMA.value:
            ml = ollama.list()
            models = [m.model or "" for m in ml.models]
            return models
        elif self.provider == Provider.GEMINI.value:
            return []
        else:
            base_url = BASE_URL[cast(str, self.provider)]
            api_key = self.state.api_key

            if api_key is None:
                raise ValueError("API Key is invalid")

            client = OpenAI(base_url=base_url, api_key=api_key) 
            ml = client.models.list().data
            models : List[str] = [m.id for m in ml]
            return models

