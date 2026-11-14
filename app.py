# Youssoupha Toure — Imports and Flask Setup
# Flask: Web framework core
# render_template: injects data and serves HTML files from the templates/ folder
# request: reads user inputs sent via HTML forms
# redirect & url_for: utility functions to send users to specific route functions
# session: stores the logged-in user's ID and username across pages
from flask import Flask, render_template, request, redirect, url_for, session

# python library for running SQL queries without external database servers
import sqlite3

# date and calendar utilities for monthly filtering and 6-month chart windows
from datetime import datetime, timedelta
import calendar

# start the Flask web application
app = Flask(__name__)

# secret key used to sign user session cookies
app.secret_key = "cashflow_dev_secret_key"

# the file name where our SQL database stores tables and user data on disk
DB_NAME = "finance.db"


# desmond burnett— database initialization
def init_db():
    """Connects to the database and ensures our 'users', 'transactions', and 'budgets' tables exist."""
    # connection to the SQLite database file (creates it if missing)
    conn = sqlite3.connect(DB_NAME)

    # cursor is our pointer to execute SQL queries
    cursor = conn.cursor()

    # desmond burnett:create the users table if this is the first time running
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

    # seed default demo user account if it does not already exist
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, password)
        VALUES (1, 'demo', 'password123')
    """)

    # Youssoupha Toure :create transactions table isolated by user_id
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # sakin zaman: create budgets table storing custom category caps per user
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            limit_amount REAL NOT NULL,
            UNIQUE(user_id, category),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # saves our schema changes to disk
    conn.commit()

    # close connection to free system resources
    conn.close()


# run table setup immediately on server start so the database is always ready
init_db()


# dashboard data helper 
def get_dashboard_data(user_id, target_year=None, target_month=None):
    """
    Central helper function to calculate metrics, monthly chart data,
    and budget progress strictly isolated to the specified user_id.
    """
    now = datetime.now()
    year = target_year if target_year else now.year
    month = target_month if target_month else now.month

    cur_month_str = f"{year:04d}-{month:02d}"

    # calculate previous month date string (YYYY-MM) for month-over-month comparisons
    prev_dt = datetime(year, month, 1) - timedelta(days=1)
    prev_month_str = f"{prev_dt.year:04d}-{prev_dt.month:02d}"

    # open database connection and configure rows to behave like dictionaries
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Youssoupha Toure: fetch transactions list for the logged-in user
    cursor.execute("""
        SELECT * FROM transactions 
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
    """, (user_id,))
    transactions = cursor.fetchall()

    # John: total balance, monthly income/expenses, trends
    # sum all-time income and expenses for this user to compute overall balance
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN LOWER(type) = 'income' THEN amount ELSE 0 END), 0) AS total_income,
            COALESCE(SUM(CASE WHEN LOWER(type) = 'expense' THEN amount ELSE 0 END), 0) AS total_expense
        FROM transactions
        WHERE user_id = ?
    """, (user_id,))
    totals = cursor.fetchone()
    total_income = totals["total_income"] if totals else 0.0
    total_expense = totals["total_expense"] if totals else 0.0
    total_balance = total_income - total_expense

    # sum income and expenses for the currently selected month
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN LOWER(type) = 'income' THEN amount ELSE 0 END), 0) AS cur_income,
            COALESCE(SUM(CASE WHEN LOWER(type) = 'expense' THEN amount ELSE 0 END), 0) AS cur_expense
        FROM transactions
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
    """, (user_id, cur_month_str))
    cur_m = cursor.fetchone()
    cur_income = cur_m["cur_income"] if cur_m else 0.0
    cur_expense = cur_m["cur_expense"] if cur_m else 0.0
    cur_balance = cur_income - cur_expense

    # sum income and expenses for the previous month to compare against current month
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN LOWER(type) = 'income' THEN amount ELSE 0 END), 0) AS prev_income,
            COALESCE(SUM(CASE WHEN LOWER(type) = 'expense' THEN amount ELSE 0 END), 0) AS prev_expense
        FROM transactions
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
    """, (user_id, prev_month_str))
    prev_m = cursor.fetchone()
    prev_income = prev_m["prev_income"] if prev_m else 0.0
    prev_expense = prev_m["prev_expense"] if prev_m else 0.0
    prev_balance = prev_income - prev_expense

    # helper function to calculate percentage change and up/down arrow indicators
    def calc_trend(current, previous):
        if previous == 0:
            if current > 0:
                return {"arrow": "↗", "pct": "100.0%", "text": "vs. last month", "direction": "up"}
            return {"arrow": "–", "pct": "0.0%", "text": "vs. last month", "direction": "up"}
        diff = ((current - previous) / abs(previous)) * 100
        arrow = "↗" if diff >= 0 else "↘"
        direction = "up" if diff >= 0 else "down"
        return {"arrow": arrow, "pct": f"{abs(diff):.1f}%", "text": "vs. last month", "direction": direction}

    metrics = {
        "balance": total_balance,
        "balance_trend": calc_trend(cur_balance, prev_balance),
        "income": cur_income,
        "income_trend": calc_trend(cur_income, prev_income),
        "expenses": cur_expense,
        "expenses_trend": calc_trend(cur_expense, prev_expense)
    }

    # desmond burnett:income vs expenses bar chart
    # query monthly income and expense totals across the last 6 months
    cursor.execute("""
        SELECT 
            strftime('%Y-%m', date) AS month_key,
            COALESCE(SUM(CASE WHEN LOWER(type) = 'income' THEN amount ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN LOWER(type) = 'expense' THEN amount ELSE 0 END), 0) AS expense
        FROM transactions
        WHERE user_id = ?
          AND date >= date('now', 'start of month', '-5 months')
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month_key ASC
    """, (user_id,))
    db_month_data = {row["month_key"]: (row["income"], row["expense"]) for row in cursor.fetchall()}

    # recursive SQL CTE to build 6 consecutive month labels even when a month has $0
    cursor.execute("""
        WITH RECURSIVE months(m_date, step) AS (
            SELECT date('now', 'start of month', '-5 months'), 0
            UNION ALL
            SELECT date(m_date, '+1 month'), step + 1 FROM months WHERE step < 5
        )
        SELECT 
            strftime('%Y-%m', m_date) AS month_key,
            CASE strftime('%m', m_date)
                WHEN '01' THEN 'Jan' WHEN '02' THEN 'Feb' WHEN '03' THEN 'Mar'
                WHEN '04' THEN 'Apr' WHEN '05' THEN 'May' WHEN '06' THEN 'Jun'
                WHEN '07' THEN 'Jul' WHEN '08' THEN 'Aug' WHEN '09' THEN 'Sep'
                WHEN '10' THEN 'Oct' WHEN '11' THEN 'Nov' ELSE 'Dec'
            END AS label
        FROM months;
    """)
    six_months_keys = cursor.fetchall()

    # find peak monthly dollar amount to scale bar heights proportionally
    peak_value = 0.0
    for row in six_months_keys:
        inc, exp = db_month_data.get(row["month_key"], (0.0, 0.0))
        peak_value = max(peak_value, inc, exp)

    chart_ceiling = max(peak_value * 1.15, 100.0)
    baseline_y = 176
    max_bar_height = 144

    # fixed X-axis coordinates for rendering bars inside the homepage SVG chart
    svg_positions = [
        {"inc_x": 65,  "exp_x": 91,  "label_x": 90},
        {"inc_x": 150, "exp_x": 176, "label_x": 175},
        {"inc_x": 235, "exp_x": 261, "label_x": 260},
        {"inc_x": 320, "exp_x": 346, "label_x": 345},
        {"inc_x": 405, "exp_x": 431, "label_x": 430},
        {"inc_x": 490, "exp_x": 516, "label_x": 515}
    ]

    monthly_chart = []
    for idx, row in enumerate(six_months_keys):
        inc, exp = db_month_data.get(row["month_key"], (0.0, 0.0))
        inc_fill_pct = min(round((inc / chart_ceiling) * 100, 1), 100.0) if inc > 0 else 0
        exp_fill_pct = min(round((exp / chart_ceiling) * 100, 1), 100.0) if exp > 0 else 0
        inc_svg_h = max(int((inc / chart_ceiling) * max_bar_height), 4) if inc > 0 else 0
        exp_svg_h = max(int((exp / chart_ceiling) * max_bar_height), 4) if exp > 0 else 0
        pos = svg_positions[idx] if idx < len(svg_positions) else {"inc_x": 0, "exp_x": 0, "label_x": 0}

        monthly_chart.append({
            "label": row["label"],
            "income": round(inc, 2),
            "expense": round(exp, 2),
            "income_height": inc_fill_pct,
            "expense_height": exp_fill_pct,
            "inc_x": pos["inc_x"],
            "exp_x": pos["exp_x"],
            "label_x": pos["label_x"],
            "inc_y": baseline_y - inc_svg_h,
            "inc_h": inc_svg_h,
            "exp_y": baseline_y - exp_svg_h,
            "exp_h": exp_svg_h
        })

    # sakin zaman: category budgets & progress bar 
    default_limits = {
        "Bills": 1800.0,
        "Food & Groceries": 600.0,
        "Shopping": 350.0
    }

    # fetch any custom category budget caps saved by the user
    cursor.execute("""
        SELECT category, limit_amount 
        FROM budgets 
        WHERE user_id = ?
    """, (user_id,))
    custom_limits = {row["category"]: row["limit_amount"] for row in cursor.fetchall()}

    # sum logged expenses per category for the selected month
    cursor.execute("""
        SELECT category, COALESCE(SUM(amount), 0) AS spent
        FROM transactions
        WHERE user_id = ? 
          AND LOWER(type) = 'expense'
          AND strftime('%Y-%m', date) = ?
        GROUP BY category
    """, (user_id, cur_month_str))
    spent_map = {row["category"]: row["spent"] for row in cursor.fetchall()}

    category_budgets = []
    category_colors = {
        "Bills": "track-bills",
        "Food & Groceries": "track-food light",
        "Shopping": "track-shopping gold"
    }

    for cat, def_limit in default_limits.items():
        limit = custom_limits.get(cat, def_limit)
        spent = spent_map.get(cat, 0.0)
        raw_pct = (spent / limit) * 100 if limit > 0 else 0
        fill_pct = min(raw_pct, 100.0)
        category_budgets.append({
            "name": cat,
            "spent": spent,
            "limit": limit,
            "raw_pct": round(raw_pct, 1),
            "fill_pct": round(fill_pct, 1),
            "is_over": spent > limit,
            "color_class": category_colors.get(cat, "track-bills")
        })

    # close database connection after all queries complete
    conn.close()
    return {
        "transactions": transactions,
        "metrics": metrics,
        "monthly_chart": monthly_chart,
        "category_budgets": category_budgets,
        "year": year,
        "month": month
    }


