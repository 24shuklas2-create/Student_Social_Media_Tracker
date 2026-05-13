"""
ISPAS — Smart Procrastination Analysis System
Flask Backend + SQLite Database + Login System
"""

from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime, timedelta
import random
import hashlib

app = Flask(__name__)
app.secret_key = "ispas-secret-2026-rbu"
CORS(app, supports_credentials=True)

DB_PATH = os.path.join(os.path.dirname(__file__), "ispas.db")

# ──────────────────────────────────────────────
#  DATABASE SETUP
# ──────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL UNIQUE,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL CHECK(role IN ('admin','student')),
            student_id  INTEGER REFERENCES students(id),
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS students (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            roll_number     TEXT    NOT NULL UNIQUE,
            created_at      TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS habit_logs (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id              INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            study_hours             REAL    NOT NULL CHECK(study_hours BETWEEN 0 AND 24),
            social_media_hours      REAL    NOT NULL CHECK(social_media_hours BETWEEN 0 AND 24),
            stress_level            INTEGER NOT NULL CHECK(stress_level BETWEEN 1 AND 10),
            attendance_pct          INTEGER NOT NULL CHECK(attendance_pct BETWEEN 0 AND 100),
            assignment_completion   INTEGER NOT NULL CHECK(assignment_completion BETWEEN 0 AND 100),
            task_type               TEXT    NOT NULL DEFAULT 'Reading',
            logged_at               TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  INTEGER REFERENCES students(id) ON DELETE CASCADE,
            level       TEXT NOT NULL CHECK(level IN ('danger','warn','info')),
            message     TEXT NOT NULL,
            is_read     INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_logs_student ON habit_logs(student_id);
        CREATE INDEX IF NOT EXISTS idx_alerts_student ON alerts(student_id);
        """)
    print("✅  Database initialised:", DB_PATH)


def seed_demo_data():
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] > 0:
            return

        # 50 realistic students from B.Tech CSE (AI & Data Science), RBU Nagpur
        demo_students = [
            ("Riya Sharma",         "23001"), ("Arjun Mehta",          "23002"),
            ("Priya Kulkarni",      "23003"), ("Rahul Desai",          "23004"),
            ("Sneha Tiwari",        "23005"), ("Amit Joshi",           "23006"),
            ("Kavya Nair",          "23007"), ("Rohan Patil",          "23008"),
            ("Ananya Singh",        "23009"), ("Vikas Yadav",          "23010"),
            ("Pooja Iyer",          "23011"), ("Siddharth Rao",        "23012"),
            ("Neha Gupta",          "23013"), ("Kunal Verma",          "23014"),
            ("Ishita Banerjee",     "23015"), ("Aditya Kumar",         "23016"),
            ("Shruti Mishra",       "23017"), ("Yash Pandey",          "23018"),
            ("Divya Reddy",         "23019"), ("Nikhil Chavan",        "23020"),
            ("Ankita Bhatt",        "23021"), ("Harsh Agarwal",        "23022"),
            ("Simran Kaur",         "23023"), ("Pranav Doshi",         "23024"),
            ("Meera Pillai",        "23025"), ("Akash Dubey",          "23026"),
            ("Tanvi Shah",          "23027"), ("Gaurav Saxena",        "23028"),
            ("Pallavi Jain",        "23029"), ("Rishabh Srivastava",   "23030"),
            ("Nidhi Choudhary",     "23031"), ("Varun Malhotra",       "23032"),
            ("Sakshi Tripathi",     "23033"), ("Karan Bhatia",         "23034"),
            ("Lavanya Menon",       "23035"), ("Shubham Tiwari",       "23036"),
            ("Ritika Patel",        "23037"), ("Mohit Sharma",         "23038"),
            ("Deepika Naidu",       "23039"), ("Ajay Rathore",         "23040"),
            ("Swati Ghosh",         "23041"), ("Sameer Ansari",        "23042"),
            ("Bhavna Solanki",      "23043"), ("Tushar Pawar",         "23044"),
            ("Kajal Thakur",        "23045"), ("Omkar Hegde",          "23046"),
            ("Shraddha Kulkarni",   "23047"), ("Vishal Bhosale",       "23048"),
            ("Preeti Wagh",         "23049"), ("Saurabh Gaikwad",      "23050"),
        ]

        # Realistic habit profiles: (study, social_media, stress, attendance, assignment, task)
        base_profiles = [
            (3.0, 5.8, 7, 72, 42, "Social Media"),   # distracted
            (3.5, 4.9, 8, 68, 55, "Reading"),         # distracted
            (7.0, 1.8, 3, 95, 90, "Project Work"),    # focused
            (2.5, 6.1, 8, 60, 38, "Social Media"),    # distracted
            (6.5, 2.1, 4, 92, 88, "Writing"),         # focused
            (5.0, 3.2, 5, 80, 72, "Reading"),         # moderate
            (5.5, 2.8, 5, 83, 78, "Project Work"),    # moderate
            (4.0, 3.8, 6, 76, 65, "Revision"),        # moderate
            (6.8, 1.5, 3, 94, 91, "Project Work"),    # focused
            (2.0, 7.0, 9, 55, 30, "Social Media"),    # distracted
            (6.2, 2.3, 4, 89, 85, "Reading"),         # focused
            (4.5, 4.0, 6, 78, 68, "Revision"),        # moderate
            (3.2, 5.5, 7, 70, 48, "Social Media"),    # distracted
            (5.8, 2.5, 4, 86, 80, "Writing"),         # focused
            (4.2, 3.5, 5, 79, 70, "Reading"),         # moderate
            (7.2, 1.2, 2, 97, 95, "Project Work"),    # focused
            (2.8, 6.5, 8, 62, 40, "Social Media"),    # distracted
            (5.3, 3.0, 5, 82, 74, "Revision"),        # moderate
            (6.0, 2.0, 3, 91, 87, "Writing"),         # focused
            (3.8, 4.5, 6, 74, 60, "Reading"),         # moderate
            (1.5, 8.0, 9, 50, 25, "Social Media"),    # distracted
            (5.5, 2.8, 4, 84, 76, "Project Work"),    # moderate
            (7.5, 1.0, 2, 98, 96, "Project Work"),    # focused
            (3.0, 6.0, 8, 65, 44, "Social Media"),    # distracted
            (6.3, 2.2, 3, 90, 86, "Reading"),         # focused
            (4.8, 3.6, 6, 77, 66, "Revision"),        # moderate
            (2.2, 7.2, 9, 58, 32, "Social Media"),    # distracted
            (5.7, 2.6, 4, 85, 79, "Writing"),         # moderate
            (6.9, 1.6, 3, 93, 89, "Project Work"),    # focused
            (3.5, 5.0, 7, 71, 52, "Reading"),         # distracted
            (4.3, 4.2, 6, 75, 63, "Revision"),        # moderate
            (6.6, 1.9, 3, 92, 88, "Writing"),         # focused
            (2.7, 6.3, 8, 63, 41, "Social Media"),    # distracted
            (5.1, 3.3, 5, 81, 73, "Reading"),         # moderate
            (7.1, 1.4, 2, 96, 93, "Project Work"),    # focused
            (3.3, 5.2, 7, 69, 47, "Social Media"),    # distracted
            (4.9, 3.7, 6, 78, 67, "Revision"),        # moderate
            (6.4, 2.1, 3, 90, 84, "Writing"),         # focused
            (2.3, 6.8, 9, 57, 33, "Social Media"),    # distracted
            (5.6, 2.9, 5, 83, 77, "Project Work"),    # moderate
            (4.1, 4.3, 6, 73, 61, "Reading"),         # moderate
            (6.7, 1.7, 3, 91, 86, "Project Work"),    # focused
            (3.1, 5.6, 8, 66, 43, "Social Media"),    # distracted
            (5.2, 3.1, 5, 82, 75, "Revision"),        # moderate
            (7.3, 1.1, 2, 97, 94, "Writing"),         # focused
            (2.6, 6.6, 8, 61, 39, "Social Media"),    # distracted
            (5.9, 2.4, 4, 88, 83, "Reading"),         # focused
            (4.4, 4.1, 6, 76, 64, "Project Work"),    # moderate
            (3.6, 4.8, 7, 72, 50, "Reading"),         # distracted
            (6.1, 2.2, 4, 89, 85, "Writing"),         # focused
        ]

        base_date = datetime.now() - timedelta(days=29)
        tasks = ["Reading", "Writing", "Project Work", "Revision", "Social Media"]

        for i, (name, roll) in enumerate(demo_students):
            conn.execute("INSERT INTO students (name, roll_number) VALUES (?,?)", (name, roll))
            sid = conn.execute("SELECT id FROM students WHERE roll_number=?", (roll,)).fetchone()[0]
            p = base_profiles[i]
            study, social, stress, attend, assign, task = p

            for day in range(30):
                def noise(v, r): return round(max(0, v + random.uniform(-r, r)), 1)
                conn.execute("""
                    INSERT INTO habit_logs
                    (student_id,study_hours,social_media_hours,stress_level,attendance_pct,assignment_completion,task_type,logged_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    sid,
                    noise(study, 1.5),
                    noise(social, 1.0),
                    max(1, min(10, round(noise(stress, 1)))),
                    max(0, min(100, round(noise(attend, 5)))),
                    max(0, min(100, round(noise(assign, 8)))),
                    random.choice(tasks) if day % 5 == 0 else task,
                    (base_date + timedelta(days=day)).strftime("%Y-%m-%d %H:%M:%S"),
                ))

        # Auto-generate alerts for high-risk students
        high_risk_alerts = [
            (4,  "danger", "Social media usage exceeded 6h. High risk of academic failure."),
            (1,  "warn",   "Assignment completion dropped to 42%. Intervention recommended."),
            (2,  "warn",   "Stress level at 8/10 for 3 consecutive days."),
            (10, "danger", "Social media usage at 7h/day. Immediate counselling advised."),
            (13, "warn",   "Attendance below 75%. At risk of detention."),
            (17, "danger", "Assignment completion critically low at 25%."),
            (21, "danger", "Social media 8h/day. Academic failure risk very high."),
            (24, "warn",   "Stress level critically high. Counselling recommended."),
            (27, "danger", "Attendance 58% — below minimum threshold."),
            (3,  "info",   "Predicted grade improved to 84. Positive trend detected."),
            (5,  "info",   "Consistent study pattern. Grade prediction: 88."),
            (16, "info",   "Top performer this week. Keep it up!"),
        ]
        for sid, lvl, msg in high_risk_alerts:
            conn.execute("INSERT INTO alerts (student_id,level,message) VALUES (?,?,?)", (sid, lvl, msg))

        # Seed admin user
        conn.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)",
                     ("admin", hash_pw("admin123"), "admin"))

        # Seed one student user per student (roll number = username, roll+123 = password)
        for name, roll in demo_students:
            sid = conn.execute("SELECT id FROM students WHERE roll_number=?", (roll,)).fetchone()[0]
            conn.execute("INSERT INTO users (username,password,role,student_id) VALUES (?,?,?,?)",
                         (roll, hash_pw(roll + "123"), "student", sid))

        print("🌱  Demo data seeded — 50 students, 1500 habit logs, 12 alerts.")
        print("   Admin login   → username: admin   password: admin123")
        print("   Student login → username: 23001   password: 23001123  (roll + 123)")


