import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

def init_database():
    conn = sqlite3.connect('health_tracker.db')
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            first_name TEXT,
            last_name TEXT,
            password_hash TEXT NOT NULL,      
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Symptoms table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS symptoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            category TEXT
        )
    ''')

    # Symptom logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS symptom_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symptom_id INTEGER NOT NULL,
            severity INTEGER NOT NULL CHECK (severity >= 1 AND severity <= 10),
            log_date DATE NOT NULL,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (symptom_id) REFERENCES symptoms(id) ON DELETE CASCADE
        )
    ''')

    # Insert default symptoms
    default_symptoms = [
        ('Headache', 'Pain in the head or neck area', 'physical'),
        ('Nausea', 'Feeling of sickness with urge to vomit', 'digestive'),
        ('Fatigue', 'Extreme tiredness or exhaustion', 'physical'),
        ('Anxiety', 'Feelings of worry or unease', 'mental'),
        ('Back Pain', 'Pain in the back or spine area', 'physical'),
        ('Dizziness', 'Feeling unsteady or lightheaded', 'physical'),
        ('Stomach Pain', 'Pain or discomfort in stomach area', 'digestive'),
        ('Insomnia', 'Difficulty falling or staying asleep', 'physical'),
        ('Mood Changes', 'Unusual changes in emotional state', 'mental'),
        ('Joint Pain', 'Pain in joints or connective areas', 'physical')
    ]
    cursor.executemany('INSERT OR IGNORE INTO symptoms (name, description, category) VALUES (?, ?, ?)', default_symptoms)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_database()
    print("Database created successfully!")