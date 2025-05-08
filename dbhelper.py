import sqlite3
import csv
import io
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
import os
import time
from werkzeug.utils import secure_filename

RESOURCE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'resources')

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
                points INTEGER DEFAULT 0,
                address TEXT,
                photo TEXT
           )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lab_computers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lab TEXT NOT NULL,
                computer_number INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                UNIQUE(lab, computer_number)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idno TEXT NOT NULL,
                purpose TEXT NOT NULL,
                laboratory TEXT NOT NULL, 
                computer_number INTEGER NOT NULL,
                time_in DATETIME NOT NULL,
                time_out DATETIME,
                status TEXT DEFAULT 'Pending',
                requested_time DATETIME,
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_name TEXT NOT NULL,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT,
                file_size INTEGER,
                uploaded_by TEXT,
                is_active INTEGER DEFAULT 1,
                upload_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        try:
            cursor.execute("ALTER TABLE reservations ADD COLUMN time_out DATETIME")
        except sqlite3.OperationalError:

            pass
            
        conn.commit()

# def initialize_database():
#     with sqlite3.connect("users.db") as conn:
#         cursor = conn.cursor()
        
#         # Add remaining_sessions column if it doesn't exist
#         cursor.execute("""
#             ALTER TABLE users ADD COLUMN remaining_sessions INTEGER DEFAULT 0;
#         """)
        
#         # Update existing users with default session values based on their course
#         cursor.execute("""
#             UPDATE users 
#             SET remaining_sessions = CASE 
#                 WHEN course LIKE '%BSIT%' THEN 30
#                 WHEN course LIKE '%BSCS%' THEN 30
#                 ELSE 20
#             END
#             WHERE remaining_sessions IS NULL;
#         """)
        
#         conn.commit()

# # Call this function to update the database schema
# initialize_database()

# for both student and admin
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

def user_exists(idno, username, email):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE IDNO = ? OR username = ? OR email = ?", 
                          (idno, username, email))
            return cursor.fetchone() is not None
    except Exception as e:
        print(f"Error checking if user exists: {e}")
        return True  # Assume user exists on error to prevent registration


# student register start
def register_user(idno, lastname, firstname, middlename, level, course, address, username, email, password, session_limit):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # First check if user already exists with more specific checks
            cursor.execute("SELECT * FROM users WHERE IDNO = ?", (idno,))
            if cursor.fetchone():
                print(f"User with ID {idno} already exists")
                return False
                
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                print(f"User with username {username} already exists")
                return False
                
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                print(f"User with email {email} already exists")
                return False
            
            # If all checks pass, insert the new user
            cursor.execute("""
                INSERT INTO users (IDNO, lastname, firstname, middlename, year_level, course, address, username, email, password, sessions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (idno, lastname, firstname, middlename, level, course, address, username, email, password, session_limit))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error registering user: {e}")
        return False

def validate_registration_data(user_data):
    required_fields = ['idno', 'lastname', 'firstname', 'course', 'year_level', 
                      'email', 'username', 'password']
    
    for field in required_fields:
        if not user_data.get(field):
            return False, f"{field} is required"
            
    return True, None

def process_registration(user_data, course):
    try:
        session_limit = 30 if course in [
            'Bachelor of Science in Information Technology',
            'Bachelor of Science in Computer Science'
        ] else 15
        
        user_data['sessions'] = session_limit
        
        if add_user(user_data):
            return True, session_limit, None
        return False, None, "Failed to add user to database"
        
    except Exception as e:
        print(f"Registration processing error: {e}")
        return False, None, str(e)
# student register end


# student lab resources start
def get_resource_folders():
    """Get available resource folders based on completed sit-ins"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # Get folders that have active resources and match completed sit-in purposes
            cursor.execute("""
                SELECT DISTINCT r.folder_name 
                FROM resources r
                INNER JOIN reservations res ON r.folder_name = res.purpose
                WHERE r.is_active = 1
                AND res.status = 'Completed'
                GROUP BY r.folder_name
                ORDER BY r.folder_name
            """)
            
            return [{'name': folder[0]} for folder in cursor.fetchall()]
    except Exception as e:
        print(f"Database error in get_resource_folders: {e}")
        return []

def get_resource_files(folder_name):
    """Get files for a specific resource folder"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    name,
                    file_path,
                    file_type,
                    file_size,
                    upload_date,
                    uploaded_by
                FROM resources
                WHERE folder_name = ? 
                AND is_active = 1
                ORDER BY upload_date DESC
            """, (folder_name,))
            
            files = cursor.fetchall()
            return [{
                'name': file[0],
                'path': file[1],
                'type': file[2],
                'size': file[3],
                'date': file[4],
                'uploaded_by': file[5]
            } for file in files]
    except Exception as e:
        print(f"Error getting resource files: {e}")
        return []

