import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect('C:/Users/vibin/AppData/Roaming/Shakshuka/data/shakshuka.db')
conn.row_factory = sqlite3.Row

# Get first task
cursor = conn.execute('SELECT * FROM tasks LIMIT 1')
task = cursor.fetchone()

if task:
    task_id = task['id']
    print(f"Testing with task: {task['title']} (ID: {task_id})")
    print(f"Current refreshed_at: {task['refreshed_at']}")
    
    # Update with refreshed_at
    now = datetime.now().isoformat()
    conn.execute('''
        UPDATE tasks SET refreshed_at = ? WHERE id = ?
    ''', (now, task_id))
    conn.commit()
    
    print(f"Updated refreshed_at to: {now}")
    
    # Verify
    cursor = conn.execute('SELECT refreshed_at FROM tasks WHERE id = ?', (task_id,))
    result = cursor.fetchone()
    print(f"Verified refreshed_at: {result['refreshed_at']}")
    
    if result['refreshed_at'] == now:
        print("✅ SUCCESS: refreshed_at was saved correctly!")
    else:
        print("❌ FAILED: refreshed_at was not saved")
else:
    print("No tasks found")

conn.close()
