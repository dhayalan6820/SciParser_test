import logging
import sys

from src.utils.db_log_handler import DatabaseLogHandler

# Define a clean, developer-friendly log format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Create formatter
formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

# 1. Console Handler (Prints to terminal — keeps live workflow log output)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# 2. Database Handler (Persists log records to the `app_logs` table instead
# of a rotating log file — see src/utils/db_log_handler.py for the
# batching/threading design that keeps this non-blocking and crash-safe.)
db_handler = DatabaseLogHandler()

# Setup the main logger
logger = logging.getLogger("sciparser")
logger.setLevel(logging.INFO)

# Prevent duplicate logs if logger is imported multiple times
if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(db_handler)

# Also configure the root logger to catch uvicorn/fastapi logs
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[console_handler, db_handler]
)
