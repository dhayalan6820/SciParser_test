import logging
import sys
import os
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Define a clean, developer-friendly log format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Create formatter
formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

# 1. Console Handler (Prints to terminal)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

# 2. File Handler (Stores in file, rotates at 5MB, keeps 5 backups)
file_handler = RotatingFileHandler(
    "logs/sciparser-log", 
    maxBytes=5 * 1024 * 1024, # 5 MB
    backupCount=5,
    encoding="utf-8"
)
file_handler.setFormatter(formatter)

# Setup the main logger
logger = logging.getLogger("sciparser")
logger.setLevel(logging.INFO)

# Prevent duplicate logs if logger is imported multiple times
if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

# Also configure the root logger to catch uvicorn/fastapi logs
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[console_handler, file_handler]
)
