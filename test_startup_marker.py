#!/usr/bin/env python3
"""
Add a startup test marker to see if the startup checker runs
"""

import sqlite3
from datetime import datetime

def main():
    print("🧪 Adding startup test marker...")
    
    # Database path
    db_path = 'C:/Users/vibin/AppData/Roaming/Shakshuka/data/shakshuka.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add a test task with a special title that includes timestamp
        test_timestamp = datetime.now().isoformat()
        test_title = f"STARTUP_TEST_MARKER_{test_timestamp}"
        
        # Insert test task with struck_today = 1
        cursor.execute("""
            INSERT INTO tasks (id, user_id, title, struck_today, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            f"startup-test-{test_timestamp.replace(':', '-')}",
            "default_user",
            test_title,
            1,  # struck_today = 1
            test_timestamp
        ))
        
        conn.commit()
        print(f"✅ Added test task: {test_title}")
        print("📋 Now restart the app and check if this task gets refreshed_at added")
        
        # Show current state
        cursor.execute("""
            SELECT title, struck_today, refreshed_at 
            FROM tasks 
            WHERE title LIKE 'STARTUP_TEST_MARKER%'
        """)
        test_tasks = cursor.fetchall()
        
        print(f"\n📊 Current test tasks:")
        for task in test_tasks:
            print(f"  - {task[0]}: struck_today={task[1]}, refreshed_at={task[2]}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
