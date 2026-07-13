# Backend — Personal Agentic AI Assistant

This directory contains the Python-based FastAPI backend foundation for the local Personal Agentic AI Assistant.

## Prerequisites
- **Python**: Version 3.12 (preferred for library compatibility and binary wheels).
- **Environment**: Windows, Linux, or macOS.

---

## Getting Started

### 1. Virtual Environment Setup
Create and activate the virtual environment in the `backend` directory:

```bash
# In backend/ directory
py -3.12 -m venv .venv
```

Activate the environment:
- **Windows (PowerShell)**:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```

### 2. Dependency Installation
Upgrade pip and install the required library packages:

```bash
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the `.env.example` file to create a local `.env` configuration file:

- **Windows (PowerShell)**:
  ```powershell
  Copy-Item .env.example .env
  ```
- **macOS / Linux (Bash)**:
  ```bash
  cp .env.example .env
  ```

The server default values are optimized for local development:
```ini
APP_NAME="Personal Agentic AI Assistant"
APP_VERSION="0.1.0"
APP_ENV="development"
DEBUG=true
API_V1_PREFIX="/api/v1"
HOST="127.0.0.1"
PORT=8000
DATABASE_URL="sqlite:///./data/assistant.db"
LOG_LEVEL="INFO"
```

---

## Running the Server

Start the Uvicorn ASGI server using:

```bash
# From the backend directory
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

- **API Base URL**: `http://127.0.0.1:8000`
- **Health Check Endpoint**: `http://127.0.0.1:8000/api/v1/health`
- **Interactive Swagger Documentation**: `http://127.0.0.1:8000/docs`
- **Alternative Redoc Documentation**: `http://127.0.0.1:8000/redoc`

---

## Running the Tests

Verify database connectivity and API route handlers:

```bash
# From the backend directory
.\.venv\Scripts\pytest -v
```

This commands executes the unit tests inside the `tests` directory against a temporary SQLite test database (`test_assistant.db`) which is automatically created and cleaned up after execution.

---

## Backend Directory Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── dependencies.py      # Dependency injection providers (e.g. DB sessions)
│   │   └── routes/
│   │       └── health.py        # Dynamic system health checks
│   ├── core/
│   │   ├── config.py            # Pydantic Settings management
│   │   ├── constants.py         # Static system configuration fallback values
│   │   ├── exceptions.py        # Centralized exception models and handlers
│   │   └── logging.py           # Clean console stream formatting logger setup
│   └── database/
│       ├── database.py          # SQLAlchemy engine, session maker, base mapper
│       └── models.py            # SQLite verification schemas
├── data/                        # Contains SQLite .db engine files
├── tests/                       # Pytest unit-test suites
├── .env.example                 # Example template for configurations
├── pytest.ini                   # Configuration rules for Pytest
└── requirements.txt             # Pinned package dependencies list
```

---

## Phase 3 — Conversations & WebSockets

### 1. Conversation Database Models
- **`conversations`**: Stores session metadata (`id`, `title`, `created_at`, `updated_at`).
- **`messages`**: Stores message turns (`id`, `conversation_id`, `role`, `content`, `created_at`). Cascades delete on conversation removal. SQLite foreign key pragmas are enabled on connect.

### 2. REST API Endpoints
- **Create Session**: `POST /api/v1/conversations` (takes optional title)
- **List Sessions**: `GET /api/v1/conversations` (returns paginated lists sorted by active updates)
- **Retrieve History**: `GET /api/v1/conversations/{id}` (returns metadata and chronological message history)
- **Rename Session**: `PATCH /api/v1/conversations/{id}` (renames the title manually)
- **Delete Session**: `DELETE /api/v1/conversations/{id}` (removes conversation and cascades message deletion)
- **Send Message**: `POST /api/v1/conversations/{id}/messages` (adds user message, processes non-streaming LLM response)

### 3. WebSocket Real-Time Chat
- **Endpoint**: `WS /api/v1/ws/chat/{conversation_id}`
- **Protocol**:
  - **Client to Server**:
    - Send Message: `{"type": "message.send", "data": {"content": "Your prompt content here"}}`
  - **Server to Client**:
    - Connection Ready: `{"type": "connection.ready", "data": {"conversation_id": "UUID"}}`
    - User Message Saved: `{"type": "message.user.saved", "data": {"message_id": "UUID"}}`
    - Response Started: `{"type": "response.started", "data": {"provider": "ollama", "model": "llama3.2"}}`
    - Response Chunk: `{"type": "response.chunk", "data": {"content": "Token"}}`
    - Response Completed: `{"type": "response.completed", "data": {"message_id": "UUID", "content": "Full response text"}}`
    - Error Event: `{"type": "error", "data": {"code": "ERROR_CODE", "message": "Description"}}`

### 4. Context Management & Trimming
- **Trimming default values**: `MAX_CONTEXT_MESSAGES=20`, `MAX_CONTEXT_CHARS=12000`
- **Rules**: System prompt and newest user message are always preserved. History is filled back-to-front (newest history turns first) until limits are reached, maintaining chronological sorting.

### 5. Executing Tests
- **Run Mocked/Local Unit Tests (Ollama offline)**:
  ```bash
  .\.venv\Scripts\pytest -v -m "not integration"
  ```
- **Run Live Ollama Integration Tests (Ollama online)**:
  ```bash
  .\.venv\Scripts\pytest -v -m "integration"
  ```
- **Run Live Conversation & WS Verification Runner**:
  ```bash
  .\.venv\Scripts\python tests/test_live_conversation.py
  ```

