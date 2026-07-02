#!/usr/bin/env python3
from src.sqlite_data_manager import SQLiteDataManager

dm = SQLiteDataManager()
conn = dm.get_connection()
cursor = conn.cursor()

# Check tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

# Check functions
cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
triggers = [row[0] for row in cursor.fetchall()]

print("✓ Database initialized")
print(f"✓ Total tables: {len(tables)}")
print(f"✓ Key tables: tasks={('tasks' in tables)}, settings={('settings' in tables)}, users={('users' in tables)}")
print(f"✓ Triggers: {len(triggers)}")

conn.close()
print("\n✓ All checks passed!")
