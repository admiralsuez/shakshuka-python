#!/usr/bin/env python3
"""
Manually trigger daily reset to test refreshed badge functionality
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.app import reset_daily_strikes_job
from src.sqlite_data_manager import SQLiteDataManager
from src.utils.helpers import get_user_id

def main():
    print("🔄 Manually triggering daily reset...")
    
    # Initialize data manager
    data_manager = SQLiteDataManager()
    user_id = get_user_id()
    
    # Load current tasks
    tasks = data_manager.load_tasks_for_user(user_id)
    print(f"📋 Loaded {len(tasks)} tasks")
    
    # Count struck tasks
    struck_tasks = [task for task in tasks if task.get('struck_today')]
    print(f"⚡ Found {len(struck_tasks)} tasks with struck_today=True")
    
    if struck_tasks:
        print("\nTasks that will be refreshed:")
        for task in struck_tasks:
            print(f"  - {task['title']}")
    
    # Run daily reset
    print("\n🌅 Running daily reset job...")
    reset_daily_strikes_job()
    
    # Reload tasks to see the changes
    updated_tasks = data_manager.load_tasks_for_user(user_id)
    refreshed_tasks = [task for task in updated_tasks if task.get('refreshed_at')]
    
    print(f"\n✅ Reset complete! {len(refreshed_tasks)} tasks now have refreshed_at")
    
    if refreshed_tasks:
        print("\nRefreshed tasks:")
        for task in refreshed_tasks:
            print(f"  - {task['title']}: {task['refreshed_at']}")
    
    print(f"\n🏷️  The refreshed badge will now be visible between 8am-12pm today!")

if __name__ == "__main__":
    main()
