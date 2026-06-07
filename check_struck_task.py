#!/usr/bin/env python3
"""Check if struck task is in database"""
import sqlite3

DB_PATH = r"C:\Users\vibin\AppData\Roaming\Shakshuka\data\shakshuka.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check for struck tasks
cursor.execute("""
    SELECT id, title, struck_today, struck_forever, completed, status 
    FROM tasks 
    WHERE user_id = 'default_user' 
    AND (struck_today = 1 OR struck_forever = 1)
    LIMIT 10
""")

print("Struck tasks in database:")
for row in cursor.fetchall():
    print(f"  ID: {row['id']}")
    print(f"    Title: {row['title']}")
    print(f"    Struck Today: {row['struck_today']}")
    print(f"    Struck Forever: {row['struck_forever']}")
    print(f"    Completed: {row['completed']}")
    print(f"    Status: {row['status']}")
    print()

# Check task count by status
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_count,
        SUM(CASE WHEN struck_today = 1 THEN 1 ELSE 0 END) as struck_today_count,
        SUM(CASE WHEN struck_forever = 1 THEN 1 ELSE 0 END) as struck_forever_count
    FROM tasks
    WHERE user_id = 'default_user'
""")

row = cursor.fetchone()
print(f"Task counts:")
print(f"  Total: {row['total']}")
print(f"  Completed: {row['completed_count']}")
print(f"  Struck Today: {row['struck_today_count']}")
print(f"  Struck Forever: {row['struck_forever_count']}")

conn.close()
