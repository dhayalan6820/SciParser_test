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
- **Persistent Storage**: MySQL database for managing chat sessions and execution logs.

## Prerequisites

- **Node.js** (v18+)
- **Python** (3.10+)
- **MySQL** (v8.0+)
- **Google Chrome** (for browser automation)

## Getting Started

### 1. Clone the Repository
```bash
git clone <repository-url>
cd SciParser
```

### 2. Backend Setup
1. Navigate to the Backend directory:
   ```bash
   cd Backend
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Configure environment variables:
   Create a `.env` file in the `Backend/` directory (refer to `.env.example` if available) with the following:
   ```env
   TAVILY_API_KEY=your_tavily_key
   OPENROUTER_API_KEY=your_openrouter_key
   GOOGLE_API_KEY=your_google_key
   DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/sciparser_v1
   JWT_SECRET=your_jwt_secret
   BROWSER_EXECUTABLE_PATH=path_to_chrome_exe
   ```
4. Initialize the database:
   The database is automatically initialized on the first run.
5. Run the backend:
   ```bash
   python run.py
   ```

### 3. Frontend Setup
1. Navigate to the Frontend directory:
   ```bash
   cd ../Frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```

## Deployment

### Backend Deployment
- Use a production-grade ASGI server like `uvicorn` or `gunicorn`.
- Ensure MySQL is accessible and properly configured.
- Install Playwright browsers: `playwright install chromium`.

### Frontend Deployment
- Build the project: `npm run build`.
- Serve the `dist` folder using a static file server (Nginx, Vercel, Netlify).

## License
[MIT License](LICENSE)
