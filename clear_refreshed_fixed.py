import sqlite3

conn = sqlite3.connect('C:/Users/vibin/AppData/Roaming/Shakshuka/data/shakshuka.db')

# Clear today's refreshed_at timestamps (the ones I manually added)
cursor = conn.execute('UPDATE tasks SET refreshed_at = NULL WHERE refreshed_at LIKE "2025-12-22T12:%"')
print(f'Cleared {cursor.rowcount} refreshed_at timestamps')

conn.commit()

# Verify the clear
cursor = conn.execute('SELECT COUNT(*) FROM tasks WHERE struck_today = 1 AND refreshed_at IS NULL')
struck_no_refresh = cursor.fetchone()[0]
print(f'Tasks with struck_today=1 but no refreshed_at: {struck_no_refresh}')

conn.close()
