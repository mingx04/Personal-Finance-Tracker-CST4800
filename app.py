# Youssopha Toure (1-16)
#                      Imports and Setup 
# Flask: Web framework core
# render_template: injects data and serves HTML files from the templates/ folder
# request: reads user inputs sent via HTML forms
# redirect & url_for: utility functions to send users to specific route functions
from flask import Flask, render_template, request, redirect, url_for

# python library for running SQL queries without external database servers
import sqlite3

# start the Flask web application
app = Flask(__name__)

# the file name where our SQL database stores tables and user data on disk
DB_NAME = "finance.db"

#Desmond Burnett (lines:18-55)
#                   database initialization 
def init_db():
    """Connects to the database and ensures our 'users' table exists."""
    # connection to the SQLite database file (creates it if missing)
    conn = sqlite3.connect(DB_NAME)

    # cursor is our pointer to execute SQL queries
    cursor = conn.cursor()

    # SQL DDL: create the users table if this is the first time running
    # - id: Unique auto-incrementing integer identifier
    # - username: TEXT, UNIQUE stops duplicate registrations, NOT NULL enforces required entry
    # - password: TEXT, NOT NULL enforces mandatory password
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # saves our schema changes to disk
    conn.commit()

    # connection to free system resources
    conn.close()


# run table setup immediately on server start so the database is always ready
init_db()


#     routing route : home
@app.route("/")
def home():
    """Redirects the base URL (http://127.0.0.1:5000/) directly to our auth page."""
    return redirect(url_for("auth"))

# Sakin Zaman: 57 to 129 
#           Routing: authentication (SQL & FORM LOGIC) 
# Allows both GET (viewing the webpage) and POST (submitting form data)
@app.route("/auth", methods=["GET", "POST"])
def auth():
    # set response messages as None for default page load
    message = None
    status = None

    # executes only when a user clicks 'Sign Up' or 'Log In' buttons
    if request.method == "POST":
        # read the hidden input 'action' to determine which form triggered the request
        action = request.form.get("action")

        # extract form inputs; .strip() strips leading/trailing blank spaces
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        #  verify neither field is completely blank
        if not username or not password:
            message = "Please fill in all fields."
            status = "error"
        else:
            # open database connection to run queries
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()

            #  case 1: user is signing up
            if action == "signup":
                try:
                    # SQL INSERT: parameterized with '?' placeholders to prevent SQL injection
                    cursor.execute(
                        "INSERT INTO users (username, password) VALUES (?, ?)",
                        (username, password),
                    )
                    # commit writes the new account record to finance.db
                    conn.commit()
                    message = f"Account '{username}' created successfully! Please log in."
                    status = "success"

                # sqlite3.IntegrityError fires if the username already exists due to UNIQUE constraint
                except sqlite3.IntegrityError:
                    message = "Username already exists. Choose another."
                    status = "error"

            #   case 2: user is loggin in
            elif action == "login":
                # SQL SELECT: query for a row matching both username and password
                cursor.execute(
                    "SELECT * FROM users WHERE username = ? AND password = ?",
                    (username, password),
                )
                # fetchone() returns the record if found, or None if credentials don't match
                user = cursor.fetchone()

                if user:
                    message = f"Welcome back, {username}! Login successful."
                    status = "success"
                else:
                    message = "Invalid username or password."
                    status = "error"

            # close database connection after query completes
            conn.close()

    # pass the outcome back to the HTML template to display dynamic alerts
    return render_template("login.html", message=message, status=status)


# application entry point
if __name__ == "__main__":
    # debug=True automatically reloads the server when app.py edits are saved
    app.run(debug=True)