def save_resource_file(folder_name, file_name, file_path, file_type, file_size, uploaded_by):
    """Save resource file information to database"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # First check if the file already exists
            cursor.execute("""
                SELECT id FROM resources 
                WHERE folder_name = ? AND name = ?
            """, (folder_name, file_name))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record
                cursor.execute("""
                    UPDATE resources 
                    SET file_path = ?,
                        file_type = ?,
                        file_size = ?,
                        uploaded_by = ?,
                        upload_date = CURRENT_TIMESTAMP,
                        is_active = 1
                    WHERE folder_name = ? AND name = ?
                """, (file_path, file_type, file_size, uploaded_by, folder_name, file_name))
            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO resources (
                        folder_name, name, file_path, file_type, 
                        file_size, uploaded_by, is_active, upload_date
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (folder_name, file_name, file_path, file_type, file_size, uploaded_by))
            
            conn.commit()
            
            # Verify the save
            cursor.execute("""
                SELECT id FROM resources 
                WHERE folder_name = ? AND name = ?
            """, (folder_name, file_name))
            
            return cursor.fetchone() is not None
            
    except Exception as e:
        print(f"Database error in save_resource_file: {e}")
        return False
# student lab resources end

# student lab purpose start 
def get_student_purposes(student_id):
    """Get unique purposes from student's completed sit-ins"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT purpose 
                FROM reservations 
                WHERE idno = ? 
                AND status = 'Completed'
                ORDER BY purpose
            """, (student_id,))
            return [row[0] for row in cursor.fetchall()]  # Return list of strings
    except Exception as e:
        print(f"Error getting student purposes: {e}")
        return []

def get_student_completed_purposes(student_id):
    """Get list of completed purposes for a student"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT purpose 
                FROM reservations 
                WHERE idno = ? 
                AND status = 'Completed'
            """, (student_id,))
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting completed purposes: {e}")
        return []
# student lab purpose end

# student user start       
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

def save_profile_photo(file, upload_folder):
    try:
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        photo_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(upload_folder, photo_filename)
        file.save(file_path)
        
        return True, photo_filename
    except Exception as e:
        print(f"Error saving photo: {e}")
        return False, str(e)

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

def get_all_users():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                idno,
                firstname || ' ' || COALESCE(middlename, '') || ' ' || lastname as name,
                course,
                year_level,
                sessions,
                photo
            FROM users
            ORDER BY name
        """)
        
        return [
            {
                'idno': row[0],
                'name': row[1],
                'course': row[2],
                'year_level': row[3],
                'remaining_sessions': row[4],
                'photo': row[5] if row[5] else None
            }
            for row in cursor.fetchall()
        ]

def get_user_points_and_sessions(student_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT points, sessions
                FROM users
                WHERE idno = ?
            """, (student_id,))
            result = cursor.fetchone()
            
            # Ensure we're getting the actual points value, not None
            points = result[0] if result and result[0] is not None else 0
            sessions = result[1] if result and result[1] is not None else 0
            
            return {
                'points': int(points),  # Convert to integer to ensure consistent type
                'sessions': int(sessions)
            }
    except Exception as e:
        print(f"Error getting user points and sessions: {e}")
        return {'points': 0, 'sessions': 0}

def update_user_points(student_id, points):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET points = ?
                WHERE idno = ?
            """, (points, student_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating user points: {e}")
        return False

def increment_user_points(student_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            # Get current points
            cursor.execute("SELECT points FROM users WHERE idno = ?", (student_id,))
            result = cursor.fetchone()
            current_points = result[0] if result and result[0] is not None else 0
            
            new_points = current_points + 1
            
            # If points reach 3, add a session and reset points
            if new_points >= 3:
                cursor.execute("""
                    UPDATE users 
                    SET points = 0,
                        sessions = COALESCE(sessions, 0) + 1
                    WHERE idno = ?
                """, (student_id,))
                return True, "Points converted to an extra session!"
            else:
                # Just update points
                cursor.execute("""
                    UPDATE users 
                    SET points = ?
                    WHERE idno = ?
                """, (new_points, student_id))
                return True, f"Point added! Current points: {new_points}/3"
            
    except Exception as e:
        print(f"Error incrementing user points: {e}")
        return False, str(e)
#student user end

# student announcement start
def get_student_announcements():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.announcement_id, a.title, a.message, a.created_at, a.author
                FROM announcements a
                ORDER BY a.created_at DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching announcements: {e}")
        return []
# student announcement end

# student laboratory resources start
def get_student_resources(student_id):
    """Get available resources based on student's completed sit-ins"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # Get student's completed purposes
            cursor.execute("""
                SELECT DISTINCT purpose 
                FROM reservations 
                WHERE idno = ? AND status = 'Completed'
            """, (student_id,))
            
            completed_purposes = [row[0] for row in cursor.fetchall()]
            
            # Get resources for completed purposes
            resources = []
            for purpose in completed_purposes:
                cursor.execute("""
                    SELECT 
                        id,
                        folder_name,
                        name,
                        file_path,
                        file_type,
                        upload_date
                    FROM resources
                    WHERE folder_name = ? AND is_active = 1
                    ORDER BY upload_date DESC
                """, (purpose,))
                
                files = cursor.fetchall()
                if files:
                    resources.append({
                        'purpose': purpose,
                        'files': [{
                            'id': f[0],
                            'name': f[2],
                            'type': f[4],
                            'upload_date': f[5],
                            'download_path': f[3]
                        } for f in files]
                    })
            
            return resources
    except Exception as e:
        print(f"Error getting student resources: {e}")
        return []

def get_resource_file(file_id):
    """Get file information for download"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, file_path, file_type
                FROM resources
                WHERE id = ? AND is_active = 1
            """, (file_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"Error getting resource file: {e}")
        return None

def check_resource_access(student_id, resource_name):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) 
                FROM reservations 
                WHERE idno = ? 
                AND purpose = ? 
                AND status = 'Completed'
            """, (student_id, resource_name))
            
            count = cursor.fetchone()[0]
            return count > 0
    except Exception as e:
        print(f"Error checking resource access: {e}")
        return False

def get_file_info(file_path):
    """Get file information including size and last modified date"""
    try:
        stats = os.stat(file_path)
        return {
            'size': stats.st_size,
            'modified': datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'exists': True
        }
    except:
        return {
            'size': 0,
            'modified': None,
            'exists': False
        }
# student laboratory resources end

# student reservation start
def get_lab_computers(lab):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # Create table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lab_computers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lab TEXT NOT NULL,
                    computer_number INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'available',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(lab, computer_number)
                )
            """)
            
            # Get all computers for the lab
            cursor.execute("""
                SELECT computer_number, status
                FROM lab_computers
                WHERE lab = ?
                ORDER BY computer_number
            """, (lab,))
            
            computers = cursor.fetchall()
            return [{'id': comp[0], 'status': comp[1]} for comp in computers]
            
    except Exception as e:
        print(f"Error fetching lab computers: {e}")
        return []

def is_computer_available(lab, computer_number):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status 
                FROM lab_computers 
                WHERE lab = ? AND computer_number = ?
            """, (lab, computer_number))
            
            result = cursor.fetchone()
            return result[0] == 'available' if result else True
            
    except Exception as e:
        print(f"Error checking computer availability: {e}")
        return False

