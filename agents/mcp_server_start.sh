#!/bin/bash
export PYTHONPATH="/Users/user/Library/jupyterlab-desktop/jlab_server/lib/python3.12/site-packages"
cd "$(dirname "$0")"
exec /opt/homebrew/bin/python3.12 -u mcp_server.py
