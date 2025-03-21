from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from dbhelper import *
from werkzeug.security import check_password_hash
import os
from werkzeug.utils import secure_filename
import time

app = Flask(__name__, static_folder='static')
app.secret_key = 'tonifowlersupersecretkey'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  

with app.app_context():
    create_tables()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#admin route

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # First check admin credentials
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM admin WHERE username = ? AND password = ?", (username, password))
            admin = cursor.fetchone()
            
            if admin:
                session['admin_id'] = admin[0]
                session['admin_username'] = admin[1]
                return redirect(url_for('admin_dashboard'))
        
        # If not admin, check student credentials
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT IDNO, Password, username FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            
            if user:
                session['username'] = username
                session['student_id'] = user[0]
                return redirect(url_for('Dashboard'))
            
        flash("Invalid credentials. Please try again.", "error")
    
    return render_template('login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
        
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        
        # Get total students
        cursor.execute("SELECT COUNT(*) FROM users")
        total_students = cursor.fetchone()[0]
        
        # Change 'Ongoing' to 'Active' to match the status used in sit-in
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE status = 'Active'")
        current_sitins = cursor.fetchone()[0]
        
        # Get total sit-ins
        cursor.execute("SELECT COUNT(*) FROM reservations")
        total_sitins = cursor.fetchone()[0]
        
        # Get purpose counts per month
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
        purpose_data = cursor.fetchall()
        
        # Format data for the chart
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        purposes = ['C#', 'C', 'ASP.NET', 'Java', 'Php']
        
        chart_data = {purpose: [0] * 12 for purpose in purposes}
        
        for month_num, purpose, count in purpose_data:
            month_index = int(month_num) - 1
            if purpose in chart_data:
                chart_data[purpose][month_index] = count

    return render_template('admin/admindashboard.html',
                         chart_data=chart_data,
                         months=months,
                         total_students=total_students,
                         current_sitins=current_sitins,
                         total_sitins=total_sitins)
        
    # Get total registered students
    cursor.execute("SELECT COUNT(*) FROM users")
    total_students = cursor.fetchone()[0]
    
    # Get current sit-ins
    cursor.execute("SELECT COUNT(*) FROM reservations WHERE status = 'Active'")
    current_sitins = cursor.fetchone()[0]
    
    # Get total sit-ins
    cursor.execute("SELECT COUNT(*) FROM reservations")
    total_sitins = cursor.fetchone()[0]
    
    # Get monthly statistics for labs
    cursor.execute("""
        SELECT strftime('%m', time_in) as month, lab, COUNT(*) as count
        FROM reservations
        GROUP BY month, lab
        ORDER BY month
    """)
    lab_stats = cursor.fetchall()
    
    return render_template('admin/admindashboard.html', 
                         total_students=total_students,
                         current_sitins=current_sitins,
                         total_sitins=total_sitins,
                         lab_stats=lab_stats)

@app.route('/admin/sit-in')
def admin_sitin():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, r.idno, u.firstname, u.lastname, r.purpose, r.lab, r.time_in, 
                   CASE 
                       WHEN r.status = 'Active' THEN 'Sit-in'
                       ELSE r.status 
                   END as status
            FROM reservations r
            JOIN users u ON r.idno = u.idno
            ORDER BY r.time_in DESC
        """)
        rows = cursor.fetchall()
        
        reservations = []
        for row in rows:
            reservations.append({
                'id': row[0],
                'idno': row[1],
                'name': f"{row[2]} {row[3]}",
                'purpose': row[4],
                'lab': row[5],
                'time_in': row[6],
                'status': row[7]
            })
    
    return render_template('admin/adminsitin.html', reservations=reservations)

@app.route('/admin/search_student/<student_id>')
def search_student(student_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT idno, firstname, middlename, lastname, course, year_level, 
                       COALESCE(sessions, 0) as sessions 
                FROM users 
                WHERE idno = ?
            """, (student_id,))
            student = cursor.fetchone()
            
            if student:
                full_name = f"{student[1]} {student[2] if student[2] else ''} {student[3]}".strip()
                sessions_remaining = int(student[6] or 0)  # Convert to integer with null safety
                
                if sessions_remaining <= 0:
                    message = "Student has reached maximum session limit"
                else:
                    message = f"Student has {sessions_remaining} sessions remaining"
                    
                return jsonify({
                    'id': student[0],
                    'name': full_name,
                    'course': student[4],
                    'year_level': student[5],
                    'remainingSession': sessions_remaining,
                    'message': message
                })
            
            return jsonify({'error': f'No student found with ID: {student_id}'}), 404
            
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/reports')
def admin_reports():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    return render_template('admin/reports.html')