# student reservation end

# student session start
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

def get_user_session_info(student_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(sessions, 0) as sessions, course
                FROM users 
                WHERE idno = ?
            """, (student_id,))
            
            result = cursor.fetchone()
            if not result:
                return 15, 15, 0  # Default values if user not found
                
            current_sessions, course = result
            is_cs_course = any(program in course for program in ['BSIT', 'BSCS'])
            total_sessions = 30 if is_cs_course else 15
            
            if current_sessions != total_sessions:
                cursor.execute("""
                    UPDATE users 
                    SET sessions = ?
                    WHERE idno = ?
                """, (total_sessions, student_id))
                conn.commit()
                current_sessions = total_sessions
                
            available_sessions = int(current_sessions)
            used_sessions = total_sessions - available_sessions
            
            return total_sessions, available_sessions, used_sessions
    except Exception as e:
        print(f"Error getting session info: {e}")
        return 15, 15, 0  # Default values on error

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
# student session end



# student reservation start --not fully functional
def get_user_reservations(student_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.id, r.idno, r.purpose, r.lab, r.time_in, r.status, 
                       u.firstname, u.lastname
                FROM reservations r
                JOIN users u ON r.idno = u.idno
                WHERE r.idno = ?
                ORDER BY r.time_in DESC
            """, (student_id,))
            return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching user reservations: {e}")
        return []

def get_user_reservation_data(student_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT idno, firstname, lastname, course, sessions
                FROM users 
                WHERE idno = ?
            """, (student_id,))
            result = cursor.fetchone()
            if not result:
                return None
                
            user = dict(zip(['idno', 'firstname', 'lastname', 'course', 'sessions'], result))
            
            total_sessions = 30 if user['course'] in [
                'Bachelor of Science in Information Technology',
                'Bachelor of Science in Computer Science'
            ] else 15
            
            if user['sessions'] is None:
                user['sessions'] = total_sessions
                cursor.execute("UPDATE users SET sessions = ? WHERE idno = ?", 
                             (total_sessions, student_id))
                conn.commit()
                
            return user
    except Exception as e:
        print(f"Error getting user reservation data: {e}")
        return None

def get_all_reservations():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, u.firstname, u.lastname 
                FROM reservations r 
                JOIN users u ON r.idno = u.idno 
                ORDER BY r.time_in DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching reservations: {e}")
        return []

def create_reservation(student_id, lab, computer, time_in, purpose):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # Insert the reservation with Pending status
            cursor.execute("""
                INSERT INTO reservations (
                    idno, lab, computer_number, time_in, 
                    purpose, status, requested_time
                ) VALUES (?, ?, ?, ?, ?, 'Pending', datetime('now', 'localtime'))
            """, (student_id, lab, computer, time_in, purpose))
            
            new_id = cursor.lastrowid
            conn.commit()
            
            # Get the newly created reservation
            cursor.execute("""
                SELECT r.*, u.firstname, u.lastname 
                FROM reservations r
                JOIN users u ON r.idno = u.idno 
                WHERE r.id = ?
            """, (new_id,))
            new_reservation = cursor.fetchone()
            
            return True, new_id, new_reservation
            
    except Exception as e:
        print(f"Error creating reservation: {e}")
        return False, None, str(e)


def delete_user_record(record_id, student_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM reservations 
                WHERE id = ? AND idno = ?
            """, (record_id, student_id))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting record: {e}")
        return False
# student reservation end

# student history
def get_user_history(student_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    r.id,
                    r.idno,
                    u.firstname || ' ' || u.lastname as name,
                    r.purpose,
                    r.lab,
                    r.time_in,
                    r.time_out,
                    DATE(r.time_in) as date,
                    r.status
                FROM reservations r
                JOIN users u ON r.idno = u.idno
                WHERE r.idno = ?  
                ORDER BY r.time_in DESC
            """, (student_id,))
            records = cursor.fetchall()
            
            return [{
                'id': record[0],
                'idno': record[1],
                'name': record[2],
                'purpose': record[3],
                'laboratory': record[4],
                'login': record[5],
                'logout': record[6] if record[6] else 'Not logged out',
                'date': record[7],
                'status': record[8]
            } for record in records]
    except Exception as e:
        print(f"Error fetching user history: {e}")
        return []
# student history

# student feedback start
def add_user_feedback(student_id, reservation_id, feedback_text):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedback (idno, reservation_id, feedback_text)
                VALUES (?, ?, ?)
            """, (student_id, reservation_id, feedback_text))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error adding feedback: {e}")
        return False

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
# student feedback end





#ADMIN DBHELPER

# admin user validation start
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
# admin user validation end


# admin dashboard start
def get_dashboard_stats():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_students = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE status = 'Active'")
        current_sitins = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reservations")
        total_sitins = cursor.fetchone()[0]
        
        return total_students, current_sitins, total_sitins

