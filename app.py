import os
from flask import Flask, render_template_string, request, redirect, url_for, flash
import psycopg2
import cohere
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Cohere API key
COHERE_API_KEY = "4fKw6r8NGUQh3ilrwCLjUaL06gp0PPZUuzW6tFJM"

# Initialize Cohere client
co = cohere.Client(COHERE_API_KEY)

# Parse database URL
DATABASE_URL = "postgresql://postgres:kvWgDtueoVeTbWzWxmYJFCodUzJuWTrZ@junction.proxy.rlwy.net:52445/railway"
parsed_url = urlparse(DATABASE_URL)
DB_HOST = parsed_url.hostname
DB_PORT = parsed_url.port
DB_NAME = parsed_url.path[1:]  # Remove leading '/'
DB_USER = parsed_url.username
DB_PASSWORD = parsed_url.password


# Database connection utility
def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    return conn


# Initialize the database (create tables if needed)
def initialize_database():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    work_hours VARCHAR(255),
                    sleep_hours VARCHAR(255)
                )
            """)
            conn.commit()


# Initialize database on startup
initialize_database()


# Routes
@app.route('/', methods=['GET', 'POST'])
def home():
    """Login or Register."""
    if request.method == 'POST':
        action = request.form['action']
        username = request.form['username']
        password = request.form['password']

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                if action == 'login':
                    cursor.execute('SELECT password FROM users WHERE username = %s', (username,))
                    user = cursor.fetchone()
                    if user and check_password_hash(user[0], password):
                        return redirect(url_for('dashboard', username=username))
                    else:
                        flash('Invalid username or password.')
                        return redirect(url_for('home'))

                elif action == 'register':
                    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                    if cursor.fetchone():
                        flash('Username already exists. Please choose a different one.')
                        return redirect(url_for('home'))

                    hashed_password = generate_password_hash(password)
                    cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, hashed_password))
                    conn.commit()
                    flash('User registered successfully! Please log in.')
                    return redirect(url_for('home'))

    return render_template_string("""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Login or Register</title>
    </head>
    <body>
        <h1>Welcome to Your Daily Planner</h1>
        <h2>Login or Register</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit" name="action" value="login">Login</button>
            <button type="submit" name="action" value="register">Register</button>
        </form>
        <p> <i>If you register please enter your information then click register, after that an account will be created for you and you may login with it </i> </p>
    </body>
    </html>
    """)


@app.route('/dashboard/<username>', methods=['GET', 'POST'])
def dashboard(username):
    """Dashboard to manage user work and sleep hours."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT work_hours, sleep_hours FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()

    if request.method == 'POST':
        work_hours = request.form['work_hours']
        sleep_hours = request.form['sleep_hours']

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE users SET work_hours = %s, sleep_hours = %s WHERE username = %s',
                               (work_hours, sleep_hours, username))
                conn.commit()
        flash('Information updated successfully!')
        return redirect(url_for('dashboard', username=username))

    return render_template_string("""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Dashboard</title>
    </head>
    <body>
        <h1>Welcome, {{ username }}</h1>
        <form method="POST">
            <label>Work Hours:</label>
            <input type="text" name="work_hours" value="{{ user[0] or '' }}" required>
            <label>Sleep Hours:</label>
            <input type="text" name="sleep_hours" value="{{ user[1] or '' }}" required>
            <button type="submit">Update</button>
        </form>
        <a href="/tasks/{{ username }}">Manage Tasks</a>
    </body>
    </html>
    """, username=username, user=user)


@app.route('/tasks/<username>', methods=['GET', 'POST'])
def tasks(username):
    """Task input and scheduling using Cohere."""
    if request.method == 'POST':
        tasks = request.form['tasks']
        free_time = request.form['free_time']

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT work_hours, sleep_hours FROM users WHERE username = %s', (username,))
                user_data = cursor.fetchone()

        if not user_data:
            flash('User data not found.')
            return redirect(url_for('dashboard', username=username))

        work_hours, sleep_hours = user_data

        response = co.generate(
            model='command-xlarge-nightly',
            prompt=f"Create a schedule based on work hours {work_hours}, sleep hours {sleep_hours}, free time {free_time}, and tasks {tasks}",
            max_tokens=700
        )
        schedule = response.generations[0].text  # Access the first generation's text
        return render_template_string("""
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>AI Schedule</title>
        </head>
        <body>
            <h1>Your AI-Generated Schedule</h1>
            <pre>{{ schedule }}</pre>
            <a href="/">Go to Login and Register Page</a>
        </body>
        </html>
        """, schedule=schedule, username=username)

    return render_template_string("""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Tasks</title>
    </head>
    <body>
        <h1>Enter Your Tasks</h1>
        <form method="POST">
            <textarea name="tasks" placeholder="Enter tasks" required></textarea>
            <input type="text" name="free_time" placeholder="Free time (e.g., 4 PM - 6 PM)" required>
            <button type="submit">Generate Schedule</button>
        </form>
    </body>
    </html>
    """, username=username)


# Run the app
if __name__ == '__main__':
    app.run(debug=True)
