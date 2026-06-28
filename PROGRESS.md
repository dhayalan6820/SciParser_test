# SciParser AI - Working Progress Documentation

## Project Overview
SciParser AI is an advanced multi-agent system designed for intelligent web navigation, data extraction, and task automation. It combines the power of Large Language Models (LLMs) with real-time browser interaction to execute complex workflows autonomously.

---

## Current Status (as of June 2026)

### 1. Core Architecture
- **Multi-Agent Orchestrator**: Successfully implemented a tiered agent system:
    - **Input Understanding Agent**: Analyzes user intent and determines if a task is ready for execution or needs more info.
    - **Planning Agent (ATAG)**: Generates a step-by-step execution plan.
    - **Execution Agent**: Interacts with the web using `browser-use` and Playwright.
    - **Critic Agent**: Reviews failures and suggests strategy revisions.
- **Database Integration**: MySQL backend using SQLAlchemy (Async) for persistent storage of chat sessions, agent logs, and tool executions.
- **Real-time Communication**: WebSocket-based streaming for live agent thoughts, status updates, and browser frame previews.

### 2. Key Features Implemented
- **Web Automation**: Full integration with `browser-use` for navigating websites, filling forms, and extracting data.
- **MCP (Model Context Protocol)**: Support for MCP tools, allowing the agent to discover and use external tools dynamically.
- **Live Preview**: A "Browser Preview" component in the frontend that shows the agent's current screen in real-time.
- **Agent Reasoning**: Live streaming of the agent's "thoughts" and "plans" to the UI.
- **Authentication**: Secure user sign-up and sign-in using JWT and bcrypt.

### 3. Recent Progress & Fixes
- **Dependency Management**: Updated `requirements.txt` to include all necessary packages (`browser-use`, `PyJWT`, `passlib`, etc.).
- **Database Schema**: Automated database and table creation on startup.
- **Error Handling**: Improved resilience in the execution loop with a Critic-led retry mechanism.
- **Frontend UI**: Developed a modern, responsive dashboard using Shadcn UI and Framer Motion.

---

## Technical Specifications

### Backend (Python/FastAPI)
- **Framework**: FastAPI
- **Agents**: LangChain, LangGraph
- **Automation**: Playwright, browser-use
- **Database**: MySQL (aiomysql)
- **Search**: Tavily API

### Frontend (React/TypeScript)
- **Build Tool**: Vite
- **Styling**: Tailwind CSS, Shadcn UI
- **State Management**: React Context API
- **Animations**: Framer Motion

---

## Known Issues & Roadmap

### Known Issues
- **Token Limits**: Large web pages can sometimes exceed LLM context windows (e.g., Google AI Studio 1M token limit).
- **Browser Path**: Requires manual configuration of the Chrome executable path in `.env`.

### Roadmap
- [ ] **Multi-User Isolation**: Enhance temp directory management for concurrent users.
- [ ] **Advanced Scheduling**: Implement recurring task execution for automated monitoring.
- [ ] **Vision Support**: Improve agent's ability to process complex visual elements on web pages.
- [ ] **Export Options**: Add functionality to export extracted data to CSV/JSON/PDF.

---

## Deployment Progress
- **Local**: Fully functional on Windows/Linux environments.
- **Production**: Backend is ready for ASGI deployment (Uvicorn/Gunicorn). Frontend is ready for static hosting.
- **Docker**: (Planned) Containerization for easier deployment of the full stack.