def get_purpose_data():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                strftime('%m', time_in) as month,
                purpose,
                COUNT(*) as count
            FROM reservations
            WHERE strftime('%Y', time_in) = strftime('%Y', 'now')
            GROUP BY strftime('%m', time_in), purpose
            ORDER BY month, purpose
        """)
        return cursor.fetchall()

def get_points_leaderboard():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    u.idno,
                    u.firstname,
                    u.lastname,
                    u.course,
                    u.photo,
                    COALESCE(u.points, 0) as points,
                    r.id as reservation_id
                FROM users u
                JOIN reservations r ON u.idno = r.idno
                WHERE r.status = 'Active'
                ORDER BY u.points DESC
            """)
            return [{
                'idno': row[0],
                'name': f"{row[1]} {row[2]}",
                'course': row[3],
                'photo': row[4] or 'default.png',
                'points': row[5],
                'reservation_id': row[6]
            } for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting points leaderboard: {e}")
        return []

def add_student_point(student_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # Check if student has an active sit-in
            cursor.execute("""
                SELECT 1 FROM reservations 
                WHERE idno = ? AND status = 'Active'
            """, (student_id,))
            
            if not cursor.fetchone():
                return False, "Student must be actively sitting in to receive points"
            
            cursor.execute("SELECT points FROM users WHERE idno = ?", (student_id,))
            result = cursor.fetchone()
            current_points = result[0] if result and result[0] is not None else 0
            
            new_points = current_points + 1
            
            if new_points >= 3:
                # Add a new session and reset points
                cursor.execute("""
                    UPDATE users 
                    SET points = 0,
                        sessions = COALESCE(sessions, 0) + 1
                    WHERE idno = ?
                """, (student_id,))
                message = 'Points converted to a new session!'
            else:
                # Just update points
                cursor.execute("""
                    UPDATE users 
                    SET points = ?
                    WHERE idno = ?
                """, (new_points, student_id))
                message = f'Point added! ({new_points}/3 points)'
            
            conn.commit()
            return True, message
            
    except Exception as e:
        return False, str(e)

def get_student_leaderboard():
    """Get top 5 students with the most sit-ins"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.firstname, u.lastname, u.course, COUNT(r.id) as sit_in_count, u.photo
                FROM users u
                JOIN reservations r ON u.idno = r.idno
                WHERE r.status = 'Completed'
                GROUP BY u.idno
                ORDER BY sit_in_count DESC
                LIMIT 5
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error getting student leaderboard: {e}")
        return []
# admin dashboard end


# admin announcement start
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

def add_announcement(admin_id, title, message, author):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO announcements (admin_id, title, message, author)
                VALUES (?, ?, ?, ?)
            """, (admin_id, title, message, author))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error adding announcement: {e}")
        return False

def get_announcements():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.announcement_id, a.title, a.message, a.created_at, a.author
                FROM announcements a
                ORDER BY a.created_at DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching announcements: {e}")
        return []

def delete_announcement_by_id(announcement_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM announcements WHERE announcement_id = ?", (announcement_id,))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error deleting announcement: {e}")
        return False

def update_announcement(announcement_id, title, message, admin_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE announcements 
                SET title = ?, message = ?, admin_id = ?
                WHERE announcement_id = ?
            """, (title, message, admin_id, announcement_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating announcement: {e}")
        return False

def get_announcement_by_id(announcement_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.announcement_id, a.title, a.message, a.created_at, adm.username
                FROM announcements a
                JOIN admin adm ON a.admin_id = adm.admin_id
                WHERE a.announcement_id = ?
            """, (announcement_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"Error fetching announcement: {e}")
        return None

# admin announcement end


# admin search student start
def search_student_by_id(student_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT idno, firstname, middlename, lastname, course, year_level, 
                       COALESCE(sessions, 0) as remaining_sessions 
                FROM users 
                WHERE idno = ?
            """, (student_id,))
            student = cursor.fetchone()
            
            if student:
                full_name = f"{student[1]} {student[2] if student[2] else ''} {student[3]}".strip()
                
                return {
                    'id': student[0],
                    'name': full_name,
                    'course': student[4],
                    'year_level': student[5],
                    'remaining_sessions': int(student[6]),  # Consistent field name
                    'message': ("Student has reached maximum session limit" 
                              if int(student[6]) <= 0 
                              else f"Student has {int(student[6])} sessions remaining")
                }
            return None
            
    except Exception as e:
        raise Exception(f"Database error: {e}")
# admin search student end


# admin reservations start --not fully functional
def get_pending_reservations():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                r.id,
                r.idno,
                u.firstname || ' ' || COALESCE(u.middlename, '') || ' ' || u.lastname as name,
                u.course,
                r.purpose,
                r.lab,
                r.computer_number,
                strftime('%H:%M', r.time_in) as time_in,
                strftime('%Y-%m-%d', r.requested_time) as reservation_date,
                u.sessions,
                COALESCE(u.photo, 'default.png') as photo
            FROM reservations r
            JOIN users u ON r.idno = u.idno
            WHERE r.status = 'Pending'
            ORDER BY r.requested_time DESC
        """)
        
        columns = [column[0] for column in cursor.description]
        reservations = cursor.fetchall()
        
        result = []
        for r in reservations:
            reservation_dict = dict(zip(columns, r))
            # Ensure computer_number is properly formatted
            if 'computer_number' in reservation_dict and reservation_dict['computer_number']:
                reservation_dict['computer_number'] = str(reservation_dict['computer_number'])
            else:
                reservation_dict['computer_number'] = "N/A"
                
            result.append(reservation_dict)
            
        return result

def process_reservation_action(reservation_id, action):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            if action == 'approve':
                cursor.execute("""
                    UPDATE reservations 
                    SET status = 'Accepted',  -- Change status to 'Accepted'
                        time_in = datetime('now', 'localtime')
                    WHERE id = ?
                """, (reservation_id,))
                
                cursor.execute("""
                    UPDATE users 
                    SET sessions = sessions - 1
                    WHERE idno = (
                        SELECT idno FROM reservations WHERE id = ?
                    )
                """, (reservation_id,))
                
            elif action == 'decline':
                cursor.execute("""
                    UPDATE reservations 
                    SET status = 'Rejected'  -- Change status to 'Rejected'
                    WHERE id = ?
                """, (reservation_id,))
            
            conn.commit()
            return True, f'Reservation {action}d successfully'
            
    except Exception as e:
        return False, str(e)

def get_reservation_logs():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    r.id,
                    r.idno,
                    u.firstname || ' ' || COALESCE(u.middlename, '') || ' ' || u.lastname as name,
                    u.course,
                    r.purpose,
                    r.lab,
                    r.computer_number,
                    strftime('%Y-%m-%d %H:%M', r.time_in) as time_in,
                    COALESCE(u.sessions, 0) as sessions,
                    strftime('%Y-%m-%d', r.requested_time) as reservation_date,
                    r.status,
                    COALESCE(u.photo, 'default.png') as photo
                FROM reservations r
                JOIN users u ON r.idno = u.idno
                WHERE r.status IN ('Accepted', 'Rejected')
                ORDER BY r.requested_time DESC
            """)
            
            columns = [column[0] for column in cursor.description]
            reservations = cursor.fetchall()
            
            result = []
            for r in reservations:
                reservation_dict = dict(zip(columns, r))
                # Ensure computer_number is properly formatted
                if 'computer_number' in reservation_dict and reservation_dict['computer_number']:
                    reservation_dict['computer_number'] = str(reservation_dict['computer_number'])
                else:
                    reservation_dict['computer_number'] = "N/A"
                    
                result.append(reservation_dict)
                
            return result
    except Exception as e:
        print(f"Error fetching reservation logs: {e}")
        return []
# admin reservations end

# admin sesison start
def reset_student_sessions(student_id, course, session_limit):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET sessions = ?
                WHERE IDNO = ? AND course = ?
            """, (session_limit, student_id, course))
            
            if cursor.rowcount > 0:
                conn.commit()
                return True, None
            return False, "Student not found"
            
    except Exception as e:
        print(f"Database error: {e}")
        return False, str(e)

def reset_all_student_sessions():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET sessions = CASE 
                    WHEN course IN ('Bachelor of Science in Information Technology', 
                                  'Bachelor of Science in Computer Science',
                                  'BSIT', 'BSCS') THEN 30 
                    ELSE 15 
                END
            """)
            conn.commit()
            affected_rows = cursor.rowcount
            return True, f'Successfully reset {affected_rows} student sessions'
    except Exception as e:
        print(f"Database error: {e}")
        return False, str(e)

def update_null_sessions():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET sessions = CASE 
                    WHEN (course LIKE '%Information Technology%' 
                         OR course LIKE '%Computer Science%') THEN 30 
                    ELSE 15 
                END
                WHERE sessions IS NULL
            """)
            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating null sessions: {e}")
        return False

