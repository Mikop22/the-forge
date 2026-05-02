#!/bin/bash
cd "$(dirname "$0")"
exec .venv/bin/python3.12 -u mcp_server.py
