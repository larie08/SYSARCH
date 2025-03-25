from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from sqlite3 import Row

#dbhelper para sa user end/students
def connect_db():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row 
    return conn

def create_tables():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                idno INTEGER PRIMARY KEY,
                lastname TEXT NOT NULL,
                firstname TEXT NOT NULL,
                middlename TEXT,
                course TEXT NOT NULL,
                year_level INTEGER NOT NULL,
                email TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                sessions TEXT DEFAULT NULL,
                address TEXT,
                photo TEXT
           )
        """)

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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id INTEGER,
                student_id TEXT,
                feedback TEXT,
                laboratory TEXT,
                date TEXT,
                FOREIGN KEY (student_id) REFERENCES users (idno),
                FOREIGN KEY (reservation_id) REFERENCES reservations (id)
            )
        """)

        try:
            cursor.execute("ALTER TABLE reservations ADD COLUMN time_out DATETIME")
        except sqlite3.OperationalError:

            pass
            
        conn.commit()

def add_user(user_data):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (idno, lastname, firstname, middlename, course, year_level, 
                                 email, username, password, sessions, address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_data['idno'], user_data['lastname'], user_data['firstname'], 
                 user_data['middlename'], user_data['course'], user_data['year_level'], 
                 user_data['email'], user_data['username'], user_data['password'],
                 None, user_data['address']))
            conn.commit()
            return True  
    except sqlite3.IntegrityError as e:
        print(f"Database error: {e}")
        return False
        
def check_user(username, password):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        # Check if user exists in the users table
        cursor.execute('''
            SELECT idno, username, password, address 
            FROM users 
            WHERE username = ?
        ''', (username,))
        result = cursor.fetchone()
        if result and check_password_hash(result['password'], password):
            return {
                "id": result['idno'],
                "username": result['username'],
                "address": result['address'],
                "role": "user"
            }
        return None
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

def update_user_profile(student_id, data):
    """Update user profile information including photo"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            if data.get('photo'):
                query = """
                    UPDATE users 
                    SET firstname = ?, 
                        lastname = ?, 
                        middlename = ?,
                        email = ?,
                        course = ?,
                        year_level = ?,
                        address = ?,
                        photo = ?
                    WHERE idno = ?
                """
                params = [
                    data['firstname'],
                    data['lastname'],
                    data['middlename'],
                    data['email'],
                    data['course'],
                    data['level'],
                    data['address'],
                    data['photo'],
                    student_id
                ]
            else:
                query = """
                    UPDATE users 
                    SET firstname = ?, 
                        lastname = ?, 
                        middlename = ?,
                        email = ?,
                        course = ?,
                        year_level = ?,
                        address = ?
                    WHERE idno = ?
                """
                params = [
                    data['firstname'],
                    data['lastname'],
                    data['middlename'],
                    data['email'],
                    data['course'],
                    data['level'],
                    data['address'],
                    student_id
                ]

            cursor.execute(query, params)
            conn.commit()

            cursor.execute("SELECT photo FROM users WHERE idno = ?", (student_id,))
            result = cursor.fetchone()
            print("Updated photo value:", result[0] if result else None)
            
            return True
    except Exception as e:
        print(f"Error updating user profile: {e}")
        return False

def get_user_profile(student_id):
    """Get user profile information including photo"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT idno,         -- 0
                       lastname,     -- 1
                       firstname,    -- 2
                       middlename,   -- 3
                       course,       -- 4
                       year_level,   -- 5
                       email,        -- 6
                       address,      -- 7
                       sessions,     -- 8
                       photo         -- 9
                FROM users 
                WHERE idno = ?
            """, (student_id,))
            result = cursor.fetchone()
            print("Retrieved profile with photo:", result[9] if result else None)
            return result
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return None

def initialize_user_sessions(student_idno):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_session_counts WHERE student_idno = ?", (student_idno,))
        existing = cursor.fetchone()
        
        if not existing:
            cursor.execute("""
                INSERT INTO user_session_counts (student_idno, total_sessions, available_sessions, used_sessions) 
                VALUES (?, 30, 30, 0)
            """, (student_idno,))
            conn.commit()
    except Exception as e:
        print(f"Error initializing sessions: {e}")
    finally:
        conn.close()

def update_sessions_on_reservation(student_idno):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT available_sessions, used_sessions 
            FROM user_session_counts 
            WHERE student_idno = ?
        """, (student_idno,))
        session_data = cursor.fetchone()
        
        if session_data and session_data[0] > 0:  
            cursor.execute("""
                UPDATE user_session_counts 
                SET available_sessions = available_sessions - 1,
                    used_sessions = used_sessions + 1
                WHERE student_idno = ?
            """, (student_idno,))
            conn.commit()
            return True
        return False
    finally:
        conn.close()