# routing: home overview
@app.route("/")
def home():
    """Renders the main overview homepage at the base URL (http://127.0.0.1:5000/)."""
    # Ming Gui Xiao: protect route so unauthenticated visitors go to login first
    if not session.get("user_id"):
        return redirect(url_for("auth"))

    # john: read selected year/month period from the dropdown filter
    now = datetime.now()
    period = request.args.get("period")
    if period and "-" in period:
        try:
            year, month = map(int, period.split("-"))
        except ValueError:
            year, month = now.year, now.month
    else:
        year, month = now.year, now.month

    data = get_dashboard_data(session["user_id"], target_year=year, target_month=month)

    # build sorted list of months for the period selector dropdown
    months = []
    base = datetime(year, month, 1)
    for i in range(-6, 7):
        d = base + timedelta(days=31 * i)
        months.append((d.year, d.month, calendar.month_name[d.month]))

    unique_months = []
    seen = set()
    for item in months:
        key = (item[0], item[1])
        if key not in seen:
            seen.add(key)
            unique_months.append(item)
    unique_months.sort(key=lambda x: (x[0], x[1]))

    # Taif: pass metrics, chart data, and budget progress into home.html
    return render_template(
        "home.html",
        metrics=data["metrics"],
        monthly_chart=data["monthly_chart"],
        category_budgets=data["category_budgets"],
        selected_year=year,
        selected_month=month,
        months=unique_months,
        month_name=calendar.month_name[month]
    )


