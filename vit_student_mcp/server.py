import json
from mcp.server.fastmcp import FastMCP
from vit_student_mcp.database import get_connection, create_tables

# Initialize DB on startup
create_tables()

# Create the MCP server — this name shows up in Claude Desktop
mcp = FastMCP("vit-student-mcp")


# ── TOOL 1: Get All Courses ───────────────────────────────────────────────────
@mcp.tool()
def get_my_courses() -> str:
    """Get all courses I am enrolled in this semester, including faculty, venue, credits and type."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT code, title, type, credits, venue, faculty
        FROM courses
        ORDER BY code
    """).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2)


# ── TOOL 2: Get Timetable ─────────────────────────────────────────────────────
@mcp.tool()
def get_timetable(day: str = None) -> str:
    """
    Get my class schedule.
    Optionally filter by day — pass MON, TUE, WED, THU, or FRI.
    Returns course name, slot, venue, start and end time.
    """
    conn = get_connection()

    if day:
        rows = conn.execute("""
            SELECT c.code, c.title, t.day, t.start_time, t.end_time,
                   c.venue, s.slot AS slot
            FROM timetable t
            JOIN courses c ON c.id = t.course_id
            JOIN slots   s ON s.id = t.slot_id
            WHERE t.day = ?
            ORDER BY t.start_time
        """, (day.upper(),)).fetchall()
    else:
        rows = conn.execute("""
            SELECT c.code, c.title, t.day, t.start_time, t.end_time,
                   c.venue, s.slot AS slot
            FROM timetable t
            JOIN courses c ON c.id = t.course_id
            JOIN slots   s ON s.id = t.slot_id
            ORDER BY
                CASE t.day
                    WHEN 'MON' THEN 1
                    WHEN 'TUE' THEN 2
                    WHEN 'WED' THEN 3
                    WHEN 'THU' THEN 4
                    WHEN 'FRI' THEN 5
                END,
                t.start_time
        """).fetchall()

    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2)


# ── TOOL 3: Get Attendance ────────────────────────────────────────────────────
@mcp.tool()
def get_attendance(at_risk_only: bool = False) -> str:
    """
    Get attendance percentage for all courses.
    Set at_risk_only=True to only show courses below 75% (detention risk).
    Also calculates how many classes need to be attended to reach 75%.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            c.code,
            c.title,
            a.attended,
            a.total,
            a.percentage,
            MAX(0, CAST(CEIL((0.75 * a.total - a.attended) / 0.25) AS INTEGER)) AS classes_needed_for_75
        FROM attendance a
        JOIN courses c ON c.id = a.course_id
        ORDER BY a.percentage ASC
    """).fetchall()
    conn.close()

    data = [dict(r) for r in rows]

    if at_risk_only:
        data = [r for r in data if r["percentage"] < 75]

    for r in data:
        if r["percentage"] >= 75:
            r["status"] = "✅ Safe"
        elif r["percentage"] >= 65:
            r["status"] = "⚠️ Warning"
        else:
            r["status"] = "❌ At Risk"

    return json.dumps(data, indent=2)


# ── TOOL 4: Get Marks ─────────────────────────────────────────────────────────
@mcp.tool()
def get_marks(course_code: str = None, unread_only: bool = False) -> str:
    """
    Get my marks/scores for assessments.
    Optionally filter by course_code (e.g. 'CS3001') or set unread_only=True
    to see only newly released marks I haven't viewed yet.
    Also calculates percentage score per assessment.
    """
    conn = get_connection()

    conditions = []
    params = []

    if course_code:
        conditions.append("c.code = ?")
        params.append(course_code.upper())
    if unread_only:
        conditions.append("m.is_read = 0")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = conn.execute(f"""
        SELECT
            c.code,
            c.title AS course,
            m.title AS assessment,
            m.scored,
            m.max,
            ROUND((m.scored * 100.0) / m.max, 1) AS percentage,
            CASE WHEN m.is_read = 0 THEN 'NEW' ELSE 'Seen' END AS status
        FROM marks m
        JOIN courses c ON c.id = m.course_id
        {where}
        ORDER BY c.code, m.id
    """, params).fetchall()

    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2)


