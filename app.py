
from pathlib import Path
from datetime import date
import hmac
import os
import re
import secrets
import sqlite3

from flask import (
    Flask, request, jsonify, send_from_directory,
    redirect, session, url_for, render_template_string
)

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "driveease.db"

# For deployment, set these environment variables.
app.secret_key = os.environ.get("DRIVEEASE_SECRET_KEY") or secrets.token_hex(32)

ADMIN_PASSWORD = os.environ.get(
    "DRIVEEASE_ADMIN_PASSWORD", "DriveEase@123"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                car_name TEXT NOT NULL,
                pickup_date TEXT NOT NULL,
                return_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = conn.execute(
            "PRAGMA table_info(bookings)"
        ).fetchall()

        column_names = [column["name"] for column in columns]

        if "status" not in column_names:
            conn.execute("""
                ALTER TABLE bookings
                ADD COLUMN status TEXT NOT NULL DEFAULT 'Pending'
            """)


# IMPORTANT: Initialize the database when the app starts,
# including when it starts through Gunicorn on Render.
init_db()


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/style.css")
def stylesheet():
    return send_from_directory(BASE_DIR, "style.css")


@app.route("/script.js")
def javascript():
    return send_from_directory(BASE_DIR, "script.js")


@app.route("/admin", methods=["GET"])
def admin():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    return send_from_directory(BASE_DIR, "admin.html")


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if hmac.compare_digest(password, ADMIN_PASSWORD):
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin"))

        return render_template_string(
            LOGIN_PAGE, error="Incorrect password."
        )

    if session.get("is_admin"):
        return redirect(url_for("admin"))

    return render_template_string(LOGIN_PAGE, error="")


@app.route("/admin-logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


# Only serve approved public website files.
@app.route("/<path:filename>")
def static_files(filename):
    public_files = {"index.html", "style.css", "script.js"}

    if filename in public_files:
        return send_from_directory(BASE_DIR, filename)

    return "Not found", 404


@app.route("/api/cars", methods=["GET"])
def get_cars():
    return jsonify([
        {"name": "Hyundai Creta", "price": 2500, "type": "SUV"},
        {"name": "Maruti Swift", "price": 1500, "type": "Hatchback"},
        {"name": "Honda City", "price": 2200, "type": "Sedan"},
        {"name": "Mahindra Thar", "price": 3500, "type": "SUV"}
    ])


@app.route("/api/bookings", methods=["POST"])
def create_booking():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Invalid request. Please try again."
        }), 400

    name = str(data.get("customerName", "")).strip()
    phone = str(data.get("customerPhone", "")).strip()
    car = str(data.get("carName", "")).strip()
    pickup = str(data.get("pickupDate", "")).strip()
    returning = str(data.get("returnDate", "")).strip()

    if not all([name, phone, car, pickup, returning]):
        return jsonify({
            "error": "Please fill in all fields."
        }), 400

    if len(name) < 2 or len(name) > 100:
        return jsonify({
            "error": "Enter a valid full name."
        }), 400

    if not re.fullmatch(r"[0-9]{10}", phone):
        return jsonify({
            "error": "Enter a valid 10-digit mobile number."
        }), 400

    allowed_cars = {
        "Hyundai Creta",
        "Maruti Swift",
        "Honda City",
        "Mahindra Thar"
    }

    if car not in allowed_cars:
        return jsonify({
            "error": "Please select a valid car."
        }), 400

    try:
        pickup_day = date.fromisoformat(pickup)
        return_day = date.fromisoformat(returning)
    except ValueError:
        return jsonify({
            "error": "Select valid pickup and return dates."
        }), 400

    if pickup_day < date.today():
        return jsonify({
            "error": "Pickup date cannot be in the past."
        }), 400

    if return_day < pickup_day:
        return jsonify({
            "error": "Return date cannot be before pickup."
        }), 400

    try:
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO bookings (
                    customer_name,
                    phone,
                    car_name,
                    pickup_date,
                    return_date,
                    status
                )
                VALUES (?, ?, ?, ?, ?, 'Pending')
            """, (name, phone, car, pickup, returning))

            booking_id = cursor.lastrowid

        return jsonify({
            "message": "Booking saved successfully!",
            "bookingId": booking_id
        }), 201

    except sqlite3.Error:
        app.logger.exception("Database error while saving booking")
        return jsonify({
            "error": "Database error. Please try again."
        }), 500


# Customers must provide both booking ID and registered phone.
@app.route("/api/booking-status", methods=["POST"])
def check_booking_status():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Enter your Booking ID and mobile number."
        }), 400

    try:
        booking_id = int(data.get("bookingId", 0))
    except (ValueError, TypeError):
        return jsonify({
            "error": "Enter a valid Booking ID."
        }), 400

    phone = str(data.get("phone", "")).strip()

    if booking_id < 1 or not re.fullmatch(r"[0-9]{10}", phone):
        return jsonify({
            "error": "Enter a valid Booking ID and 10-digit mobile number."
        }), 400

    try:
        with get_db() as conn:
            booking = conn.execute("""
                SELECT id, car_name, pickup_date, return_date, status
                FROM bookings
                WHERE id = ? AND phone = ?
            """, (booking_id, phone)).fetchone()

        if booking is None:
            return jsonify({
                "error": (
                    "Booking not found. Check your ID and "
                    "registered mobile number."
                )
            }), 404

        return jsonify({
            "bookingId": booking["id"],
            "carName": booking["car_name"],
            "pickupDate": booking["pickup_date"],
            "returnDate": booking["return_date"],
            "status": booking["status"]
        })

    except sqlite3.Error:
        app.logger.exception(
            "Database error while checking booking status"
        )
        return jsonify({
            "error": "Could not check booking status."
        }), 500


# Only a logged-in admin can see all bookings.
@app.route("/api/bookings", methods=["GET"])
def list_bookings():
    if not session.get("is_admin"):
        return jsonify({
            "error": "Admin login required."
        }), 401

    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT id, customer_name, phone, car_name,
                       pickup_date, return_date, created_at, status
                FROM bookings
                ORDER BY id DESC
            """).fetchall()

        return jsonify([dict(row) for row in rows])

    except sqlite3.Error:
        app.logger.exception("Database error while reading bookings")
        return jsonify({
            "error": "Could not load bookings."
        }), 500


