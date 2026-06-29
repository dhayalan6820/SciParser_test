#!/bin/bash
set -e

cd Frontend && npm install --prefer-offline 2>&1 | tail -5