def get_user_by_id(student_id):
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE idno = ?", (student_id,))
        user = cursor.fetchone()
        return user
    except Exception as e:
        print(f"Error getting user: {e}")
        return None
    finally:
        conn.close()

def submit_feedback(student_id, reservation_id, feedback_text, laboratory, date):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedback (student_id, reservation_id, feedback, laboratory, date)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, reservation_id, feedback_text, laboratory, date))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error submitting feedback: {e}")
        return False

def get_all_feedback():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    u.idno,
                    f.laboratory,
                    f.date,
                    f.feedback
                FROM feedback f
                JOIN users u ON f.student_id = u.idno
                ORDER BY f.date DESC
            """)
            feedbacks = cursor.fetchall()
            return feedbacks
    except Exception as e:
        print(f"Error fetching feedback: {e}")
        return []
#dbhelper para sa user end/students


#ADMIN DBHELPER

def check_admin_login(username, password):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT admin_id, username, password FROM admin WHERE username = ?', (username,))
        result = cursor.fetchone()
        if result and check_password_hash(result['password'], password):
            return {"id": result['admin_id'], "username": result['username'], "role": "admin"}
        return None
    finally:
        conn.close()

def admin_announcement():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        admin_id = session['admin_id']
        
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO announcements (admin_id, title, message)
                    VALUES (?, ?, ?)
                """, (admin_id, title, message))
                conn.commit()
                flash('Announcement added successfully', 'success')
            except Exception as e:
                print(f"Error adding announcement: {e}")
                flash('Failed to add announcement', 'error')
                
    # Fetch all announcements
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.announcement_id, a.title, a.message, a.created_at, adm.username
            FROM announcements a
            JOIN admin adm ON a.admin_id = adm.admin_id
            ORDER BY a.created_at DESC
        """)
        announcements = cursor.fetchall()
        
    return render_template('adminannouncement.html', announcements=announcements)


def add_announcement(title, content):
    try:
        with connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO announcements (title, content, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (title, content))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error adding announcement: {e}")
        return False

def search_student(student_id):
    try:
        with connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.*, 
                       COALESCE(
                           (SELECT available_sessions 
                            FROM user_session_counts 
                            WHERE student_idno = u.IDNO), 
                           30
                       ) as available_sessions
                FROM users u
                WHERE u.IDNO = ?
            """, (student_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"Error searching student: {e}")
        return None

def record_sit_in(student_id, admin_id, laboratory):
    try:
        with connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sit_in_records (student_id, admin_id, laboratory, time_in)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (student_id, admin_id, laboratory))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error recording sit-in: {e}")
        return False

def get_sit_in_history(limit=50):
    try:
        with connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, u.FIRSTNAME || ' ' || u.LASTNAME as student_name
                FROM sit_in_records s
                JOIN users u ON s.student_id = u.IDNO
                ORDER BY time_in DESC
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching sit-in history: {e}")
        return []


#ADMIN DBHELPER


#debug purposes
def cleanup_orphaned_sitins():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        # Delete sit-in records where the user no longer exists
        cursor.execute("""
            DELETE FROM reservations 
            WHERE idno NOT IN (SELECT idno FROM users)
        """)
        conn.commit()