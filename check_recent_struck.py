#!/usr/bin/env python3
"""Check the most recently struck task"""
import sqlite3
from datetime import datetime

DB_PATH = r"C:\Users\vibin\AppData\Roaming\Shakshuka\data\shakshuka.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check for struck tasks TODAY
today = datetime.now().strftime('%Y-%m-%d')
print(f"Looking for tasks struck on {today}...\n")

cursor.execute("""
    SELECT id, title, struck_today, struck_forever, struck_date, completed, status, updated_at
    FROM tasks 
    WHERE user_id = 'default_user' 
    AND struck_today = 1
    ORDER BY updated_at DESC
    LIMIT 10
""")

print("Tasks struck today (struck_today = 1):")
for row in cursor.fetchall():
    print(f"  ID: {row['id']}")
    print(f"    Title: {row['title']}")
    print(f"    Struck Today: {row['struck_today']}")
    print(f"    Struck Forever: {row['struck_forever']}")
    print(f"    Struck Date: {row['struck_date']}")
    print(f"    Completed: {row['completed']}")
    print(f"    Status: {row['status']}")
    print(f"    Updated: {row['updated_at']}")
    print()

conn.close()
