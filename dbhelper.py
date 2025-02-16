from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

def connect_db():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row  # Enables fetching rows as dictionaries
    return conn

def create_tables():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        
        # Create users table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                IDNO TEXT PRIMARY KEY,
                LASTNAME TEXT NOT NULL,
                FIRSTNAME TEXT NOT NULL,
                MIDDLENAME TEXT,
                COURSE TEXT NOT NULL,
                YEAR_LEVEL TEXT NOT NULL,
                EMAIL TEXT UNIQUE NOT NULL,
                Username TEXT UNIQUE NOT NULL,
                Password TEXT NOT NULL,
                sessions INTEGER DEFAULT 3
            )
        """)
        
        # Create reservations table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idno TEXT NOT NULL,
                purpose TEXT NOT NULL,
                lab TEXT NOT NULL,
                time_in DATETIME NOT NULL,
                time_out DATETIME,
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (idno) REFERENCES users(IDNO)
            )
        """)
        
        # Add time_out column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE reservations ADD COLUMN time_out DATETIME")
        except sqlite3.OperationalError:
            # Column already exists
            pass
            
        conn.commit()

def add_user(user_data):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (IDNO, Lastname, Firstname, Middlename, Course, Year_Level, Email, Username, Password)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_data['idno'], user_data['lastname'], user_data['firstname'], user_data['middlename'],
                 user_data['course'], user_data['year_level'], user_data['email'], user_data['username'], user_data['password']))
            conn.commit()
            return True  
    except sqlite3.IntegrityError:  
        return False  

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

def get_data():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Fetch Sit-in Requests
    cursor.execute("SELECT class_name, date, status FROM sessions WHERE student_id = ?", (session['student_id'],))
    requests = cursor.fetchall()

    # Fetch Upcoming Sessions
    cursor.execute("SELECT class_name, instructor, date, time FROM sessions WHERE status='Approved' AND date >= DATE('now')")
    upcoming_sessions = cursor.fetchall()

    # Fetch Popular Sit-in Classes
    cursor.execute("SELECT class_name, COUNT(student_id) AS student_count FROM sessions GROUP BY class_name ORDER BY student_count DESC LIMIT 5")
    popular_classes = cursor.fetchall()

    conn.close()
    return requests, upcoming_sessions, popular_classes