@app.route('/admin/feedback')
def admin_feedback():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
        
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
        
        formatted_feedbacks = []
        for feedback in feedbacks:
            formatted_feedbacks.append({
                'idno': feedback[0],
                'student_name': feedback[1],
                'laboratory': feedback[2],
                'date': feedback[3],
                'message': feedback[4],
                'submitted_at': feedback[5]
            })
        
    return render_template('admin/feedback.html', feedbacks=formatted_feedbacks)

@app.route('/admin/announcement', methods=['GET', 'POST'])
def admin_announcement():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        author = request.form.get('author')  # Get the selected author from the form
        admin_id = session['admin_id']
        
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO announcements (admin_id, title, message, author)
                    VALUES (?, ?, ?, ?)
                """, (admin_id, title, message, author))
                conn.commit()
                flash('Announcement added successfully', 'success')
            except Exception as e:
                print(f"Error adding announcement: {e}")
                flash('Failed to add announcement', 'error')
                
    # Fetch all announcements for display
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.announcement_id, a.title, a.message, a.created_at, a.author
            FROM announcements a
            ORDER BY a.created_at DESC
        """)
        announcements = cursor.fetchall()
        
    # Define available authors
    authors = ['CSS Admin', 'CSS Dean', 'Sit-in Supervisor']
        
    return render_template('admin/adminannouncement.html', 
                         announcements=announcements,
                         authors=authors)