# sakin zaman: form logic
# allows both GET (viewing the webpage) and POST (submitting form data)
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

        # verify neither field is completely blank
        if not username or not password:
            message = "Please fill in all fields."
            status = "error"
        else:
            # open database connection to run queries
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()

            # case 1: user is signing up
            if action == "signup":
                try:
                    # SQL INSERT: parameterized with '?' placeholders to prevent SQL injection
                    cursor.execute(
                        "INSERT INTO users (username, password) VALUES (?, ?)",
                        (username, password),
                    )
                    new_user_id = cursor.lastrowid

                    # seed starter budget limits for the newly registered user
                    default_budgets = [
                        (new_user_id, "Bills", 1800.0),
                        (new_user_id, "Food & Groceries", 600.0),
                        (new_user_id, "Shopping", 350.0)
                    ]
                    cursor.executemany("""
                        INSERT INTO budgets (user_id, category, limit_amount)
                        VALUES (?, ?, ?)
                    """, default_budgets)

                    # commit writes the new account record and default budgets to finance.db
                    conn.commit()
                    message = f"Account '{username}' created successfully! Please log in."
                    status = "success"

                # sqlite3.IntegrityError fires if the username already exists due to UNIQUE constraint
                except sqlite3.IntegrityError:
                    message = "Username already exists. Choose another."
                    status = "error"

            # case 2: user is logging in
            elif action == "login":
                # SQL SELECT: query for a row matching both username and password
                cursor.execute(
                    "SELECT * FROM users WHERE username = ? AND password = ?",
                    (username, password),
                )
                # fetchone() returns the record if found, or None if credentials don't match
                user = cursor.fetchone()

                if user:
                    # Ming Gui Xiao: save user_id and username in session and redirect to homepage
                    session["user_id"] = user[0]
                    session["username"] = user[1]
                    conn.close()
                    return redirect(url_for("home"))
                else:
                    message = "Invalid username or password."
                    status = "error"

            # close database connection after query completes
            conn.close()

    # pass the outcome back to the HTML template to display dynamic alerts
    return render_template("login.html", message=message, status=status)


