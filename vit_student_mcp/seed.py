from database import get_connection, create_tables

def seed():
    create_tables()
    conn = get_connection()

    # ── Courses (realistic VIT Chennai CSE Sem 5) ─────────────────────
    courses = [
        (1, "CS3001", "Computer Networks",          "Theory", 4, "TT303",   "Dr. R. Priya"),
        (2, "CS3002", "Operating Systems",           "Theory", 4, "SJT507",  "Dr. K. Mani"),
        (3, "CS3003", "Database Management Systems", "Theory", 4, "MB118",   "Dr. S. Rao"),
        (4, "CS3004", "Computer Networks Lab",       "Lab",    2, "CB Lab2", "Dr. R. Priya"),
        (5, "CS3005", "Software Engineering",        "Theory", 4, "TT406",   "Dr. P. Singh"),
        (6, "MAT3001", "Probability and Statistics", "Theory", 4, "GDN108",  "Dr. V. Anand"),
    ]
    conn.executemany("INSERT OR REPLACE INTO courses VALUES (?,?,?,?,?,?,?)", courses)

    # ── Slots (VIT slot system) ───────────────────────────────────────
    # (id, slot, course_id) — standalone slots have NULL course_id
    slots = [
        (1,  "A1",    None), (2,  "B1",    None), (3,  "C1",    None),
        (4,  "D1",    None), (5,  "E1",    None), (6,  "A2",    None),
        (7,  "B2",    None), (8,  "C2",    None), (9,  "D2",    None),
        (10, "E2",    None), (11, "L1+L2", None), (12, "L3+L4", None),
        (13, "L5+L6", None),
    ]
    conn.executemany("INSERT OR REPLACE INTO slots VALUES (?,?,?)", slots)

    # ── Timetable ─────────────────────────────────────────────────────
    # (id, course_id, slot_id, day, start_time, end_time)
    timetable = [
        (1,  1, 1,  "MON", "08:00", "08:50"),  # Networks  A1    Mon
        (2,  1, 6,  "WED", "10:00", "10:50"),  # Networks  A2    Wed
        (3,  1, 1,  "FRI", "08:00", "08:50"),  # Networks  A1    Fri
        (4,  2, 2,  "TUE", "09:00", "09:50"),  # OS        B1    Tue
        (5,  2, 7,  "THU", "09:00", "09:50"),  # OS        B2    Thu
        (6,  3, 3,  "MON", "11:00", "11:50"),  # DBMS      C1    Mon
        (7,  3, 8,  "WED", "11:00", "11:50"),  # DBMS      C2    Wed
        (8,  3, 3,  "FRI", "11:00", "11:50"),  # DBMS      C1    Fri
        (9,  4, 11, "TUE", "14:00", "15:50"),  # CN Lab    L1+L2 Tue
        (10, 5, 4,  "THU", "08:00", "08:50"),  # SE        D1    Thu
        (11, 5, 9,  "MON", "14:00", "14:50"),  # SE        D2    Mon
        (12, 6, 5,  "FRI", "10:00", "10:50"),  # Prob&Stat E1    Fri
        (13, 6, 10, "WED", "14:00", "14:50"),  # Prob&Stat E2    Wed
    ]
    conn.executemany("INSERT OR REPLACE INTO timetable VALUES (?,?,?,?,?,?)", timetable)

    # ── Attendance ────────────────────────────────────────────────────
    # (id, course_id, attended, total, percentage)
    attendance = [
        (1, 1, 18, 22, 81),  # Networks  81% ✅ safe
        (2, 2, 12, 20, 60),  # OS        60% ❌ AT RISK
        (3, 3, 19, 22, 86),  # DBMS      86% ✅ safe
        (4, 4,  8, 10, 80),  # CN Lab    80% ✅ safe
        (5, 5, 14, 22, 63),  # SE        63% ❌ AT RISK
        (6, 6, 20, 22, 90),  # Prob&Stat 90% ✅ safe
    ]
    conn.executemany("INSERT OR REPLACE INTO attendance VALUES (?,?,?,?,?)", attendance)

    # ── Marks ─────────────────────────────────────────────────────────
    # (id, course_id, title, scored, max, is_read)
    marks = [
        (1,  1, "CAT 1",        38, 50, 1),
        (2,  1, "CAT 2",        41, 50, 1),
        (3,  2, "CAT 1",        29, 50, 1),
        (4,  2, "CAT 2",        33, 50, 0),  # ← unread!
        (5,  3, "CAT 1",        45, 50, 1),
        (6,  3, "CAT 2",        44, 50, 1),
        (7,  4, "Lab Internal", 36, 50, 1),
        (8,  5, "CAT 1",        25, 50, 1),
        (9,  5, "CAT 2",        31, 50, 0),  # ← unread!
        (10, 6, "CAT 1",        43, 50, 1),
        (11, 6, "CAT 2",        46, 50, 1),
    ]
    conn.executemany("INSERT OR REPLACE INTO marks VALUES (?,?,?,?,?,?)", marks)

    # ── Exams ─────────────────────────────────────────────────────────
    # (id, course_id, title, date, time, venue, seat)
    exams = [
        (1, 1, "FAT", "2026-11-20", "09:00 AM", "CB406",  "VIT-CSE-042"),
        (2, 2, "FAT", "2026-11-22", "09:00 AM", "SJT501", "VIT-CSE-042"),
        (3, 3, "FAT", "2026-11-25", "02:00 PM", "GDN201", "VIT-CSE-042"),
        (4, 5, "FAT", "2026-11-27", "09:00 AM", "TT302",  "VIT-CSE-042"),
        (5, 6, "FAT", "2026-11-28", "02:00 PM", "CB104",  "VIT-CSE-042"),
    ]
    conn.executemany("INSERT OR REPLACE INTO exams VALUES (?,?,?,?,?,?,?)", exams)

    # ── Assignments ───────────────────────────────────────────────────
    # (id, course_id, title, due_date, submitted)
    assignments = [
        (1, 3, "ER Diagram Submission",        "2026-06-10", 1),  # submitted
        (2, 3, "SQL Query Assignment",          "2026-06-18", 0),  # pending ⚠
        (3, 5, "UML Diagram - Use Case",        "2026-06-12", 0),  # pending ⚠
        (4, 5, "Software Requirements Report",  "2026-06-25", 0),  # pending ⚠
        (5, 1, "Subnetting Worksheet",          "2026-06-08", 1),  # submitted
    ]
    conn.executemany("INSERT OR REPLACE INTO assignments VALUES (?,?,?,?,?)", assignments)

    # ── Staff ─────────────────────────────────────────────────────────
    # (id, course_id, name, email, cabin)
    staff = [
        (1, 1, "Dr. R. Priya", "rpriya@vit.ac.in", "SJT 420A"),
        (2, 2, "Dr. K. Mani",  "kmani@vit.ac.in",  "SJT 318B"),
        (3, 3, "Dr. S. Rao",   "srao@vit.ac.in",   "MB 210"),
        (4, 5, "Dr. P. Singh", "psingh@vit.ac.in",  "TT 504"),
        (5, 6, "Dr. V. Anand", "vanand@vit.ac.in",  "GDN 105"),
    ]
    conn.executemany("INSERT OR REPLACE INTO staff VALUES (?,?,?,?,?)", staff)

    # ── Profile ──────────────────────────────────────────────────────
    conn.execute("DELETE FROM profile")
    conn.execute(
        "INSERT INTO profile VALUES (?,?,?,?)",
        (1, "INESH KUMAR", 8.58, 64)
    )

    conn.commit()
    conn.close()
    print("✅ Database seeded with VIT student data!")
    print("   6 courses | 13 slots | 13 timetable entries")
    print("   6 attendance records | 11 marks | 5 exams")
    print("   5 assignments | 5 staff members | 1 profile")

if __name__ == "__main__":
    seed()
