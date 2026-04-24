"""
ISPAS — Smart Procrastination Analysis System
Flask Backend + SQLite Database
"""

from flask import Flask, jsonify, request, render_template, abort
from flask_cors import CORS
import sqlite3
import os
import math
from datetime import datetime, timedelta
import random

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "ispas.db")

# ──────────────────────────────────────────────
#  DATABASE SETUP
# ──────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # dict-like rows
    conn.execute("PRAGMA journal_mode=WAL") # safer concurrent access
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
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
    """Insert realistic demo students + logs if the DB is empty."""
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] > 0:
            return  # already seeded

        demo_students = [
            ("Riya Sharma",    "23001"),
            ("Arjun Mehta",    "23002"),
            ("Priya Kulkarni", "23003"),
            ("Rahul Desai",    "23004"),
            ("Sneha Tiwari",   "23005"),
            ("Amit Joshi",     "23006"),
            ("Kavya Nair",     "23007"),
            ("Rohan Patil",    "23008"),
        ]

        profiles = {
            "23001": dict(study=3.0, social=5.8, stress=7, attend=72, assign=42, task="Social Media"),
            "23002": dict(study=3.5, social=4.9, stress=8, attend=68, assign=55, task="Reading"),
            "23003": dict(study=7.0, social=1.8, stress=3, attend=95, assign=90, task="Project Work"),
            "23004": dict(study=2.5, social=6.1, stress=8, attend=60, assign=38, task="Social Media"),
            "23005": dict(study=6.5, social=2.1, stress=4, attend=92, assign=88, task="Writing"),
            "23006": dict(study=5.0, social=3.2, stress=5, attend=80, assign=72, task="Reading"),
            "23007": dict(study=5.5, social=2.8, stress=5, attend=83, assign=78, task="Project Work"),
            "23008": dict(study=4.0, social=3.8, stress=6, attend=76, assign=65, task="Revision"),
        }

        base_date = datetime.now() - timedelta(days=29)

        for name, roll in demo_students:
            conn.execute("INSERT INTO students (name, roll_number) VALUES (?,?)", (name, roll))
            sid = conn.execute("SELECT id FROM students WHERE roll_number=?", (roll,)).fetchone()[0]
            p   = profiles[roll]
            # 30 days of logs with small noise
            for day in range(30):
                noise = lambda v, r: round(max(0, v + random.uniform(-r, r)), 1)
                conn.execute("""
                    INSERT INTO habit_logs
                    (student_id,study_hours,social_media_hours,stress_level,attendance_pct,assignment_completion,task_type,logged_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    sid,
                    noise(p["study"],  1.5),
                    noise(p["social"], 1.0),
                    max(1, min(10, round(noise(p["stress"], 1)))),
                    max(0, min(100, round(noise(p["attend"], 5)))),
                    max(0, min(100, round(noise(p["assign"], 8)))),
                    p["task"],
                    (base_date + timedelta(days=day)).strftime("%Y-%m-%d %H:%M:%S"),
                ))

        # seed some alerts
        alert_data = [
            (4, "danger", "Social media usage exceeded 6 h today. High risk of academic failure detected."),
            (1, "warn",   "Assignment completion dropped to 42 %. Intervention recommended."),
            (2, "warn",   "Stress level at 8/10 for 3 consecutive days."),
            (3, "info",   "Predicted grade improved to 84. Positive trend detected."),
        ]
        for sid, lvl, msg in alert_data:
            conn.execute("INSERT INTO alerts (student_id,level,message) VALUES (?,?,?)", (sid, lvl, msg))

        print("🌱  Demo data seeded.")


# ──────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────

def compute_risk(social_media_hours, assignment_completion, attendance_pct, study_hours):
    """
    Simple weighted risk score (0–100).
    Higher social media + lower study/assignment/attendance → higher risk.
    """
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
    """Linear regression approximation."""
    grade = (study_hours / 12) * 40 + (attendance_pct / 100) * 30 + (assignment_completion / 100) * 30
    return round(min(100, max(0, grade)), 1)


def generate_alerts(student_id, name, log):
    """Auto-generate alerts based on latest habit log."""
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


# ──────────────────────────────────────────────
#  ROUTES — DASHBOARD
# ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/dashboard", methods=["GET"])
def dashboard_stats():
    """Aggregate stats for the top KPI cards and charts."""
    with get_db() as conn:
        total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]

        # Latest log per student
        latest = conn.execute("""
            SELECT s.id, s.name,
                   hl.study_hours, hl.social_media_hours, hl.stress_level,
                   hl.attendance_pct, hl.assignment_completion, hl.task_type
            FROM students s
            JOIN habit_logs hl ON hl.id = (
                SELECT id FROM habit_logs WHERE student_id = s.id ORDER BY logged_at DESC LIMIT 1
            )
        """).fetchall()

        risks = []
        profiles_count = {"Focused": 0, "Moderate": 0, "Distracted": 0}
        task_dist = {}
        total_social = 0
        total_study  = 0
        total_stress = 0
        total_attend = 0
        total_assign = 0

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

        # Task distribution as percentages
        task_total = sum(task_dist.values()) or 1
        task_pct = {k: round(v / task_total * 100) for k, v in task_dist.items()}

        # Unread alerts
        new_alerts = conn.execute("SELECT COUNT(*) FROM alerts WHERE is_read=0").fetchone()[0]

        return jsonify({
            "total_students":       total_students,
            "avg_social_media":     round(total_social / n, 1),
            "focused_pct":          round(profiles_count["Focused"] / n * 100),
            "at_risk_count":        at_risk,
            "avg_study_hours":      round(total_study  / n, 1),
            "avg_stress":           round(total_stress / n, 1),
            "avg_attendance":       round(total_attend / n),
            "avg_assignment":       round(total_assign / n),
            "profiles":             profiles_count,
            "task_distribution":    task_pct,
            "new_alerts":           new_alerts,
        })


# ──────────────────────────────────────────────
#  ROUTES — STUDENTS
# ──────────────────────────────────────────────

@app.route("/api/students", methods=["GET"])
def list_students():
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
                "id":          r["id"],
                "name":        r["name"],
                "roll_number": r["roll_number"],
                "created_at":  r["created_at"],
                "social_media_hours":    r["social_media_hours"],
                "study_hours":           r["study_hours"],
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
    with get_db() as conn:
        s = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            abort(404, "Student not found")

        logs = conn.execute("""
            SELECT * FROM habit_logs WHERE student_id=? ORDER BY logged_at DESC LIMIT 30
        """, (sid,)).fetchall()

        last = logs[0] if logs else None
        risk  = compute_risk(last["social_media_hours"], last["assignment_completion"],
                             last["attendance_pct"], last["study_hours"]) if last else 0

        return jsonify({
            "id":          s["id"],
            "name":        s["name"],
            "roll_number": s["roll_number"],
            "created_at":  s["created_at"],
            "risk_score":  risk,
            "profile":     compute_profile(risk),
            "predicted_grade": predict_grade(
                last["study_hours"] if last else 0,
                last["attendance_pct"] if last else 0,
                last["assignment_completion"] if last else 0,
            ),
            "logs": [dict(row) for row in logs],
        })


# ──────────────────────────────────────────────
#  ROUTES — HABIT LOGS (Data Entry)
# ──────────────────────────────────────────────

@app.route("/api/logs", methods=["POST"])
def create_log():
    """
    Save a new habit log for a student.
    If the student (by roll_number) doesn't exist, create them first.
    """
    data = request.get_json(force=True)
    required = ["name", "roll_number", "study_hours", "social_media_hours",
                "stress_level", "attendance_pct", "assignment_completion", "task_type"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    with get_db() as conn:
        # Upsert student
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

        # Insert log
        conn.execute("""
            INSERT INTO habit_logs
            (student_id,study_hours,social_media_hours,stress_level,attendance_pct,assignment_completion,task_type)
            VALUES (?,?,?,?,?,?,?)
        """, (
            sid,
            float(data["study_hours"]),
            float(data["social_media_hours"]),
            int(data["stress_level"]),
            int(data["attendance_pct"]),
            int(data["assignment_completion"]),
            data["task_type"],
        ))

        log = {
            "study_hours":           float(data["study_hours"]),
            "social_media_hours":    float(data["social_media_hours"]),
            "stress_level":          int(data["stress_level"]),
            "attendance_pct":        int(data["attendance_pct"]),
            "assignment_completion": int(data["assignment_completion"]),
        }

        # Auto-alerts
        new_alerts = generate_alerts(sid, data["name"], log)
        for a_sid, a_lvl, a_msg in new_alerts:
            conn.execute("INSERT INTO alerts (student_id,level,message) VALUES (?,?,?)",
                         (a_sid, a_lvl, a_msg))

        risk  = compute_risk(log["social_media_hours"], log["assignment_completion"],
                             log["attendance_pct"], log["study_hours"])

        return jsonify({
            "success":       True,
            "student_id":    sid,
            "risk_score":    risk,
            "profile":       compute_profile(risk),
            "predicted_grade": predict_grade(log["study_hours"], log["attendance_pct"],
                                             log["assignment_completion"]),
            "alerts_generated": len(new_alerts),
        }), 201


# ──────────────────────────────────────────────
#  ROUTES — ALERTS
# ──────────────────────────────────────────────

@app.route("/api/alerts", methods=["GET"])
def list_alerts():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT a.*, s.name as student_name, s.roll_number
            FROM alerts a
            LEFT JOIN students s ON s.id = a.student_id
            ORDER BY a.created_at DESC
            LIMIT 50
        """).fetchall()
        return jsonify([dict(r) for r in rows])


@app.route("/api/alerts/<int:aid>/read", methods=["PATCH"])
def mark_alert_read(aid):
    with get_db() as conn:
        conn.execute("UPDATE alerts SET is_read=1 WHERE id=?", (aid,))
        return jsonify({"success": True})


# ──────────────────────────────────────────────
#  ROUTES — RISK MONITOR (table on dashboard)
# ──────────────────────────────────────────────

@app.route("/api/risk-monitor", methods=["GET"])
def risk_monitor():
    """Top 10 students sorted by risk score descending."""
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


# ──────────────────────────────────────────────
#  ROUTES — TREND DATA (for charts)
# ──────────────────────────────────────────────

@app.route("/api/trends", methods=["GET"])
def trends():
    """Last 30 days aggregate daily averages."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT DATE(logged_at) as day,
                   ROUND(AVG(study_hours),2)           as avg_study,
                   ROUND(AVG(social_media_hours),2)    as avg_social,
                   ROUND(AVG(stress_level),1)           as avg_stress,
                   ROUND(AVG(attendance_pct),1)         as avg_attend,
                   ROUND(AVG(assignment_completion),1)  as avg_assign,
                   COUNT(DISTINCT student_id)            as students_logged
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
