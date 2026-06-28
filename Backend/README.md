# SciParser Backend

The backend of SciParser is a FastAPI application that orchestrates AI agents and browser automation.

## Tech Stack
- **FastAPI**: Web framework.
- **SQLAlchemy**: ORM for MySQL.
- **LangChain & LangGraph**: Agent orchestration.
- **Browser-use & Playwright**: Web automation.
- **Tavily**: Search API.

## Setup

1. **Environment Variables**:
   Ensure your `.env` file is configured with:
   - `DATABASE_URL`: MySQL connection string.
   - `TAVILY_API_KEY`: For web search.
   - `OPENROUTER_API_KEY` or `GOOGLE_API_KEY`: For LLM access.
   - `BROWSER_EXECUTABLE_PATH`: Path to your Chrome/Chromium executable.

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Playwright Setup**:
   ```bash
   playwright install chromium
   ```

4. **Run**:
   ```bash
   python run.py
   ```

## API Documentation
Once running, visit `http://localhost:8000/docs` for the interactive Swagger UI.
