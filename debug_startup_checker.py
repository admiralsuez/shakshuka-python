#!/usr/bin/env python3
"""
Debug script to check why the startup missed reset checker isn't working
"""

import sqlite3
from datetime import datetime

def main():
    print("🔍 Debugging startup missed reset checker...")
    
    # Database path
    db_path = 'C:/Users/vibin/AppData/Roaming/Shakshuka/data/shakshuka.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current time
        now = datetime.now()
        print(f"📅 Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🕐 Current hour: {now.hour:02d}:{now.minute:02d}")
        
        # Reset time should be 04:20
        reset_hour, reset_minute = 4, 20
        today_reset_time = now.replace(hour=reset_hour, minute=reset_minute, second=0, microsecond=0)
        print(f"⏰ Reset time: {today_reset_time.strftime('%H:%M')}")
        print(f"📊 Is current time past reset time? {now > today_reset_time}")
        
        # Check for struck tasks
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE struck_today = 1")
        struck_count = cursor.fetchone()[0]
        print(f"⚡ Tasks with struck_today = 1: {struck_count}")
        
        if struck_count > 0:
            cursor.execute("SELECT id, title FROM tasks WHERE struck_today = 1")
            struck_tasks = cursor.fetchall()
            print("\nStruck tasks:")
            for task in struck_tasks:
                print(f"  - {task[1]}")
        
        # Check for refreshed_at tasks
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE refreshed_at IS NOT NULL")
        refreshed_count = cursor.fetchone()[0]
        print(f"🏷️  Tasks with refreshed_at: {refreshed_count}")
        
        if refreshed_count > 0:
            cursor.execute("""
                SELECT id, title, refreshed_at 
                FROM tasks 
                WHERE refreshed_at IS NOT NULL 
                ORDER BY refreshed_at DESC 
                LIMIT 3
            """)
            refreshed_tasks = cursor.fetchall()
            print("\nRecently refreshed tasks:")
            for task in refreshed_tasks:
                print(f"  - {task[1]}: {task[2]}")
        
        # Determine what should happen
        if now > today_reset_time and struck_count > 0:
            print("\n✅ EXPECTED: Startup checker SHOULD run missed reset!")
            print("   The tasks should have refreshed_at timestamps added automatically.")
        elif now <= today_reset_time:
            print("\n⏳ EXPECTED: Reset time hasn't passed yet, no action needed.")
        elif struck_count == 0:
            print("\n👍 EXPECTED: No struck tasks, no action needed.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
