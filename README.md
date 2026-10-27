# Karthik AI

> A personal, context-aware AI assistant for learning, projects, documents, and placement preparation.

Karthik AI combines structured personal data with document search and conversational AI to provide grounded answers about a user's profile, skills, projects, resume, placement drives, and interview preparation. It is built with React, FastAPI, PostgreSQL, and pgvector.

## What it can do

- Maintain a personal profile, skills, projects, certifications, and career goals.
- Upload and search personal documents using semantic retrieval and citations.
- Continue multi-turn conversations with profile and document context.
- Track placement drives, deadlines, eligibility, skill matches, and priorities.
- Compare a candidate profile with a placement opportunity and generate preparation plans.
- Optimize resume content and support mock interview preparation.
- Return explicit `UNKNOWN` or insufficient-data results instead of guessing.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, Vite 6 |
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL 16 with pgvector |
| Retrieval | FastEmbed embeddings and document chunking |
| Local LLM | Ollama (configurable provider/model) |
| Documents | PDF, DOCX, and PPTX parsing |

## Requirements

| Tool           | Minimum Version |
|----------------|-----------------|
| Python         | 3.13+           |
| Node.js        | 22+             |
| npm            | 10+             |
| Docker         | 29+             |
| Docker Compose | v5+             |
| Ollama | Optional, for local LLM responses |

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/kxrtik250/Karthik-AI.git
cd Karthik-AI
```

### 2. Start PostgreSQL and Ollama

```bash
docker compose -f docker/docker-compose.yml up -d
```

To use the local Ollama container, pull the configured model:

```bash
docker exec -it karthik_ai_ollama ollama pull llama3.2:1b
```

### 3. Start the backend

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux

uvicorn app.main:app --reload --port 8000
```

### 4. Start the frontend

```bash
cd frontend
npm install
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux

npm run dev
```

Open the web app at [http://localhost:5173](http://localhost:5173).

## Service URLs

| Service          | URL                                    |
|------------------|----------------------------------------|
| Web app | http://localhost:5173 |
| API health | http://localhost:8000/api/health |
| Database health | http://localhost:8000/api/health/db |
| Interactive API docs | http://localhost:8000/docs |

## Configuration

Copy each `.env.example` file to `.env` before starting its service. Key settings include `DATABASE_URL`, `VITE_API_URL`, `LLM_PROVIDER`, `OLLAMA_MODEL`, `EMBEDDING_MODEL_NAME`, and `RAG_TOP_K`.

Never commit real `.env` files or API keys; they are ignored by default.

## Development commands

Build the frontend:

```bash
cd frontend
npm run build
```

Run backend tests:

```bash
cd backend
pytest
```

## Project Structure

```
karthik_ai/
├── frontend/          # React + Vite web application
├── backend/           # FastAPI API, services, migrations, and tests
├── docker/            # PostgreSQL/pgvector and Ollama services
├── docs/              # Architecture and feature documentation
├── uploads/           # Local uploads (contents are gitignored)
├── .env.example       # Environment variable template
└── README.md
```

## Documentation

- [Architecture](docs/architecture.md)
- [Database schema](docs/database-schema.md)
- [Document pipeline](docs/document-pipeline.md)
- [RAG pipeline](docs/rag-pipeline.md)
- [Personal context](docs/personal-context.md)
- [Placement intelligence](docs/placement-intelligence.md)

## Project status

Karthik AI is an actively developed personal project. APIs and database schemas may evolve as new assistant, retrieval, resume, and placement features are added.

## License

Private — personal project.