# ──────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────

def compute_risk(social_media_hours, assignment_completion, attendance_pct, study_hours):
    risk = (
        (social_media_hours / 12) * 40 +
        ((100 - assignment_completion) / 100) * 30 +
        ((100 - attendance_pct) / 100) * 20 +
        (max(0, 6 - study_hours) / 6) * 10
    )
    return round(min(100, max(0, risk)))


def compute_profile(risk_score):
    if risk_score >= 65:
        return "Distracted"
    elif risk_score <= 35:
        return "Focused"
    return "Moderate"


def predict_grade(study_hours, attendance_pct, assignment_completion):
    grade = (study_hours / 12) * 40 + (attendance_pct / 100) * 30 + (assignment_completion / 100) * 30
    return round(min(100, max(0, grade)), 1)


def generate_alerts(student_id, name, log):
    alerts = []
    if log["social_media_hours"] >= 5:
        alerts.append((student_id, "danger",
                        f"Social media usage reached {log['social_media_hours']:.1f} h. High risk detected."))
    if log["assignment_completion"] < 50:
        alerts.append((student_id, "warn",
                        f"Assignment completion dropped to {log['assignment_completion']}%. Intervention recommended."))
    if log["stress_level"] >= 8:
        alerts.append((student_id, "warn",
                        f"Stress level at {log['stress_level']}/10. Counselling advised."))
    return alerts


