#!/usr/bin/env python3
"""Crowe Sense as an MCP server, runnable from this checkout with no install:

    python3 ~/crowe-sense/mcp_server.py

Stdlib only. Points at the node named by CROWE_SENSE_URL (direct) or by the file
`crowe sense use` writes. See firmware/crowe/mcp.py for the tools and the rules.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "firmware"))

from crowe.mcp import main  # noqa: E402

if __name__ == "__main__":
    main()
