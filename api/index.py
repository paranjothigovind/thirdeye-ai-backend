"""Vercel serverless function entry point"""
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the FastAPI app
from app.main import app

# Export the app for Vercel
app = app
