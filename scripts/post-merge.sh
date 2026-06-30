#!/bin/bash
set -e

cd Frontend && npm install --prefer-offline 2>&1 | tail -5

cd ../Backend && python3 -m playwright install chromium 2>&1 | tail -5