def get_current_sitins():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    r.idno,
                    u.firstname || ' ' || COALESCE(u.middlename, '') || ' ' || u.lastname as full_name,
                    r.purpose,
                    r.lab,
                    strftime('%Y-%m-%d %H:%M', r.time_in) as time_in,
                    strftime('%Y-%m-%d %H:%M', r.time_out) as time_out,
                    u.photo
                FROM reservations r
                JOIN users u ON r.idno = u.idno
                WHERE r.status = 'Active' AND r.time_out IS NULL
                ORDER BY r.time_in DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching current sit-ins: {e}")
        return []
# admin session end


# admin sitin start
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

def standardize_purpose(purpose):
    purpose_mapping = {
        'PHP PROGRAMMING': 'Php Programming',
        'JAVA PROGRAMMING': 'Java Programming',
        'C# PROGRAMMING': 'C# Programming',
        'C PROGRAMMING': 'C Programming',
        'ASP.NET PROGRAMMING': 'ASP.NET Programming',
        'DATABASE':'Database',
        'DIGITAL LOGIC & DESIGN':'Digital Logic & Design',
        'EMBEDDED SYSTEMS & IOT':'Embedded Systems & IOT',
        'SYSTEM INTGERATION & ARCHITECTURE':'System Integration & Architecture',
        'COMPUTER APPLICATION':'Computer Application',
        'PROJECT MANAGEMENT':'Project Management',
        'IT TRENDS':'IT Trends',
        'TECHNOPRENEURSHIP':'Technopreneurship',
        'CAPSTONE':'Capstone',
    }
    return purpose_mapping.get(purpose.upper(), purpose)

def create_sit_in_session(student_id, purpose, laboratory, computer):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # Check remaining sessions (convert to int)
            cursor.execute("SELECT remaining_sessions FROM users WHERE idno = ?", (student_id,))
            result = cursor.fetchone()
            
            if not result:
                return False, "Student not found"
                
            remaining = int(float(result[0])) if result[0] is not None else 0
            if remaining <= 0:
                return False, "No remaining sessions"
            
            # Create sit-in session - using correct column names from schema
            cursor.execute("""
                INSERT INTO reservations (idno, purpose, lab, computer_number, time_in, status)
                VALUES (?, ?, ?, ?, datetime('now'), 'Active')
            """, (student_id, purpose, laboratory, computer))
            
            # Update remaining sessions (ensure integer operation)
            cursor.execute("""
                UPDATE users 
                SET remaining_sessions = CAST(remaining_sessions AS INTEGER) - 1 
                WHERE idno = ?
            """, (student_id,))
            
            # Get updated session count (as integer)
            cursor.execute("SELECT CAST(remaining_sessions AS INTEGER) FROM users WHERE idno = ?", (student_id,))
            updated_sessions = cursor.fetchone()[0]
            
            conn.commit()
            return True, updated_sessions
            
    except Exception as e:
        print(f"Error creating sit-in session: {e}")
        return False, str(e)

