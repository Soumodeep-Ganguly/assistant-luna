# Luna

Luna is a cross-platform voice assistant powered by Ollama, OpenAI, Groq, or OpenRouter. It listens to your commands, speaks back with natural TTS, and can perform actions like opening apps, searching the web, or managing your system. Built with Python, Luna is modular, scalable, and customizable — your personal AI, always ready to help.

## Python 3.10.18

### Create environment with python version

```bash
$ conda create -n kokoro-env python=3.10 -y
```

### Switch on environment

```bash
$ conda activate kokoro-env
```

## Packages Required

- python-dotenv
- kokoro
- soundfile
- sounddevice
- SpeechRecognition
- ollama (Additionally required to keep running: ollama run gemma3:270m)
- openai
- jsonschema
- pyaudio
- playsound
- gtts
- mcp

Or you can just run

```bash
$ pip install -r requirements.txt
```

### Ollama models that can be used

```bash
$ ollama run <model-name>
```

- gemma3:270m
- qwen3:0.6b
- gemma3:1b

```bash
$ ollama stop <model-name>
```

## Environments Keys

- GROQ_API_KEY
- OPENROUTER_API_KEY
- OPENAI_API_KEY
