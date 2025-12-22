#!/usr/bin/env python3
"""
Simple script to manually add refreshed_at timestamps to struck tasks
"""

import sqlite3
from datetime import datetime

def main():
    print("🔄 Manually adding refreshed_at timestamps to struck tasks...")
    
    # Database path
    db_path = 'C:/Users/vibin/AppData/Roaming/Shakshuka/data/shakshuka.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find tasks with struck_today = 1
        cursor.execute("""
            SELECT id, title, struck_today, refreshed_at 
            FROM tasks 
            WHERE struck_today = 1 AND refreshed_at IS NULL
        """)
        struck_tasks = cursor.fetchall()
        
        print(f"📋 Found {len(struck_tasks)} tasks that need refreshing")
        
        if struck_tasks:
            print("\nTasks that will be refreshed:")
            for task in struck_tasks:
                print(f"  - {task[1]}")
            
            # Add refreshed_at timestamp
            reset_timestamp = datetime.now().isoformat()
            print(f"\n⏰ Adding timestamp: {reset_timestamp}")
            
            cursor.execute("""
                UPDATE tasks 
                SET refreshed_at = ? 
                WHERE struck_today = 1 AND refreshed_at IS NULL
            """, (reset_timestamp,))
            
            conn.commit()
            print(f"✅ Updated {cursor.rowcount} tasks")
            
            # Verify the updates
            cursor.execute("""
                SELECT id, title, refreshed_at 
                FROM tasks 
                WHERE refreshed_at IS NOT NULL 
                ORDER BY refreshed_at DESC 
                LIMIT 5
            """)
            updated = cursor.fetchall()
            
            print(f"\n🏷️  Tasks with refreshed_at:")
            for task in updated:
                print(f"  - {task[1]}: {task[2]}")
            
            print(f"\n🎉 The refreshed badge will now be visible between 8am-12pm today!")
        else:
            print("ℹ️  No struck tasks found that need refreshing")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
