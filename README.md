# TRD — Trading Research & Development

AI-powered tools for Indian market analysis and simulation.

## Projects

### [God's Eye](./gods-eye/) — Multi-Agent Market Simulation

A real-time Indian stock market simulation powered by 6 AI agents that analyze markets from different perspectives (technical, fundamental, sentiment, algorithmic, macro, and options flow), then debate and reach consensus on market direction.

**Stack:** FastAPI + React + SQLite + LLM APIs (Claude/OpenAI/Gemini)

[Get started →](./gods-eye/README.md)

### [God's Eye UI Prototypes](./gods-eye-ui/)

HTML mockups for the God's Eye interface — 7 screens covering the full user flow from welcome to settings.

## Quick Start

```bash
cd gods-eye

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your LLM API key
python -m uvicorn run:app --reload

# Frontend (new terminal)
cd frontend
npm install
cp .env.example .env
npm run dev
```

Or with Docker:

```bash
cd gods-eye
cp .env.example .env  # Add your LLM API key
docker compose up --build
```

## Documentation

| Doc | Description |
|-----|-------------|
| [SETUP.md](./gods-eye/SETUP.md) | Detailed setup guide |
| [DEPLOYMENT.md](./gods-eye/DEPLOYMENT.md) | Docker deployment guide |
| [CHANGELOG.md](./gods-eye/CHANGELOG.md) | Version history |
| [QA_REPORT.md](./gods-eye/QA_REPORT.md) | Test results & security audit |

## License

Private — All rights reserved.