@app.route('/admin/announcement/delete/<int:announcement_id>')
def delete_announcement(announcement_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
        
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM announcements WHERE announcement_id = ?", (announcement_id,))
            conn.commit()
            flash('Announcement deleted successfully', 'success')
        except Exception as e:
            print(f"Error deleting announcement: {e}")
            flash('Failed to delete announcement', 'error')
            
    return redirect(url_for('admin_announcement'))

@app.route('/admin/add_announcement', methods=['POST'])
def admin_add_announcement():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
        
    title = request.form.get('title')
    content = request.form.get('content')
    
    if add_announcement(title, content):
        flash('Announcement added successfully', 'success')
    else:
        flash('Failed to add announcement', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/announcement/edit/<int:announcement_id>', methods=['GET', 'POST'])
def edit_announcement(announcement_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        author = request.form.get('author')
        admin_id = session['admin_id']
        
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE announcements 
                    SET title = ?, message = ?, admin_id = ?
                    WHERE announcement_id = ?
                """, (title, message, admin_id, announcement_id))
                conn.commit()
                flash('Announcement updated successfully', 'success')
            except Exception as e:
                print(f"Error updating announcement: {e}")
                flash('Failed to update announcement', 'error')
                
        return redirect(url_for('admin_announcement'))
    
    # GET request - fetch announcement data for editing
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.announcement_id, a.title, a.message, a.created_at, adm.username
            FROM announcements a
            JOIN admin adm ON a.admin_id = adm.admin_id
            WHERE a.announcement_id = ?
        """, (announcement_id,))
        announcement = cursor.fetchone()
        
    if announcement:
        return render_template('admin/adminannouncement.html', announcement=announcement)
    else:
        flash('Announcement not found', 'error')
        return redirect(url_for('admin_announcement'))

@app.route('/admin/sit_in_student', methods=['POST'])
def sit_in_student():
    data = request.get_json()
    student_id = data.get('student_id')
    purpose = data.get('purpose', '').strip()
    laboratory = data.get('laboratory')
    
    # Standardize purpose case
    purpose_mapping = {
        'PHP': 'Php',
        'JAVA': 'Java',
        'C#': 'C#',
        'C': 'C',
        'ASP.NET': 'ASP.NET'
    }
    
    purpose = purpose_mapping.get(purpose.upper(), purpose)
    
    if not all([student_id, purpose, laboratory]):
        return jsonify({'error': 'Missing required data'}), 400
    
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # First check if student exists and get their course and sessions
            cursor.execute("""
                SELECT COALESCE(sessions, 0) as sessions, course 
                FROM users 
                WHERE idno = ?
            """, (student_id,))
            result = cursor.fetchone()
            
            if not result:
                return jsonify({'error': 'Student not found'}), 404
                
            current_sessions = int(result[0] or 0)  # Handle NULL sessions
            course = result[1]
            
            # Set total sessions based on course
            total_sessions = 30 if course in [
                'Bachelor of Science in Information Technology',
                'Bachelor of Science in Computer Science'
            ] else 15
            
            # Initialize sessions if it's NULL
            if current_sessions == 0:
                current_sessions = total_sessions
                cursor.execute("""
                    UPDATE users 
                    SET sessions = ? 
                    WHERE idno = ?
                """, (total_sessions, student_id))
            
            if current_sessions <= 0:
                return jsonify({
                    'error': 'No remaining sessions available'
                }), 400
            
            # Check if student already has an active sit-in
            cursor.execute("""
                SELECT COUNT(*) FROM reservations 
                WHERE idno = ? AND status = 'Active'
            """, (student_id,))
            active_sessions = cursor.fetchone()[0]
            
            if active_sessions > 0:
                return jsonify({
                    'error': 'Student already has an active sit-in session'
                }), 400
            
            # Create sit-in record
            cursor.execute("""
                INSERT INTO reservations (idno, purpose, lab, time_in, status)
                VALUES (?, ?, ?, datetime('now', 'localtime'), 'Active')
            """, (student_id, purpose, laboratory))
            
            # Update remaining sessions
            cursor.execute("""
                UPDATE users 
                SET sessions = sessions - 1 
                WHERE idno = ?
            """, (student_id,))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'remaining_sessions': current_sessions - 1,
                'message': f'Sit-in recorded successfully. {current_sessions - 1} sessions remaining.'
            })
            
    except Exception as e:
        print(f"Error in sit_in_student: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/current-sitin')
def admin_current_sitin():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        # Get current sit-ins
        cursor.execute("""
            SELECT 
                r.idno,
                u.firstname || ' ' || COALESCE(u.middlename, '') || ' ' || u.lastname as full_name,
                r.purpose,
                r.lab,
                r.time_in
            FROM reservations r
            JOIN users u ON r.idno = u.idno
            WHERE r.status = 'Active'
            ORDER BY r.time_in DESC
        """)
        current_sitins = cursor.fetchall()
        
        # Get purpose counts with case-insensitive grouping
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN upper(purpose) = 'PHP' THEN 'Php'
                    WHEN upper(purpose) = 'JAVA' THEN 'Java'
                    WHEN upper(purpose) = 'C#' THEN 'C#'
                    WHEN upper(purpose) = 'C' THEN 'C'
                    WHEN upper(purpose) = 'ASP.NET' THEN 'ASP.NET'
                    ELSE purpose
                END as standardized_purpose,
                COUNT(*) as count
            FROM reservations
            WHERE status = 'Active'
            GROUP BY standardized_purpose
        """)
        purpose_counts = dict(cursor.fetchall())
    
    return render_template('admin/admincurrentsitin.html', 
                         sitins=current_sitins,
                         purpose_counts=purpose_counts)

@app.route('/admin/logout_student', methods=['POST'])
def logout_student():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.get_json()
    student_id = data.get('student_id')
    
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            
            # Update the session count for the student
            cursor.execute("""
                UPDATE users 
                SET sessions = sessions - 1 
                WHERE idno = ?
            """, (student_id,))
            
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
            
            logout_time = cursor.fetchone()[0]
            conn.commit()
            
            return jsonify({
                'success': True,
                'logout_time': logout_time
            })
            
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))

#admin route


#route for students end/user end
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, u.firstname, u.lastname 
            FROM reservations r 
            JOIN users u ON r.idno = u.idno 
            ORDER BY r.time_in DESC
        """)
        reservations = cursor.fetchall()

    return render_template('student/index.html', reservations=reservations)

