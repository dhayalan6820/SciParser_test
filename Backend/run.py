import uvicorn
import sys
import os

# Disable browser-use telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "false"

# Add the parent directory to the path to avoid import issues
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import app
import sys
import asyncio

# Force Windows to use ProactorEventLoop to support Playwright subprocesses
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == '__main__':
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        lifespan="on"
    )