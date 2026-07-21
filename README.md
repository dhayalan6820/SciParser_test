# SciParser AI

SciParser AI is a sophisticated AI-powered platform designed for automated web navigation, data extraction, and intelligent task execution. It leverages advanced LLMs, browser automation, and a multi-agent architecture to handle complex user requests.

## Project Structure

- **Backend/**: FastAPI-based Python server handling agent logic, database interactions, and browser automation.
- **Frontend/**: React-based web interface built with Vite, Tailwind CSS, and Shadcn UI.

## Features

- **Multi-Agent Architecture**: Uses specialized agents for input understanding, planning, and execution.
- **Browser Automation**: Integrated with `browser-use` and Playwright for real-time web interaction.
- **Intelligent Search**: Powered by Tavily for accurate information retrieval.
- **Real-time Updates**: WebSocket integration for live streaming of agent thoughts and browser frames.
- **Persistent Storage**: PostgreSQL database for managing chat sessions and execution logs.

## Prerequisites

- **Node.js** (v18+)
- **Python** (3.10+)
- **Google Chrome** (for browser automation)
- **PostgreSQL** (v14+)
## Getting Started

### 1. Clone the Repository
```bash
git clone <repository-url>
cd SciParser
```

### 2. Configure Environment Variables
Copy the example file and fill in your real values:
```bash
cp .env.example .env
```

Edit the root `.env` file (single source of truth for both Backend and Frontend):
```env
# Required
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/sciparser_v1
JWT_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
OPENROUTER_API_KEY=your_openrouter_key
# Model assignments
MAIN_MODEL=openai/gpt-4o-mini
BROWSER_USE_MODEL=openai/gpt-4o-mini
LLM_EXTRACTION_MODEL=openai/gpt-4o-mini
# Optional
TAVILY_API_KEY=your_tavily_key
GOOGLE_API_KEY=your_google_key
LANGCHAIN_API_KEY=your_langsmith_key
# Chrome path (for browser automation)
BROWSER_USE_SYSTEM_CHROME=true
BROWSER_EXECUTABLE_PATH=path/to/chrome.exe
```
### 3. Backend Setup
```bash
cd Backend
pip install -r requirements.txt
playwright install chromium --with-deps
python run.py
```
The database is automatically initialized on the first run.
### 4. Frontend Setup
```bash
cd Frontend
npm install
npm run dev
```
The frontend dev server runs at `http://localhost:5000` and proxies `/sciparser/*` requests to the backend at port `8000`.


## Deployment

### Backend
- Set `ENVIRONMENT=production` in `.env`.
- Use `python run.py` or wrap with `uvicorn src.main:app --host 0.0.0.0 --port 8000`.
- Ensure PostgreSQL is accessible and `DATABASE_URL` is set.
- Run `playwright install chromium --with-deps` on the server.
- Set `CORS_ALLOWED_ORIGINS` to your real domain.

### Frontend
- Update `Frontend/.env.production` with your permanent domain URL.
- Build: `npm run build`.
- Serve the `dist/` folder with Nginx, Caddy, or a CDN.

## License
[MIT License](LICENSE)