@app.route('/Dashboard')
def Dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    rejection_message = session.pop('rejection_message', None)
    
    print(f"Debug - User in session: {session['username']}")
    print(f"Debug - Student ID: {session['student_id']}")
    
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, r.idno, r.purpose, r.lab, r.time_in, r.status, 
                   u.firstname, u.lastname
            FROM reservations r
            JOIN users u ON r.idno = u.idno
            WHERE r.idno = ?
            ORDER BY r.time_in DESC
        """, (session['student_id'],))
        reservations = cursor.fetchall()
        
        print(f"Debug - Found reservations: {reservations}")
    
    return render_template('student/index.html', 
                         username=session['username'],
                         reservations=reservations,
                         rejection_message=rejection_message)

@app.route('/Profile', methods=['GET', 'POST'])
def Profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        data = {
            'firstname': request.form.get('firstname', ''),
            'lastname': request.form.get('lastname', ''),
            'middlename': request.form.get('middlename', ''),
            'email': request.form.get('email', ''),
            'course': request.form.get('course', ''),
            'level': request.form.get('yearlevel', ''),
            'address': request.form.get('address', ''),
            'photo': None
        }

        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                try:
                    if not os.path.exists(app.config['UPLOAD_FOLDER']):
                        os.makedirs(app.config['UPLOAD_FOLDER'])

                    filename = secure_filename(file.filename)
                    timestamp = int(time.time())
                    photo_filename = f"{timestamp}_{filename}"

                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
                    file.save(file_path)

                    data['photo'] = photo_filename
                    
                    print(f"Photo saved as: {photo_filename}")  
                except Exception as e:
                    print(f"Error saving photo: {e}")
                    flash('Error uploading photo.', 'error')

        print("Data being sent to update_user_profile:", data)

        if update_user_profile(session['student_id'], data):
            flash('Profile updated successfully!', 'success')
        else:
            flash('Error updating profile.', 'error')
        
        return redirect(url_for('Profile'))

    user_profile = get_user_profile(session['student_id'])
    print("User profile data:", user_profile) 
    return render_template('student/profile.html', user=user_profile)

@app.route('/save_photo', methods=['POST'])
def save_photo():
    if 'username' not in session:
        return redirect(url_for('login'))

    current_user = get_user_profile(session['student_id'])
    
    if 'photo' not in request.files:
        flash('No photo uploaded', 'error')
        return redirect(url_for('Profile'))
    
    file = request.files['photo']
    if file.filename == '':
        flash('No photo selected', 'error')
        return redirect(url_for('Profile'))

    if file:
        try:
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            filename = secure_filename(file.filename)
            timestamp = int(time.time())
            photo_filename = f"{timestamp}_{filename}"

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
            file.save(file_path)

            data = {
                'firstname': current_user[2],   
                'lastname': current_user[1],    
                'middlename': current_user[3],   
                'email': current_user[6],        
                'course': current_user[4],      
                'level': current_user[5],       
                'address': current_user[7],      
                'photo': photo_filename          
            }
            
            if update_user_profile(session['student_id'], data):
                flash('Photo updated successfully!', 'success')
            else:
                flash('Error updating photo in database', 'error')
                
        except Exception as e:
            print(f"Error saving photo: {e}")
            flash('Error saving photo', 'error')
    
    return redirect(url_for('Profile'))

@app.route('/Announcement')
def Announcement():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.announcement_id, a.title, a.message, a.created_at, a.author
            FROM announcements a
            ORDER BY a.created_at DESC
        """)
        announcements = cursor.fetchall()
    return render_template('student/announcement.html', announcements=announcements)

@app.route('/Session')
def Session():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        # Get both sessions and course
        cursor.execute("""
            SELECT COALESCE(sessions, 0) as sessions, course
            FROM users 
            WHERE idno = ?
        """, (session['student_id'],))
        
        result = cursor.fetchone()
        if result:
            current_sessions, course = result
            # Set total sessions based on course
            total_sessions = 30 if course in [
                'Bachelor of Science in Information Technology',
                'Bachelor of Science in Computer Science'
            ] else 15
            
            # Handle NULL or invalid sessions value
            available_sessions = int(current_sessions or 0)
            
            # If sessions is 0 or NULL, initialize it
            if available_sessions == 0:
                available_sessions = total_sessions
                cursor.execute("""
                    UPDATE users 
                    SET sessions = ? 
                    WHERE idno = ?
                """, (total_sessions, session['student_id']))
                conn.commit()
            
            used_sessions = total_sessions - available_sessions
        else:
            total_sessions = 15  # Default to lower limit if user not found
            available_sessions = 15
            used_sessions = 0
            
    return render_template('student/session.html', 
                         total_sessions=total_sessions,
                         available_sessions=available_sessions,
                         used_sessions=used_sessions)

