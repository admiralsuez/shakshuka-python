import sqlite3

# Connect to database
conn = sqlite3.connect('C:/Users/vibin/AppData/Roaming/Shakshuka/data/shakshuka.db')

# Update migration version
conn.execute('INSERT INTO migration_version (version, description) VALUES (?, ?)', 
             (12, 'Migration 12 - refreshed_at column'))
conn.commit()

print('Migration version updated to 12')

# Verify the column exists
cursor = conn.execute("PRAGMA table_info(tasks)")
columns = [row[1] for row in cursor.fetchall()]
if 'refreshed_at' in columns:
    print('✓ refreshed_at column exists in tasks table')
else:
    print('✗ refreshed_at column NOT found')

conn.close()
