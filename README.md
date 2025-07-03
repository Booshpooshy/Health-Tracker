# Health Tracker

A Flask-based web application for tracking health symptoms and generating insights.

## Features

- User registration and authentication
- Symptom logging with severity tracking
- Dashboard with charts and analytics
- Data export (CSV and PDF)
- Symptom history and patterns analysis

## Local Development

1. Create a virtual environment:
   ```bash
   python -m venv health_tracker_env
   health_tracker_env\Scripts\activate  # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the database:
   ```bash
   python database.py
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Open http://localhost:5000 in your browser

## Deployment

This app is configured for deployment on Render.com. The deployment will automatically:
- Install dependencies from requirements.txt
- Initialize the database
- Start the app with gunicorn

## Environment Variables

- `SECRET_KEY`: Flask secret key for session management 