@app.route('/History')
def History():
    if 'username' not in session:
        return redirect(url_for('login'))
        
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
        """, (session['student_id'],))
        history_records = cursor.fetchall()

        history = []
        for record in history_records:
            history.append({
                'id': record[0],
                'idno': record[1],
                'name': record[2],
                'purpose': record[3],
                'laboratory': record[4],
                'login': record[5],
                'logout': record[6] if record[6] else 'Not logged out',
                'date': record[7],
                'status': record[8]
            })
            
    return render_template('student/history.html', history=history)

@app.route('/delete_record/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            # Verify the record belongs to the logged-in user
            cursor.execute("""
                DELETE FROM reservations 
                WHERE id = ? AND idno = ?
            """, (record_id, session['student_id']))
            conn.commit()
            
            if cursor.rowcount > 0:
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Record not found'}), 404
                
    except Exception as e:
        print(f"Error deleting record: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/Reservation', methods=['GET', 'POST'])
def Reservation():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    if 'student_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT idno, firstname, middlename, lastname, 
                   COALESCE(sessions, 30) as sessions 
            FROM users 
            WHERE idno = ?
        """, (session['student_id'],))
        user = cursor.fetchone()

        if user:
            user_data = {
                "idno": user[0],
                "firstname": user[1],
                "middlename": user[2] if user[2] else '',
                "lastname": user[3],
                "sessions": user[4]
            }
            
            if request.method == 'POST':
                purpose = request.form['purpose']
                lab = request.form['lab']
                time_in = request.form['time_in']

                cursor.execute("""
                    INSERT INTO reservations (idno, purpose, lab, time_in, status)
                    VALUES (?, ?, ?, ?, 'Pending')
                """, (user_data["idno"], purpose, lab, time_in))
                
                conn.commit()
                return redirect(url_for('Dashboard'))
                
        else:
            user_data = None
            
    except Exception as e:
        print(f"Error in database query: {e}")
        user_data = None
    finally:
        conn.close()
        
    return render_template('student/reservation.html', user=user_data)

@app.route('/submit_reservation', methods=['POST'])
def submit_reservation():
    if 'username' not in session:
        flash("You must be logged in to make a reservation.", "warning")
        return redirect(url_for('login'))

    student_id = session['student_id']
    purpose = request.form['purpose']
    lab = request.form['lab']
    time_in = request.form['time_in']

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT sessions, course FROM users WHERE idno = ?", (student_id,))
        user = cursor.fetchone()

        if user:
            current_sessions, course = user
            # Set total sessions based on course
            total_sessions = 30 if course in [
                'Bachelor of Science in Information Technology',
                'Bachelor of Science in Computer Science'
            ] else 15

            if current_sessions > 0:
                cursor.execute("""
                    INSERT INTO reservations (idno, purpose, lab, time_in, status) 
                    VALUES (?, ?, ?, ?, 'Pending')
                """, (student_id, purpose, lab, time_in))
                
                conn.commit()
                flash("Reservation submitted successfully!", "success")
            else:
                flash("No remaining sessions available!", "danger")
        else:
            flash("User not found!", "error")

    except Exception as e:
        print(f"Error in reservation submission: {e}")
        flash("An error occurred while submitting your reservation.", "error")
    finally:
        conn.close()

    return redirect(url_for('Dashboard'))

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        student_id = session['student_id']
        feedback_text = data.get('feedback')
        reservation_id = data.get('reservation_id')

        if not feedback_text:
            return jsonify({'success': False, 'error': 'Feedback text is required'}), 400
        if not reservation_id:
            return jsonify({'success': False, 'error': 'Reservation ID is required'}), 400

        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedback (idno, reservation_id, feedback_text)
                VALUES (?, ?, ?)
            """, (student_id, reservation_id, feedback_text))
            conn.commit()
            return jsonify({'success': True})

    except Exception as e:
        print(f"Error submitting feedback: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        course = request.form['course']
        # Set session limit based on course
        session_limit = 30 if course in ['Bachelor of Science in Information Technology', 
                                       'Bachelor of Science in Computer Science'] else 15
        
        user_data = {
            'idno': request.form['idno'],
            'lastname': request.form['lastname'],
            'firstname': request.form['firstname'],
            'middlename': request.form.get('middlename', ''),  
            'course': course,
            'year_level': request.form['level'],  
            'email': request.form['email'],
            'username': request.form['username'],
            'password': generate_password_hash(request.form['password']),
            'sessions': session_limit  # Set initial sessions based on course
        }
        
        if add_user(user_data):
            flash(f"Registration successful! Your maximum session limit is {session_limit}.", "success")
            return redirect(url_for('login'))
    
    return render_template('student/register.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not all([username, new_password, confirm_password]):
            flash("All fields are required.", "error")
        elif new_password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            if update_password(username, new_password):
                flash("Password updated successfully. Please log in.", "success")
                return redirect(url_for('login'))
            flash("Password update failed - User not found.", "error")
    
    return render_template('password.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

