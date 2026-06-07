#!/usr/bin/env python3
"""Database integrity checker for Shakshuka"""
import sqlite3
import os
import sys

DB_PATH = r"C:\Users\vibin\AppData\Roaming\Shakshuka\data\shakshuka.db"
WAL_PATH = DB_PATH + "-wal"
SHM_PATH = DB_PATH + "-shm"
BACKUP_PATH = r"C:\Users\vibin\AppData\Roaming\Shakshuka\data\shakshuka.db.migration_backup_1762544880"

def check_integrity(db_path):
    """Run PRAGMA integrity_check on database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "Unknown"
    except Exception as e:
        return f"Error: {e}"

def check_table_counts(db_path):
    """Count rows in all tables"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        counts = {}
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            counts[table_name] = count
        
        conn.close()
        return counts
    except Exception as e:
        return {"error": str(e)}

def check_wal_size():
    """Check WAL file size"""
    if os.path.exists(WAL_PATH):
        return os.path.getsize(WAL_PATH)
    return 0

def try_wal_recovery(db_path):
    """Attempt to recover from WAL file"""
    try:
        # This will checkpoint the WAL and merge it into the main database
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA wal_checkpoint(FULL)")
        conn.close()
        return "WAL checkpoint completed"
    except Exception as e:
        return f"WAL recovery failed: {e}"

def main():
    print("=" * 60)
    print("SHAKSHUKA DATABASE INTEGRITY CHECK")
    print("=" * 60)
    print()
    
    # Check file sizes
    print("File Sizes:")
    print(f"  Main DB: {os.path.getsize(DB_PATH) / 1024 / 1024:.2f} MB")
    print(f"  WAL:     {check_wal_size() / 1024 / 1024:.2f} MB")
    if os.path.exists(SHM_PATH):
        print(f"  SHM:     {os.path.getsize(SHM_PATH) / 1024:.2f} KB")
    if os.path.exists(BACKUP_PATH):
        print(f"  Backup:  {os.path.getsize(BACKUP_PATH) / 1024:.2f} KB")
    print()
    
    # Check integrity
    print("Integrity Check:")
    integrity = check_integrity(DB_PATH)
    print(f"  Result: {integrity}")
    print()
    
    # Check table counts
    print("Table Row Counts:")
    counts = check_table_counts(DB_PATH)
    if "error" in counts:
        print(f"  Error: {counts['error']}")
    else:
        for table, count in counts.items():
            print(f"  {table}: {count} rows")
    print()
    
    # Check WAL
    wal_size = check_wal_size()
    if wal_size > 1024 * 1024:  # If WAL > 1MB
        print("WARNING: Large WAL file detected!")
        print("This may indicate uncommitted transactions or improper shutdown.")
        print()
        response = input("Attempt WAL recovery? (y/n): ")
        if response.lower() == 'y':
            result = try_wal_recovery(DB_PATH)
            print(f"  {result}")
            print()
            print("Re-checking table counts after WAL recovery:")
            counts = check_table_counts(DB_PATH)
            for table, count in counts.items():
                print(f"  {table}: {count} rows")
    print()
    
    print("=" * 60)

if __name__ == "__main__":
    main()
