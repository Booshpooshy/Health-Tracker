#!/usr/bin/env bash
# Start script for Render deployment

# Initialize database if it doesn't exist
python database.py

# Start the Flask app with gunicorn
gunicorn --bind 0.0.0.0:$PORT app:app 