"""Vercel serverless entry point for the FastAPI application.

Vercel invokes this module and uses the exported ASGI ``app`` as the handler.
The repository root is added to ``sys.path`` so the ``app`` package resolves
inside the serverless bundle.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.main import app  # noqa: E402

__all__ = ["app"]
