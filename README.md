# Karthik AI

> Personal AI Assistant — Phase 1 Foundation

## Prerequisites

| Tool           | Minimum Version |
|----------------|-----------------|
| Python         | 3.13+           |
| Node.js        | 22+             |
| npm            | 10+             |
| Docker         | 29+             |
| Docker Compose | v5+             |

## Quick Start

### 1. Start the Database

```bash
docker compose -f docker/docker-compose.yml up -d
```

### 2. Start the Backend

```bash
cd backend
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux

uvicorn app.main:app --reload --port 8000
```

### 3. Start the Frontend

```bash
cd frontend
npm install
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux

npm run dev
```

### 4. Verify

| Service          | URL                                    |
|------------------|----------------------------------------|
| Frontend         | http://localhost:5173                   |
| Backend Health   | http://localhost:8000/api/health        |
| Database Health  | http://localhost:8000/api/health/db     |
| API Docs (Swagger) | http://localhost:8000/docs            |

## Project Structure

```
karthik_ai/
├── frontend/          # React + Vite
├── backend/           # Python + FastAPI
├── docker/            # Docker Compose (PostgreSQL + pgvector)
├── docs/              # Documentation
├── uploads/           # File upload storage (gitignored)
├── .env.example       # Environment variable template
└── README.md
```

## License

Private — personal project.
