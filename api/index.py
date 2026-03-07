"""
Vercel entrypoint — re-exports the FastAPI app from src/api/server.py
"""
import sys
import os

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from api.server import app