def get_completed_sitins():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    u.photo,
                    r.idno,
                    u.firstname || ' ' || u.lastname as name,
                    r.purpose,
                    r.lab,
                    strftime('%Y-%m-%d %H:%M', r.time_in) as time_in,
                    strftime('%Y-%m-%d %H:%M', r.time_out) as time_out
                FROM reservations r
                JOIN users u ON r.idno = u.idno
                WHERE r.status = 'Completed'
                ORDER BY r.time_out DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching completed sit-ins: {e}")
        return []

def get_purpose_statistics():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN upper(purpose) = 'PHP' THEN 'Php'
                        WHEN upper(purpose) = 'JAVA' THEN 'Java'
                        WHEN upper(purpose) = 'C#' THEN 'C#'
                        WHEN upper(purpose) = 'C' THEN 'C'
                        WHEN upper(purpose) = 'ASP.NET' THEN 'ASP.NET'
                        WHEN upper(purpose) = 'DATABASE' THEN 'Database'
                        WHEN upper(purpose) = 'DIGITAL LOGIC & DESIGN' THEN 'Digital Logic & Design'
                        WHEN upper(purpose) = 'EMBEDDED SYSTEMS & IOT' THEN 'Embedded Systems & IOT'
                        WHEN upper(purpose) = 'SYSTEM INTEGRATION & ARCHITECTURE' THEN 'System Integration & Architecture'
                        WHEN upper(purpose) = 'COMPUTER APPLICATION' THEN 'Computer Application'
                        WHEN upper(purpose) = 'PROJECT MANAGEMENT' THEN 'Project Management'
                        WHEN upper(purpose) = 'IT TRENDS' THEN 'IT Trends'
                        WHEN upper(purpose) = 'TECHNOPRENEURSHIP' THEN 'Technopreneurship'
                        WHEN upper(purpose) = 'CAPSTONE' THEN 'Capstone'

                        ELSE purpose
                    END as standardized_purpose,
                    COUNT(*) as count
                FROM reservations
                WHERE status = 'Completed'
                GROUP BY standardized_purpose
            """)
            return dict(cursor.fetchall())
    except Exception as e:
        print(f"Error fetching purpose statistics: {e}")
        return {}

def get_lab_statistics():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lab, COUNT(*) as count
                FROM reservations
                WHERE status = 'Completed'
                GROUP BY lab
            """)
            return dict(cursor.fetchall())
    except Exception as e:
        print(f"Error fetching lab statistics: {e}")
        return {}
# admin sitin end

# admin logout student start
def logout_student_session(student_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # Update the reservation with logout time and status
            cursor.execute("""
                UPDATE reservations 
                SET time_out = datetime('now', 'localtime'),
                    status = 'Completed'
                WHERE idno = ? AND status = 'Active'
            """, (student_id,))
            
            # Get the updated logout time
            cursor.execute("""
                SELECT time_out 
                FROM reservations 
                WHERE idno = ? 
                ORDER BY time_out DESC 
                LIMIT 1
            """, (student_id,))
            
            logout_time = cursor.fetchone()
            conn.commit()
            
            return True, logout_time[0] if logout_time else None
            
    except Exception as e:
        print(f"Database error in logout_student_session: {e}")
        return False, str(e)
# admin logout student end

# admin computer control start
def update_multiple_computer_status(lab, computer_ids, status):
    """Update the status of multiple computers in a lab."""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # Update each computer's status
            for computer_id in computer_ids:
                cursor.execute("""
                    INSERT INTO lab_computers (lab, computer_number, status)
                    VALUES (?, ?, ?)
                    ON CONFLICT(lab, computer_number) 
                    DO UPDATE SET 
                        status = excluded.status
                """, (lab, computer_id, status))
            
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Error updating computer status: {e}")
        return False

def get_lab_computers(lab):
    """Fetch all computers in a lab with their current status."""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT computer_number, status
                FROM lab_computers
                WHERE lab = ?
                ORDER BY computer_number
            """, (lab,))
            return [{'id': row[0], 'status': row[1]} for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching lab computers: {e}")
        return []

# admin computer control end

# admin lab schedule start
def create_tables():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()

        # Add lab schedule table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lab_schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lab_number TEXT NOT NULL,
                schedule_date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def add_lab_schedule(lab_number, schedule_date, start_time, end_time, description):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lab_schedules (lab_number, schedule_date, start_time, end_time, description)
                VALUES (?, ?, ?, ?, ?)
            """, (lab_number, schedule_date, start_time, end_time, description))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error adding lab schedule: {e}")
        return False

def get_lab_schedules():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lab_schedules ORDER BY schedule_date, start_time")
            return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching lab schedules: {e}")
        return []

def delete_lab_schedule(schedule_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM lab_schedules WHERE schedule_id = ?", (schedule_id,))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error deleting lab schedule: {e}")
        return False

