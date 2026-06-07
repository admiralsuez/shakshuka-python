#!/usr/bin/env python3
"""Check where completed tasks are located"""
import sqlite3

DB_PATH = r"C:\Users\vibin\AppData\Roaming\Shakshuka\data\shakshuka.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check completed tasks in active table
cursor.execute('SELECT COUNT(*) as count FROM tasks WHERE completed = 1')
completed_in_tasks = cursor.fetchone()['count']
print(f"Completed tasks in tasks table: {completed_in_tasks}")

# Check archived tasks
cursor.execute('SELECT COUNT(*) as count FROM archived_tasks')
total_archived = cursor.fetchone()['count']
print(f"Total archived tasks: {total_archived}")

# Check completed tasks in archived table
cursor.execute('SELECT COUNT(*) as count FROM archived_tasks WHERE completed = 1')
completed_in_archived = cursor.fetchone()['count']
print(f"Completed tasks in archived_tasks table: {completed_in_archived}")

# Show sample archived tasks
print("\nSample archived tasks (first 5):")
cursor.execute('SELECT id, title, completed_at FROM archived_tasks LIMIT 5')
for row in cursor.fetchall():
    print(f"  {row['id']}: {row['title']} (completed: {row['completed_at']})")

# Check if there are any tasks at all
cursor.execute('SELECT COUNT(*) as count FROM tasks')
total_tasks = cursor.fetchone()['count']
print(f"\nTotal tasks in tasks table: {total_tasks}")

conn.close()
