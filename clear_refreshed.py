import sqlite3

conn = sqlite3.connect('C:/Users/vibin/AppData/Roaming/Shakshuka/data/shakshuka.db')
conn.execute('UPDATE tasks SET refreshed_at = NULL WHERE refreshed_at LIKE "2025-12-12:%"')
conn.commit()
print('Cleared today\'s refreshed_at timestamps')
conn.close()