def generate_lab_schedule_pdf(schedules):
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Create custom styles for headers
    h1_style = ParagraphStyle(
        'H1',
        parent=title_style,
        fontSize=16,
        alignment=1,  # Center alignment
        spaceAfter=6
    )
    
    h2_style = ParagraphStyle(
        'H2',
        parent=heading_style,
        fontSize=14,
        alignment=1,
        spaceAfter=6
    )
    
    h3_style = ParagraphStyle(
        'H3',
        parent=heading_style,
        fontSize=12,
        alignment=1,
        spaceAfter=12
    )
    
    # Create the content elements
    elements = []
    
    # Add headers
    elements.append(Paragraph("University of Cebu Main Campus", h1_style))
    elements.append(Paragraph("College of Computer Studies", h2_style))
    elements.append(Paragraph("Computer Laboratory Sit-in Monitoring System", h3_style))
    elements.append(Paragraph("Laboratory Schedule", normal_style))
    elements.append(Spacer(1, 20))
    
    # Create table data
    data = [["Laboratory", "Date", "Start Time", "End Time", "Description"]]
    
    # Add schedule data to table
    for schedule in schedules:
        # Format times to 12-hour format
        start_time = schedule[3]
        end_time = schedule[4]
        
        # Add row to data
        data.append([
            schedule[1],  # Laboratory
            schedule[2],  # Date
            start_time,   # Start Time
            end_time,     # End Time
            schedule[5]   # Description
        ])
    
    # Create the table
    table = Table(data, colWidths=[doc.width/5.0]*5)
    
    # Add style to the table
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    
    table.setStyle(table_style)
    elements.append(table)
    
    # Build the PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer
# admin lab schedule end


# admin feedback start
def get_all_feedbacks():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    f.idno,
                    u.firstname || ' ' || u.lastname as student_name,
                    r.lab,
                    r.time_in,
                    f.feedback_text,
                    f.submitted_at
                FROM feedback f
                JOIN users u ON f.idno = u.idno
                JOIN reservations r ON f.reservation_id = r.id
                ORDER BY f.submitted_at DESC
            """)
            feedbacks = cursor.fetchall()
            
            return [{
                'idno': feedback[0],
                'student_name': feedback[1],
                'laboratory': feedback[2],
                'date': feedback[3],
                'message': feedback[4],
                'submitted_at': feedback[5]
            } for feedback in feedbacks]
    except Exception as e:
        print(f"Error fetching feedbacks: {e}")
        return []
# admin feedback end

# admin lab resources start
def get_resources(self, folder_name):
    try:
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT name, file_path, upload_date 
            FROM resources 
            WHERE folder = %s
            ORDER BY upload_date DESC
        """, (folder_name,))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error getting resources: {e}")
        return []

def save_resource(self, folder, filename, file_path):
    try:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO resources (folder, name, file_path, upload_date)
            VALUES (%s, %s, %s, NOW())
        """, (folder, filename, file_path))
        self.conn.commit()
        return True
    except Exception as e:
        print(f"Error saving resource: {e}")
        self.conn.rollback()
        return False
        
def add_lab_resource(lab_name, pc_count, status, description):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lab_resources (lab_name, pc_count, status, description)
                VALUES (?, ?, ?, ?)
            """, (lab_name, pc_count, status, description))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error adding lab resource: {e}")
        return False

def get_lab_resources():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT resource_id, lab_name, pc_count, status, description
                FROM lab_resources
                ORDER BY lab_name
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching lab resources: {e}")
        return []

def get_resource_by_id(resource_id):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT resource_id, lab_name, pc_count, status, description
                FROM lab_resources
                WHERE resource_id = ?
            """, (resource_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"Error fetching resource: {e}")
        return None

def update_lab_resource(resource_id, lab_name, pc_count, status, description):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lab_resources
                SET lab_name = ?, pc_count = ?, status = ?, description = ?
                WHERE resource_id = ?
            """, (lab_name, pc_count, status, description, resource_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating lab resource: {e}")
        return False

def delete_resource_file(folder_name, filename):
    """Delete resource file from database"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # Delete the record completely instead of just marking inactive
            cursor.execute("""
                DELETE FROM resources 
                WHERE folder_name = ? AND name = ?
            """, (folder_name, filename))
            
            conn.commit()
            
            # Verify deletion
            cursor.execute("""
                SELECT COUNT(*) FROM resources 
                WHERE folder_name = ? AND name = ?
            """, (folder_name, filename))
            
            count = cursor.fetchone()[0]
            return count == 0
            
    except Exception as e:
        print(f"Database error in delete_resource_file: {e}")
        return False
# admin lab resources end

# admin report/convert start

# admin report/convert start
def get_completed_reports():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    r.id,
                    r.idno,
                    u.firstname || ' ' || COALESCE(u.middlename, '') || ' ' || u.lastname as name,
                    r.purpose,
                    r.lab,
                    strftime('%Y-%m-%d %H:%M', r.time_in) as time_in,
                    strftime('%Y-%m-%d %H:%M', r.time_out) as time_out
                FROM reservations r
                JOIN users u ON r.idno = u.idno
                WHERE r.status = 'Completed'
                ORDER BY r.time_in DESC
            """)
            records = cursor.fetchall()
            
            # Convert to list of dictionaries
            return [{
                'id': record[0],
                'idno': record[1],
                'name': record[2],
                'purpose': record[3],
                'laboratory': record[4],
                'time_in': record[5],
                'time_out': record[6]
            } for record in records]
    except Exception as e:
        print(f"Error fetching completed reports: {e}")
        return []

def get_completed_sit_in_records():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    r.id as sit_in_number,
                    r.idno,
                    u.firstname || ' ' || u.lastname as name,
                    r.purpose,
                    r.lab,
                    strftime('%Y-%m-%d %H:%M', r.time_in) as login,
                    strftime('%Y-%m-%d %H:%M', r.time_out) as logout
                FROM reservations r
                JOIN users u ON r.idno = u.idno
                WHERE r.status = 'Completed'
                ORDER BY r.time_in DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching completed records: {e}")
        return []