# Taif:— Logout
@app.route("/logout")
def logout():
    """Clears the active user session and redirects back to the login page."""
    session.clear()
    return redirect(url_for("auth"))


# Routing: Budget Tracker
@app.route("/budget", methods=["GET", "POST"])
@app.route("/dashboard", methods=["GET", "POST"])
def budget():
    """Handles budget goal updates, transaction logging/deletion, and rendering the budget tracker."""
    if not session.get("user_id"):
        return redirect(url_for("auth"))

    current_user_id = session["user_id"]

    # executes when the user submits a transaction, budget update, or delete action
    if request.method == "POST":
        action_type = request.form.get("form_action", "add_transaction")
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # sakin zaman: update category budget Target strictly for current user
        if action_type == "update_budget":
            category = request.form.get("category")
            new_limit_raw = request.form.get("limit_amount")
            if category and new_limit_raw:
                try:
                    new_limit = float(new_limit_raw)
                    cursor.execute("""
                        INSERT INTO budgets (user_id, category, limit_amount)
                        VALUES (?, ?, ?)
                        ON CONFLICT(user_id, category) 
                        DO UPDATE SET limit_amount = excluded.limit_amount
                    """, (current_user_id, category, new_limit))
                    conn.commit()
                except ValueError:
                    pass

        # Youssoupha Toure: Add New Transaction Entry strictly for current user
        elif action_type == "add_transaction":
            amount_raw = request.form.get("amount")
            t_type = request.form.get("type")
            category = request.form.get("category")
            date = request.form.get("date")

            if amount_raw and t_type and category and date:
                try:
                    amount = float(amount_raw)
                    # SQL INSERT: parameterized with '?' placeholders to prevent SQL injection
                    cursor.execute("""
                        INSERT INTO transactions (user_id, amount, type, category, date)
                        VALUES (?, ?, ?, ?, ?)
                    """, (current_user_id, amount, t_type, category, date))
                    conn.commit()
                except Exception as e:
                    print("Insert Error:", e)

        #Delete an Individual Transaction Entry strictly for current user
        elif action_type == "delete_transaction":
            tx_id = request.form.get("transaction_id")
            if tx_id:
                cursor.execute("""
                    DELETE FROM transactions 
                    WHERE id = ? AND user_id = ?
                """, (tx_id, current_user_id))
                conn.commit()

        # Clear All Transactions (Reset Ledger) strictly for current user
        elif action_type == "clear_all_transactions":
            cursor.execute("""
                DELETE FROM transactions 
                WHERE user_id = ?
            """, (current_user_id,))
            conn.commit()

        conn.close()
        period = request.args.get("period")
        if period:
            return redirect(f"{request.path}?period={period}")
        return redirect(request.path)

    # john: dynamic Month selection for GET requests
    now = datetime.now()
    period = request.args.get("period")
    if period and "-" in period:
        try:
            year, month = map(int, period.split("-"))
        except ValueError:
            year, month = now.year, now.month
    else:
        year, month = now.year, now.month

    data = get_dashboard_data(current_user_id, target_year=year, target_month=month)

    months = []
    base = datetime(year, month, 1)
    for i in range(-6, 7):
        d = base + timedelta(days=31 * i)
        months.append((d.year, d.month, calendar.month_name[d.month]))

    unique_months = []
    seen = set()
    for item in months:
        key = (item[0], item[1])
        if key not in seen:
            seen.add(key)
            unique_months.append(item)
    unique_months.sort(key=lambda x: (x[0], x[1]))

    # pass all queried data back to budget.html
    return render_template(
        "budget.html",
        transactions=data["transactions"],
        metrics=data["metrics"],
        category_budgets=data["category_budgets"],
        monthly_chart=data["monthly_chart"],
        selected_year=year,
        selected_month=month,
        months=unique_months,
        month_name=calendar.month_name[month]
    )


# application entry point
if __name__ == "__main__":
    # debug=True automatically reloads the server when app.py edits are saved
    app.run(debug=True)