#!/usr/bin/env python3
"""Run this to see exactly what is in your DB right now."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_connection

conn = get_connection()
cur = conn.cursor()

print("\n=== COURSES ===")
for r in cur.execute("SELECT id, code, title, type, credits, venue, faculty FROM courses"):
    print(f"  [{r[0]}] {r[1]} — {r[2]} ({r[3]}) | {r[4]} cr | {r[5]} | {r[6]}")

print("\n=== SLOTS ===")
for r in cur.execute("SELECT s.slot, c.code, c.title FROM slots s JOIN courses c ON c.id = s.course_id"):
    print(f"  {r[0]} → {r[1]} {r[2]}")

print("\n=== ATTENDANCE ===")
for r in cur.execute("""
    SELECT c.code, c.title, a.attended, a.total, a.percentage
    FROM attendance a JOIN courses c ON c.id = a.course_id
"""):
    print(f"  {r[0]} {r[1]}: {r[2]}/{r[3]} = {r[4]}%")

print("\n=== MARKS ===")
marks = cur.execute("SELECT * FROM marks LIMIT 5").fetchall()
print(f"  {len(marks)} marks records (showing first 5): {marks}")

print("\n=== EXAMS ===")
exams = cur.execute("SELECT * FROM exams LIMIT 5").fetchall()
print(f"  {len(exams)} exam records (showing first 5): {exams}")

conn.close()