# Only the logged-in admin can approve or reject bookings.
@app.route("/api/bookings/<int:booking_id>/status", methods=["PATCH"])
def update_booking_status(booking_id):
    if not session.get("is_admin"):
        return jsonify({
            "error": "Admin login required."
        }), 401

    data = request.get_json(silent=True) or {}
    status = data.get("status")

    if status not in ("Approved", "Rejected"):
        return jsonify({
            "error": "Status must be Approved or Rejected."
        }), 400

    try:
        with get_db() as conn:
            cursor = conn.execute("""
                UPDATE bookings
                SET status = ?
                WHERE id = ?
            """, (status, booking_id))

            if cursor.rowcount == 0:
                return jsonify({
                    "error": "Booking not found."
                }), 404

        return jsonify({
            "message": f"Booking {status.lower()} successfully!",
            "bookingId": booking_id,
            "status": status
        })

    except sqlite3.Error:
        app.logger.exception(
            "Database error while updating booking status"
        )
        return jsonify({
            "error": "Could not update booking status."
        }), 500


LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DriveEase | Admin Login</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: Arial, sans-serif;
      background: #f4f6ef;
      color: #173d2e;
    }
    .login-card {
      width: min(360px, calc(100% - 48px));
      padding: 28px;
      border-radius: 14px;
      background: white;
      box-shadow: 0 8px 30px #0001;
    }
    h1 { margin-top: 0; }
    input, button {
      box-sizing: border-box;
      width: 100%;
      padding: 12px;
      margin-top: 12px;
      border-radius: 7px;
      font-size: 15px;
    }
    input { border: 1px solid #ccd5cb; }
    button {
      border: 0;
      background: #164b38;
      color: white;
      cursor: pointer;
      font-weight: bold;
    }
    .error { color: #b42318; }
  </style>
</head>
<body>
  <main class="login-card">
    <h1>DriveEase Admin</h1>
    <p>Enter the admin password to manage bookings.</p>
    <form method="post" action="/admin-login">
      <label for="password">Admin password</label>
      <input id="password" name="password" type="password"
             autocomplete="current-password" required>
      <button type="submit">Log In</button>
    </form>
    <p class="error">{{ error }}</p>
    <p><a href="/">Back to website</a></p>
  </main>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=True)