def get_filtered_records(lab=None, purpose=None, date=None):
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    r.idno,
                    u.firstname || ' ' || COALESCE(u.middlename, '') || ' ' || u.lastname as name,
                    r.lab,
                    r.purpose,
                    strftime('%Y-%m-%d %H:%M', r.time_in) as time_in,
                    strftime('%Y-%m-%d %H:%M', r.time_out) as time_out
                FROM reservations r
                JOIN users u ON r.idno = u.idno
                WHERE r.status = 'Completed'
            """
            params = []
            
            if lab and lab != 'All Laboratories':
                query += " AND r.lab = ?"
                params.append(lab)
            if purpose and purpose != 'All Purposes':
                query += " AND r.purpose = ?"
                params.append(purpose)
            if date:
                query += " AND date(r.time_in) = ?"
                params.append(date)
                
            query += " ORDER BY r.time_in DESC"
            
            cursor.execute(query, params)
            records = cursor.fetchall()
            
            return [{
                'idno': record[0],
                'name': record[1],
                'laboratory': record[2],
                'purpose': record[3],
                'time_in': record[4],
                'time_out': record[5] if record[5] else 'Not logged out'
            } for record in records]
            
    except Exception as e:
        print(f"Error getting filtered records: {e}")
        return []

def export_to_csv(records):
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers with proper formatting
        writer.writerow(['UNIVERSITY OF CEBU MAIN CAMPUS'])
        writer.writerow(['COLLEGE OF COMPUTER STUDIES'])
        writer.writerow(['COMPUTER LABORATORY SIT-IN MONITORING SYSTEM'])
        writer.writerow([])  # Empty row for spacing
        writer.writerow(['Generated on:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])  # Empty row for spacing
        writer.writerow(['ID Number', 'Name', 'Laboratory', 'Purpose', 'Login Time', 'Logout Time'])
        
        # Write data
        for record in records:
            writer.writerow([
                record['idno'],
                record['name'],
                record['laboratory'],
                record['purpose'],
                record['time_in'],
                record['time_out']
            ])
        
        # Ensure proper encoding and return bytes
        output.seek(0)
        return io.BytesIO(output.getvalue().encode('utf-8-sig'))
    except Exception as e:
        print(f"Error exporting to CSV: {e}")
        return None

def export_to_excel(records):
    try:
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()
        
        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'font_name': 'Arial'
        })
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'border': 1,
            'bg_color': '#603A75',
            'font_color': 'white'
        })
        data_format = workbook.add_format({
            'align': 'center',
            'border': 1
        })
        
        # Write titles and headers
        worksheet.merge_range('A1:F1', 'UNIVERSITY OF CEBU MAIN CAMPUS', title_format)
        worksheet.merge_range('A2:F2', 'COLLEGE OF COMPUTER STUDIES', title_format)
        worksheet.merge_range('A3:F3', 'COMPUTER LABORATORY SIT-IN MONITORING SYSTEM', title_format)
        
        # Write data with proper formatting
        headers = ['ID Number', 'Name', 'Laboratory', 'Purpose', 'Login Time', 'Logout Time']
        for col, header in enumerate(headers):
            worksheet.write(5, col, header, header_format)
            worksheet.set_column(col, col, 15)  # Set column width
        
        for row, record in enumerate(records, start=6):
            data = [
                record['idno'],
                record['name'],
                record['laboratory'],
                record['purpose'],
                record['time_in'],
                record['time_out']
            ]
            for col, value in enumerate(data):
                worksheet.write(row, col, value, data_format)
        
        workbook.close()
        output.seek(0)
        return output
    except Exception as e:
        print(f"Error exporting to Excel: {e}")
        return None

def export_to_pdf(records):
    try:
        buffer = io.BytesIO()
        
        # Create PDF document with proper margins
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Add headers with proper styling
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,
            spaceAfter=10
        )
        
        elements.extend([
            Paragraph("UNIVERSITY OF CEBU MAIN CAMPUS", title_style),
            Paragraph("COLLEGE OF COMPUTER STUDIES", title_style),
            Paragraph("COMPUTER LABORATORY SIT-IN MONITORING SYSTEM", title_style),
            Spacer(1, 20)
        ])
        
        # Create table with data
        table_data = [['ID Number', 'Name', 'Laboratory', 'Purpose', 'Login Time', 'Logout Time']]
        for record in records:
            table_data.append([
                record['idno'],
                record['name'],
                record['laboratory'],
                record['purpose'],
                record['time_in'],
                record['time_out']
            ])
        
        # Style the table
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#603A75')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BOX', (0, 0), (-1, -1), 2, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        buffer.close() 

        final_buffer = io.BytesIO(pdf_data)
        final_buffer.seek(0)
        return final_buffer
    except Exception as e:
        print(f"Error exporting to PDF: {e}")
        return None
# admin report end


#ADMIN DBHELPER






#debug purposes
def add_test_resource():
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO resources (folder_name, name, file_path, file_type, is_active)
                VALUES 
                ('IT Trends', 'Sample.pdf', 'path/to/sample.pdf', 'pdf', 1),
                ('Java Programming', 'Example.java', 'path/to/example.java', 'java', 1)
            """)
            conn.commit()
            return True
    except Exception as e:
        print(f"Error adding test resource: {e}")
        return False

def cleanup_orphaned_sitins():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        # Delete sit-in records where the user no longer exists
        cursor.execute("""
            DELETE FROM reservations 
            WHERE idno NOT IN (SELECT idno FROM users)
        """)
        conn.commit()