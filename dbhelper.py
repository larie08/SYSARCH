from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

def connect_db():
    return sqlite3.connect('users.db')

def create_tables():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        idno TEXT PRIMARY KEY,
        lastname TEXT NOT NULL,
        firstname TEXT NOT NULL,
        middlename TEXT NOT NULL,
        course TEXT NOT NULL,
        level TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        active INTEGER DEFAULT 1
    )''')
    conn.commit()
    conn.close()

def add_user(user_data):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        hashed_pw = generate_password_hash(user_data[-1])
        modified_data = user_data[:-1] + (hashed_pw,)
        cursor.execute('''
            INSERT INTO users 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (*modified_data,))
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        print(f"Registration error: {e}")
        return False
    finally:
        conn.close()

def check_user(username, password):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT password FROM users 
            WHERE username = ?
        ''', (username,))
        result = cursor.fetchone()
        return result and check_password_hash(result[0], password)
    finally:
        conn.close()

def update_password(username, new_password):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT username FROM users WHERE username = ?', (username,))
        if not cursor.fetchone():
            return False 
    
        hashed_pw = generate_password_hash(new_password)
        cursor.execute('''
            UPDATE users 
            SET password = ?
            WHERE username = ?
        ''', (hashed_pw, username))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Password update error: {e}")
        return False
    finally:
        conn.close()