def require_login():
    """Returns (user_dict, error_response) — check error_response first."""
    if "user_id" not in session:
        return None, (jsonify({"error": "Not logged in", "redirect": "/"}), 401)
    return session, None


def require_admin():
    user, err = require_login()
    if err:
        return None, err
    if user.get("role") != "admin":
        return None, (jsonify({"error": "Admin only"}), 403)
    return user, None


# ──────────────────────────────────────────────
#  AUTH ROUTES
# ──────────────────────────────────────────────

@app.route("/")
def index():
    html_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    with open(html_file, encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, hash_pw(password))
        ).fetchone()

    if not user:
        return jsonify({"error": "Invalid username or password"}), 401

    session["user_id"]    = user["id"]
    session["username"]   = user["username"]
    session["role"]       = user["role"]
    session["student_id"] = user["student_id"]

    # Get student name if student role
    student_name = None
    if user["role"] == "student" and user["student_id"]:
        with get_db() as conn:
            s = conn.execute("SELECT name FROM students WHERE id=?", (user["student_id"],)).fetchone()
            if s:
                student_name = s["name"]

    return jsonify({
        "success":      True,
        "role":         user["role"],
        "username":     user["username"],
        "student_id":   user["student_id"],
        "student_name": student_name,
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/me", methods=["GET"])
def me():
    """Return current session info — used on page refresh."""
    if "user_id" not in session:
        return jsonify({"logged_in": False}), 200

    student_name = None
    if session.get("role") == "student" and session.get("student_id"):
        with get_db() as conn:
            s = conn.execute("SELECT name FROM students WHERE id=?", (session["student_id"],)).fetchone()
            if s:
                student_name = s["name"]

    return jsonify({
        "logged_in":    True,
        "role":         session["role"],
        "username":     session["username"],
        "student_id":   session.get("student_id"),
        "student_name": student_name,
    })


# ──────────────────────────────────────────────
#  ADMIN — DASHBOARD & AGGREGATE ROUTES
# ──────────────────────────────────────────────

@app.route("/api/dashboard", methods=["GET"])
def dashboard_stats():
    user, err = require_login()
    if err: return err

    with get_db() as conn:
        total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        latest = conn.execute("""
            SELECT s.id, s.name,
                   hl.study_hours, hl.social_media_hours, hl.stress_level,
                   hl.attendance_pct, hl.assignment_completion, hl.task_type
            FROM students s
            JOIN habit_logs hl ON hl.id = (
                SELECT id FROM habit_logs WHERE student_id = s.id ORDER BY logged_at DESC LIMIT 1
            )
        """).fetchall()

        risks, profiles_count = [], {"Focused": 0, "Moderate": 0, "Distracted": 0}
        task_dist = {}
        total_social = total_study = total_stress = total_attend = total_assign = 0

        for row in latest:
            r = compute_risk(row["social_media_hours"], row["assignment_completion"],
                             row["attendance_pct"], row["study_hours"])
            p = compute_profile(r)
            profiles_count[p] += 1
            risks.append(r)
            total_social += row["social_media_hours"]
            total_study  += row["study_hours"]
            total_stress += row["stress_level"]
            total_attend += row["attendance_pct"]
            total_assign += row["assignment_completion"]
            task_dist[row["task_type"]] = task_dist.get(row["task_type"], 0) + 1

        n = len(latest) or 1
        at_risk = sum(1 for r in risks if r >= 65)
        task_total = sum(task_dist.values()) or 1
        task_pct = {k: round(v / task_total * 100) for k, v in task_dist.items()}
        new_alerts = conn.execute("SELECT COUNT(*) FROM alerts WHERE is_read=0").fetchone()[0]

        return jsonify({
            "total_students":    total_students,
            "avg_social_media":  round(total_social / n, 1),
            "focused_pct":       round(profiles_count["Focused"] / n * 100),
            "at_risk_count":     at_risk,
            "avg_study_hours":   round(total_study  / n, 1),
            "avg_stress":        round(total_stress / n, 1),
            "avg_attendance":    round(total_attend / n),
            "avg_assignment":    round(total_assign / n),
            "profiles":          profiles_count,
            "task_distribution": task_pct,
            "new_alerts":        new_alerts,
        })


@app.route("/api/students", methods=["GET"])
def list_students():
    user, err = require_login()
    if err: return err

    with get_db() as conn:
        rows = conn.execute("""
            SELECT s.id, s.name, s.roll_number, s.created_at,
                   hl.study_hours, hl.social_media_hours, hl.stress_level,
                   hl.attendance_pct, hl.assignment_completion, hl.task_type
            FROM students s
            LEFT JOIN habit_logs hl ON hl.id = (
                SELECT id FROM habit_logs WHERE student_id=s.id ORDER BY logged_at DESC LIMIT 1
            )
            ORDER BY s.name
        """).fetchall()

        students = []
        for r in rows:
            risk = compute_risk(r["social_media_hours"] or 0, r["assignment_completion"] or 0,
                                r["attendance_pct"] or 0, r["study_hours"] or 0)
            students.append({
                "id":                    r["id"],
                "name":                  r["name"],
                "roll_number":           r["roll_number"],
                "created_at":            r["created_at"],
                "social_media_hours":    r["social_media_hours"],
                "study_hours":           r["study_hours"],
                "stress_level":          r["stress_level"],
                "attendance_pct":        r["attendance_pct"],
                "assignment_completion": r["assignment_completion"],
                "task_type":             r["task_type"],
                "risk_score":            risk,
                "profile":               compute_profile(risk),
                "predicted_grade":       predict_grade(
                    r["study_hours"] or 0,
                    r["attendance_pct"] or 0,
                    r["assignment_completion"] or 0,
                ),
            })
        return jsonify(students)


@app.route("/api/students/<int:sid>", methods=["GET"])
def get_student(sid):
    user, err = require_login()
    if err: return err

    # Students can only view their own data
    if session.get("role") == "student" and session.get("student_id") != sid:
        return jsonify({"error": "Access denied"}), 403

    with get_db() as conn:
        s = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            return jsonify({"error": "Student not found"}), 404

        logs = conn.execute("""
            SELECT * FROM habit_logs WHERE student_id=? ORDER BY logged_at DESC LIMIT 30
        """, (sid,)).fetchall()

        last = logs[0] if logs else None
        risk = compute_risk(last["social_media_hours"], last["assignment_completion"],
                            last["attendance_pct"], last["study_hours"]) if last else 0

        return jsonify({
            "id":            s["id"],
            "name":          s["name"],
            "roll_number":   s["roll_number"],
            "created_at":    s["created_at"],
            "risk_score":    risk,
            "profile":       compute_profile(risk),
            "predicted_grade": predict_grade(
                last["study_hours"] if last else 0,
                last["attendance_pct"] if last else 0,
                last["assignment_completion"] if last else 0,
            ),
            "logs": [dict(row) for row in logs],
        })


# ──────────────────────────────────────────────
#  STUDENT — OWN DATA ROUTES
# ──────────────────────────────────────────────

@app.route("/api/my/dashboard", methods=["GET"])
def my_dashboard():
    """Student's own dashboard data."""
    user, err = require_login()
    if err: return err

    sid = session.get("student_id")
    if not sid:
        return jsonify({"error": "No student profile linked"}), 400

    with get_db() as conn:
        s = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        logs = conn.execute("""
            SELECT * FROM habit_logs WHERE student_id=? ORDER BY logged_at DESC LIMIT 30
        """, (sid,)).fetchall()

        if not logs:
            return jsonify({"name": s["name"], "roll_number": s["roll_number"],
                            "no_data": True})

        last = logs[0]
        risk = compute_risk(last["social_media_hours"], last["assignment_completion"],
                            last["attendance_pct"], last["study_hours"])

        # 7-day averages
        recent = logs[:7]
        avg = lambda key: round(sum(r[key] for r in recent) / len(recent), 1)

        return jsonify({
            "name":                  s["name"],
            "roll_number":           s["roll_number"],
            "risk_score":            risk,
            "profile":               compute_profile(risk),
            "predicted_grade":       predict_grade(last["study_hours"], last["attendance_pct"],
                                                   last["assignment_completion"]),
            "study_hours":           last["study_hours"],
            "social_media_hours":    last["social_media_hours"],
            "stress_level":          last["stress_level"],
            "attendance_pct":        last["attendance_pct"],
            "assignment_completion": last["assignment_completion"],
            "task_type":             last["task_type"],
            "avg_study_7d":          avg("study_hours"),
            "avg_social_7d":         avg("social_media_hours"),
            "avg_stress_7d":         avg("stress_level"),
            "avg_attend_7d":         avg("attendance_pct"),
            "avg_assign_7d":         avg("assignment_completion"),
            "logs":                  [dict(r) for r in logs[:10]],
        })


@app.route("/api/my/alerts", methods=["GET"])
def my_alerts():
    """Student's own alerts only."""
    user, err = require_login()
    if err: return err

    sid = session.get("student_id")
    if not sid:
        return jsonify([])

    with get_db() as conn:
        rows = conn.execute("""
            SELECT a.*, s.name as student_name, s.roll_number
            FROM alerts a
            LEFT JOIN students s ON s.id = a.student_id
            WHERE a.student_id = ?
            ORDER BY a.created_at DESC LIMIT 30
        """, (sid,)).fetchall()
        return jsonify([dict(r) for r in rows])


# ──────────────────────────────────────────────
#  HABIT LOGS
# ──────────────────────────────────────────────

@app.route("/api/logs", methods=["POST"])
def create_log():
    user, err = require_login()
    if err: return err

    data = request.get_json(force=True)

    # Students can only log for themselves
    if session.get("role") == "student":
        sid = session.get("student_id")
        with get_db() as conn:
            s = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
            if not s:
                return jsonify({"error": "Student profile not found"}), 404
            data["name"]        = s["name"]
            data["roll_number"] = s["roll_number"]

    required = ["name", "roll_number", "study_hours", "social_media_hours",
                "stress_level", "attendance_pct", "assignment_completion", "task_type"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    with get_db() as conn:
        existing = conn.execute("SELECT id FROM students WHERE roll_number=?",
                                (data["roll_number"],)).fetchone()
        if existing:
            sid = existing["id"]
            conn.execute("UPDATE students SET name=? WHERE id=?", (data["name"], sid))
        else:
            conn.execute("INSERT INTO students (name, roll_number) VALUES (?,?)",
                         (data["name"], data["roll_number"]))
            sid = conn.execute("SELECT id FROM students WHERE roll_number=?",
                               (data["roll_number"],)).fetchone()["id"]

        conn.execute("""
            INSERT INTO habit_logs
            (student_id,study_hours,social_media_hours,stress_level,attendance_pct,assignment_completion,task_type)
            VALUES (?,?,?,?,?,?,?)
        """, (sid, float(data["study_hours"]), float(data["social_media_hours"]),
              int(data["stress_level"]), int(data["attendance_pct"]),
              int(data["assignment_completion"]), data["task_type"]))

        log = {
            "study_hours":           float(data["study_hours"]),
            "social_media_hours":    float(data["social_media_hours"]),
            "stress_level":          int(data["stress_level"]),
            "attendance_pct":        int(data["attendance_pct"]),
            "assignment_completion": int(data["assignment_completion"]),
        }
        new_alerts = generate_alerts(sid, data["name"], log)
        for a_sid, a_lvl, a_msg in new_alerts:
            conn.execute("INSERT INTO alerts (student_id,level,message) VALUES (?,?,?)",
                         (a_sid, a_lvl, a_msg))

        risk = compute_risk(log["social_media_hours"], log["assignment_completion"],
                            log["attendance_pct"], log["study_hours"])

        return jsonify({
            "success":          True,
            "student_id":       sid,
            "risk_score":       risk,
            "profile":          compute_profile(risk),
            "predicted_grade":  predict_grade(log["study_hours"], log["attendance_pct"],
                                              log["assignment_completion"]),
            "alerts_generated": len(new_alerts),
        }), 201


# ──────────────────────────────────────────────
#  ALERTS
# ──────────────────────────────────────────────

@app.route("/api/alerts", methods=["GET"])
def list_alerts():
    user, err = require_login()
    if err: return err

    with get_db() as conn:
        rows = conn.execute("""
            SELECT a.*, s.name as student_name, s.roll_number
            FROM alerts a
            LEFT JOIN students s ON s.id = a.student_id
            ORDER BY a.created_at DESC LIMIT 50
        """).fetchall()
        return jsonify([dict(r) for r in rows])


@app.route("/api/alerts/<int:aid>/read", methods=["PATCH"])
def mark_alert_read(aid):
    user, err = require_login()
    if err: return err

    with get_db() as conn:
        conn.execute("UPDATE alerts SET is_read=1 WHERE id=?", (aid,))
        return jsonify({"success": True})


# ──────────────────────────────────────────────
#  RISK MONITOR & TRENDS (admin)
# ──────────────────────────────────────────────

@app.route("/api/risk-monitor", methods=["GET"])
def risk_monitor():
    user, err = require_login()
    if err: return err

    with get_db() as conn:
        rows = conn.execute("""
            SELECT s.id, s.name, s.roll_number,
                   hl.study_hours, hl.social_media_hours, hl.stress_level,
                   hl.attendance_pct, hl.assignment_completion, hl.task_type
            FROM students s
            JOIN habit_logs hl ON hl.id = (
                SELECT id FROM habit_logs WHERE student_id=s.id ORDER BY logged_at DESC LIMIT 1
            )
        """).fetchall()

        result = []
        for r in rows:
            risk = compute_risk(r["social_media_hours"], r["assignment_completion"],
                                r["attendance_pct"], r["study_hours"])
            result.append({
                "id":                 r["id"],
                "name":               r["name"],
                "roll_number":        r["roll_number"],
                "social_media_hours": r["social_media_hours"],
                "profile":            compute_profile(risk),
                "risk_score":         risk,
            })

        result.sort(key=lambda x: x["risk_score"], reverse=True)
        return jsonify(result[:10])


@app.route("/api/trends", methods=["GET"])
def trends():
    user, err = require_login()
    if err: return err

    with get_db() as conn:
        rows = conn.execute("""
            SELECT DATE(logged_at) as day,
                   ROUND(AVG(study_hours),2)          as avg_study,
                   ROUND(AVG(social_media_hours),2)   as avg_social,
                   ROUND(AVG(stress_level),1)          as avg_stress,
                   ROUND(AVG(attendance_pct),1)        as avg_attend,
                   ROUND(AVG(assignment_completion),1) as avg_assign,
                   COUNT(DISTINCT student_id)           as students_logged
            FROM habit_logs
            WHERE logged_at >= datetime('now','-30 days')
            GROUP BY DATE(logged_at)
            ORDER BY day
        """).fetchall()
        return jsonify([dict(r) for r in rows])


# ──────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    seed_demo_data()
    print("🚀  ISPAS running at http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)