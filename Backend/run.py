import sys
import os

# Fix protobuf/tensorflow "GetPrototype" incompatibility crash
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
# Suppress noisy TensorFlow oneDNN and deprecation warnings
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# Disable browser-use telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "false"

# Add the parent directory to the path to avoid import issues
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from src.main import app
from src import config
import asyncio

# Force Windows to use ProactorEventLoop to support Playwright subprocesses
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == '__main__':
    uvicorn.run(
        "src.main:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=False,
        log_level="info",
        lifespan="on"
    )