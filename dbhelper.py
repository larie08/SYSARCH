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

#dbhelper para sa staff end
def add_staff(staff_data):
    """Add a new staff member"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO staff (
                    staff_id, firstname, middlename, lastname, 
                    email, username, password, role, photo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                staff_data['staff_id'],
                staff_data['firstname'],
                staff_data['middlename'],
                staff_data['lastname'],
                staff_data['email'],
                staff_data['username'],
                generate_password_hash(staff_data['password']),
                staff_data['role'],
                staff_data.get('photo', None)
            ))
            conn.commit()
            return True
    except sqlite3.IntegrityError as e:
        print(f"Error adding staff: {e}")
        return False

def get_staff_profile(staff_id):
    """Get staff member profile"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT staff_id, firstname, middlename, lastname, 
                   email, username, role, photo
            FROM staff 
            WHERE staff_id = ?
        """, (staff_id,))
        return cursor.fetchone()
    finally:
        conn.close()

def update_reservation_status(reservation_id, new_status, staff_id, remarks=None):
    """Update reservation status and record in history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First update the reservation status
        cursor.execute("""
            UPDATE reservations 
            SET status = ? 
            WHERE id = ?
        """, (new_status, reservation_id))
        
        # Then record the change in status_history
        cursor.execute("""
            INSERT INTO status_history (
                reservation_id, status, changed_by, remarks
            ) VALUES (?, ?, ?, ?)
        """, (reservation_id, new_status, staff_id, remarks))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating reservation status: {e}")
        return False
    finally:
        conn.close()

def get_pending_reservations():
    """Get all pending reservations"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                r.id,
                r.idno,
                u.firstname,
                u.lastname,
                r.purpose,
                r.lab,
                r.time_in,
                r.status
            FROM reservations r
            JOIN users u ON r.idno = u.idno
            WHERE r.status = 'Pending'
            ORDER BY r.time_in ASC
        """)
        return cursor.fetchall()
    finally:
        conn.close()

def get_status_history(reservation_id):
    """Get the status history for a reservation"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                sh.status,
                sh.changed_at,
                s.firstname || ' ' || s.lastname as staff_name,
                sh.remarks
            FROM status_history sh
            JOIN staff s ON sh.changed_by = s.staff_id
            WHERE sh.reservation_id = ?
            ORDER BY sh.changed_at DESC
        """, (reservation_id,))
        return cursor.fetchall()
    finally:
        conn.close()

def staff_login(username, password):
    """Verify staff login credentials"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT staff_id, password, firstname, lastname, role 
            FROM staff 
            WHERE username = ?
        """, (username,))
        staff = cursor.fetchone()
        
        if staff and staff['password'] == password:  # Using plain text for now
            return {
                'staff_id': staff['staff_id'],
                'name': f"{staff['firstname']} {staff['lastname']}",
                'role': staff['role']
            }
        return None
    finally:
        conn.close()

def get_pending_reservations():
    """Get all pending sit-in reservations"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                r.id,
                r.idno,
                u.firstname,
                u.lastname,
                u.course,
                u.year_level,
                r.purpose,
                r.lab,
                r.time_in,
                r.status
            FROM reservations r
            JOIN users u ON r.idno = u.idno
            WHERE r.status = 'Pending'
            ORDER BY r.time_in ASC
        """)
        return cursor.fetchall()
    finally:
        conn.close()

def add_announcement(title, content, staff_id):
    """Add a new announcement"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO announcements (title, content, created_by)
            VALUES (?, ?, ?)
        """, (title, content, staff_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding announcement: {e}")
        return False
    finally:
        conn.close()

def get_announcements():
    """Get all announcements with staff details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                a.id,
                a.title,
                a.content,
                s.firstname || ' ' || s.lastname as staff_name,
                a.created_at
            FROM announcements a
            JOIN staff s ON a.created_by = s.staff_id
            ORDER BY a.created_at DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()


