# Interview Agent

## Features

- Browser-native STT/TTS via Web Speech API
- Tiered context memory with sliding window + summarization
- Single-page vanilla JS frontend

## Run

```
echo OPENROUTER_API_KEY=<put your openrouter api key here> > .env
pip install -r requirements.txt
uvicorn main:app
```

## Todo

- [x] Web Speech API integration (STT/TTS)
- [x] LLM question generation with structured output
- [x] LLM answer evaluation with scoring
- [x] Memory summarization for long sessions
- [x] Final summary with fit classification
- [ ] Review panel
- [ ] Multi-language interview support
