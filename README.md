# 🔒 Firewall LLM

A security-focused AI gateway that intercepts, inspects, and filters LLM interactions through a multi-layer protection pipeline. Built as a college project (VIT, Winter Semester 2025–26).

---

## 📌 Overview

Firewall LLM acts as a reverse proxy between users and large language models (Gemini, Mistral, etc.), enforcing security policies at every layer:

| Layer | Component | Role |
|-------|-----------|------|
| 1 | **PII Scanner** (Presidio) | Detects and anonymises personal data before it reaches the LLM |
| 2 | **Gatekeeper** (LLaMA Guard 3) | Classifies prompts as safe/unsafe using a local Ollama model |
| 3 | **Token Vault** (Redis) | Replaces sensitive tokens with reversible synthetic placeholders |
| 4 | **Semantic Cache** (sentence-transformers) | Returns cached responses for semantically similar queries |

---

## 🗂️ Project Structure

```
college project 2026/
├── backend/                  # FastAPI application
│   ├── main.py               # App entry point + auth routes
│   ├── database.py           # MySQL + MongoDB helpers
│   ├── firewall.py           # Core 4-layer pipeline
│   ├── config.py             # Pydantic settings (reads .env)
│   ├── dependencies.py       # JWT auth utilities
│   ├── routers/
│   │   ├── chat.py           # POST /api/v1/chat
│   │   └── policies.py       # Policy CRUD endpoints
│   └── services/
│       ├── llm_service.py    # Gemini / Ollama abstraction
│       ├── presidio_service.py
│       ├── embedding_service.py
│       └── redis_service.py
├── frontend-react/           # Next.js 16 + React 19 dashboard
│   ├── app/                  # App Router pages
│   ├── components/           # Sidebar, widgets, UI primitives
│   ├── lib/                  # API client, Zustand stores, types
│   └── hooks/
├── frontend/                 # Legacy Streamlit UI (app.py)
├── tests/                    # Pytest test suite
├── docs/                     # Report + poster HTML files
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── start.sh                  # Linux/macOS startup script
└── start.ps1                 # Windows PowerShell startup script
```

---

## ⚙️ Technology Stack

### Backend
- **FastAPI** — async REST API framework
- **MySQL** — user accounts, logs, policies
- **MongoDB** — conversation history
- **Redis** — token vault + semantic cache
- **Presidio** — PII detection and anonymisation (spaCy `en_core_web_lg`)
- **Ollama** — local LLM inference (LLaMA Guard 3, Mistral)
- **Google Gemini** — primary LLM via `google-generativeai`
- **JWT** — stateless authentication (`python-jose`)

### Frontend
- **Next.js 16** + **React 19** (App Router, TypeScript)
- **Tailwind CSS 4**
- **Recharts** — traffic visualisation
- **Framer Motion** — animations
- **Zustand** — state management

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- MySQL running locally
- MongoDB running locally
- Redis running locally
- [Ollama](https://ollama.com) installed with models pulled:
  ```bash
  ollama pull llama-guard-3-8b
  ollama pull mistral
  ```

### 1 — Clone & configure

```bash
git clone https://github.com/raghavkhandelwal7944/collegeproject2026.git
cd "collegeproject2026"

# Create your environment file
cp .env.example .env
# Edit .env and fill in MYSQL_PASSWORD and GEMINI_API_KEY
```

### 2 — Backend setup

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

# Download spaCy model (one-time)
python -m spacy download en_core_web_lg

# Start the API server
uvicorn backend.main:app --reload --port 8000
```

### 3 — Frontend setup

```bash
cd frontend-react
npm install
npm run dev        # http://localhost:3000
```

### Quick start scripts

```bash
# Windows
.\start.ps1

# Linux / macOS
./start.sh
```

---

## 🔑 Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Description |
|----------|-------------|
| `MYSQL_HOST` | MySQL host (default: `localhost`) |
| `MYSQL_PORT` | MySQL port (default: `3306`) |
| `MYSQL_USERNAME` | MySQL username |
| `MYSQL_PASSWORD` | MySQL password |
| `MYSQL_DATABASE` | Database name |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GATEKEEPER_MODEL_NAME` | Ollama model for Layer 2 (default: `llama-guard-3-8b`) |
| `MAIN_MODEL_NAME` | Primary Ollama model (default: `mistral:latest`) |
| `LLM_REQUEST_TIMEOUT_S` | Seconds to wait for LLM inference (default: `300`) |

> ⚠️ Never commit your `.env` file. It is listed in `.gitignore`.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 📄 Documentation

Full project report and poster are available in the `docs/` folder:

- `docs/vit_report_part1.html` — Chapters 1–3 (Introduction, Literature Survey, System Design)
- `docs/vit_report_part2.html` — Chapters 4–8 (Implementation, Testing, Results, Conclusion)
- `docs/project_poster.html` — A4 conference poster (VIT format)

---

## 👤 Author

**Raghav Khandelwal** — 22BCE3356  
VIT Vellore | Winter Semester 2025–26  
Guide: Prof. Swarnalatha P 

---

## 📜 License

This project is for academic purposes only.
