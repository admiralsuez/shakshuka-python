#!/usr/bin/env python3
"""
Check the struck_date values for struck tasks to understand why startup checker fails
"""

import sqlite3
from datetime import datetime

def main():
    print("🔍 Checking struck_date values for struck tasks...")
    
    # Database path
    db_path = 'C:/Users/vibin/AppData/Roaming/Shakshuka/data/shakshuka.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get today's date
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"📅 Today's date: {today}")
        
        # Check all struck tasks
        cursor.execute("""
            SELECT title, struck_today, struck_date, refreshed_at 
            FROM tasks 
            WHERE struck_today = 1
        """)
        struck_tasks = cursor.fetchall()
        
        print(f"\n📊 Found {len(struck_tasks)} tasks with struck_today = 1:")
        
        for task in struck_tasks:
            title, struck_today, struck_date, refreshed_at = task
            print(f"\n  Task: {title}")
            print(f"  struck_today: {struck_today}")
            print(f"  struck_date: {struck_date}")
            print(f"  refreshed_at: {refreshed_at}")
            
            if not struck_date:
                print("  ⚠️  ISSUE: No struck_date - startup checker will SKIP this task!")
            elif struck_date != today:
                print(f"  ✅ GOOD: struck_date != today - startup checker will PROCESS this task")
            else:
                print(f"  ℹ️  INFO: struck_date == today - startup checker will skip (struck today after reset)")
        
        print(f"\n🎯 CONCLUSION:")
        print("The startup checker only processes tasks where:")
        print("  1. struck_today = 1 AND")
        print("  2. struck_date exists AND") 
        print("  3. struck_date != today")
        print("\nTasks without struck_date are skipped for safety!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
