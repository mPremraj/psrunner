import sqlite3
import os

def init_db(db_path):
    """Initialize the SQLite database with required tables if they don't exist"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create script executions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS script_executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        username TEXT NOT NULL,
        environment TEXT NOT NULL,
        activity TEXT NOT NULL,
        version TEXT NOT NULL,
        script_name TEXT NOT NULL,
        output_file TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        status TEXT NOT NULL,
        stdout TEXT,
        stderr TEXT,
        return_code INTEGER
    )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection(db_path):
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def close_connection(conn):
    """Close the database connection"""
    if conn:
        conn.close()