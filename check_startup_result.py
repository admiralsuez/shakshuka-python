#!/usr/bin/env python3
"""
Check if the startup test marker was processed by the startup checker
"""

import sqlite3

def main():
    print("🔍 Checking startup test result...")
    
    # Database path
    db_path = 'C:/Users/vibin/AppData/Roaming/Shakshuka/data/shakshuka.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check the test task
        cursor.execute("""
            SELECT title, struck_today, refreshed_at 
            FROM tasks 
            WHERE title LIKE 'STARTUP_TEST_MARKER%'
        """)
        test_tasks = cursor.fetchall()
        
        print(f"📊 Found {len(test_tasks)} test tasks:")
        
        for task in test_tasks:
            title, struck_today, refreshed_at = task
            print(f"\n  Task: {title}")
            print(f"  struck_today: {struck_today}")
            print(f"  refreshed_at: {refreshed_at}")
            
            if refreshed_at is not None:
                print("  ✅ SUCCESS: Startup checker worked! Task was refreshed.")
            else:
                print("  ❌ FAILURE: Startup checker did NOT run or failed to refresh task.")
        
        # Also check other struck tasks
        cursor.execute("""
            SELECT title, struck_today, refreshed_at 
            FROM tasks 
            WHERE struck_today = 1 AND refreshed_at IS NULL
            LIMIT 5
        """)
        struck_tasks = cursor.fetchall()
        
        if struck_tasks:
            print(f"\n⚠️  Found {len(struck_tasks)} other struck tasks without refreshed_at:")
            for task in struck_tasks:
                print(f"  - {task[0]}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