# ── TOOL 5: Get Exam Schedule ─────────────────────────────────────────────────
@mcp.tool()
def get_exam_schedule() -> str:
    """
    Get my full exam schedule including FAT (Final Assessment Test) dates,
    venues, timings and seat numbers for all courses.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            c.code,
            c.title,
            e.title AS exam,
            e.date,
            e.time,
            e.venue,
            e.seat
        FROM exams e
        JOIN courses c ON c.id = e.course_id
        ORDER BY e.date
    """).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2)


# ── TOOL 6: Get Assignments ───────────────────────────────────────────────────
@mcp.tool()
def get_assignments(pending_only: bool = False) -> str:
    """
    Get all Moodle assignments.
    Set pending_only=True to only see assignments not yet submitted.
    Shows due date and submission status for each assignment.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            c.code,
            c.title AS course,
            a.title AS assignment,
            a.due_date,
            CASE WHEN a.submitted = 1 THEN '✅ Submitted' ELSE '⏳ Pending' END AS status
        FROM assignments a
        JOIN courses c ON c.id = a.course_id
        ORDER BY a.due_date
    """).fetchall()
    conn.close()

    data = [dict(r) for r in rows]
    if pending_only:
        data = [r for r in data if r["status"] == "⏳ Pending"]

    return json.dumps(data, indent=2)


# ── TOOL 7: Get Staff / Faculty Info ─────────────────────────────────────────
@mcp.tool()
def get_faculty(course_code: str = None) -> str:
    """
    Get faculty contact details — name, email, and cabin number.
    Optionally filter by course_code (e.g. 'CS3001').
    """
    conn = get_connection()

    if course_code:
        rows = conn.execute("""
            SELECT c.code, c.title, s.name, s.email, s.cabin
            FROM staff s
            JOIN courses c ON c.id = s.course_id
            WHERE c.code = ?
        """, (course_code.upper(),)).fetchall()
    else:
        rows = conn.execute("""
            SELECT c.code, c.title, s.name, s.email, s.cabin
            FROM staff s
            JOIN courses c ON c.id = s.course_id
            ORDER BY c.code
        """).fetchall()

    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2)


# ── TOOL 8: Get Profile ───────────────────────────────────────────────────────
@mcp.tool()
def get_profile() -> str:
    """
    Get student profile — name, CGPA, and total earned credits.
    This data is scraped from VTOP's student profile and grade history pages.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT name, cgpa, total_credits
        FROM profile
        LIMIT 1
    """).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2)


# ── TOOL 9: Academic Dashboard ────────────────────────────────────────────────
@mcp.tool()
def get_dashboard() -> str:
    """
    Get a full academic summary in one shot — profile info, attendance status
    for all courses, unread marks, pending assignments, and upcoming exams.
    This is the best tool to call first for a complete overview.
    """
    conn = get_connection()

    profile = conn.execute("""
        SELECT name, cgpa, total_credits
        FROM profile
        LIMIT 1
    """).fetchall()

    attendance = conn.execute("""
        SELECT c.code, c.title, a.percentage,
            CASE
                WHEN a.percentage >= 75 THEN '✅ Safe'
                WHEN a.percentage >= 65 THEN '⚠️ Warning'
                ELSE '❌ At Risk'
            END AS status
        FROM attendance a
        JOIN courses c ON c.id = a.course_id
        ORDER BY a.percentage ASC
    """).fetchall()

    unread_marks = conn.execute("""
        SELECT c.code, m.title AS assessment, m.scored, m.max
        FROM marks m
        JOIN courses c ON c.id = m.course_id
        WHERE m.is_read = 0
    """).fetchall()

    pending = conn.execute("""
        SELECT c.code, a.title, a.due_date
        FROM assignments a
        JOIN courses c ON c.id = a.course_id
        WHERE a.submitted = 0
        ORDER BY a.due_date
    """).fetchall()

    exams = conn.execute("""
        SELECT c.code, e.title, e.date, e.time, e.venue
        FROM exams e
        JOIN courses c ON c.id = e.course_id
        ORDER BY e.date
    """).fetchall()

    conn.close()

    dashboard = {
        "profile":              [dict(r) for r in profile],
        "attendance":           [dict(r) for r in attendance],
        "unread_marks":         [dict(r) for r in unread_marks],
        "pending_assignments":  [dict(r) for r in pending],
        "upcoming_exams":       [dict(r) for r in exams],
    }
    return json.dumps(dashboard, indent=2)


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    mcp.run()

if __name__ == "__main__":
    main()
