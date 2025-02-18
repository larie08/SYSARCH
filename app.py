from flask import Flask, render_template, request, redirect, url_for, session, flash
from dbhelper import *
from werkzeug.security import check_password_hash
import os
from werkzeug.utils import secure_filename
import time

app = Flask(__name__)
app.secret_key = 'tonifowlersupersecretkey'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

with app.app_context():
    create_tables()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    # Fetch user's reservations
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, u.firstname, u.lastname 
            FROM reservations r 
            JOIN users u ON r.idno = u.idno 
            ORDER BY r.time_in DESC
        """)
        reservations = cursor.fetchall()

    return render_template('index.html', reservations=reservations)

@app.route('/Dashboard')
def Dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    print(f"Debug - User in session: {session['username']}")
    print(f"Debug - Student ID: {session['student_id']}")
    
    # Fetch user's reservations
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
    
    return render_template('index.html', 
                         username=session['username'],
                         reservations=reservations)

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

        # Handle photo upload
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                try:
                    # Create upload directory if it doesn't exist
                    if not os.path.exists(app.config['UPLOAD_FOLDER']):
                        os.makedirs(app.config['UPLOAD_FOLDER'])

                    # Generate unique filename
                    filename = secure_filename(file.filename)
                    timestamp = int(time.time())
                    photo_filename = f"{timestamp}_{filename}"
                    
                    # Save the file
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
                    file.save(file_path)
                    
                    # Update data dictionary with new photo filename
                    data['photo'] = photo_filename
                    
                    print(f"Photo saved as: {photo_filename}")  # Debug print
                except Exception as e:
                    print(f"Error saving photo: {e}")
                    flash('Error uploading photo.', 'error')

        # Debug print
        print("Data being sent to update_user_profile:", data)

        # Update profile in database
        if update_user_profile(session['student_id'], data):
            flash('Profile updated successfully!', 'success')
        else:
            flash('Error updating profile.', 'error')
        
        return redirect(url_for('Profile'))

    # GET request - show profile
    user_profile = get_user_profile(session['student_id'])
    print("User profile data:", user_profile)  # Add this debug print
    return render_template('profile.html', user=user_profile)

@app.route('/save_photo', methods=['POST'])
def save_photo():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Get existing user data first
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
            # Create upload directory if it doesn't exist
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            # Generate unique filename
            filename = secure_filename(file.filename)
            timestamp = int(time.time())
            photo_filename = f"{timestamp}_{filename}"
            
            # Save the file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
            file.save(file_path)
            
            # Prepare data with existing user information
            data = {
                'firstname': current_user[2],    # firstname
                'lastname': current_user[1],     # lastname
                'middlename': current_user[3],   # middlename
                'email': current_user[6],        # email
                'course': current_user[4],       # course
                'level': current_user[5],        # year_level
                'address': current_user[7],      # address
                'photo': photo_filename          # new photo
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
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('announcement.html')

@app.route('/Session')
def Session():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('session.html')

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
                DATE(r.time_in) as date
            FROM reservations r
            JOIN users u ON r.idno = u.idno
            ORDER BY r.time_in DESC
        """)
        history_records = cursor.fetchall()
        
        # Convert to list of dictionaries for easier template handling
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
                'date': record[7]
            })
            
    return render_template('history.html', history=history)

@app.route('/Reservation', methods=['GET', 'POST'])
def Reservation():
    print(f"Reservation route - Session contents: {session}")  # Debug print
    
    if 'username' not in session:
        return redirect(url_for('login'))
        
    if 'student_id' not in session:
        print("No student_id in session!")  # Debug print
        flash("Please log in again.", "error")
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT idno, firstname, middlename, lastname, sessions FROM users WHERE idno = ?", (session['student_id'],))
        user = cursor.fetchone()
        print(f"Found user: {user}")  # Debug print

        if user:
            user_data = {
                "idno": user[0],
                "firstname": user[1],
                "middlename": user[2] if user[2] else '',
                "lastname": user[3],
                "sessions": user[4] if user[4] else 0
            }
        else:
            user_data = None
            print("No user found with student_id:", session['student_id'])  # Debug print
    except Exception as e:
        print(f"Error in database query: {e}")  # Debug print
        user_data = None

    # Handle form submission
    if request.method == 'POST':
        purpose = request.form['purpose']
        lab = request.form['lab']
        time_in = request.form['time_in']
        remaining_sessions = int(user_data["sessions"])

        if remaining_sessions > 0:
            new_sessions = remaining_sessions - 1
            cursor.execute("UPDATE users SET sessions = ? WHERE idno = ?", (new_sessions, user_data["idno"]))
            conn.commit()

            # Save reservation
            cursor.execute("INSERT INTO reservations (idno, purpose, lab, time_in) VALUES (?, ?, ?, ?)", (user_data["idno"], purpose, lab, time_in))
            conn.commit()

            flash("Reservation successful! Remaining sessions: " + str(new_sessions), "success")
        else:
            flash("No remaining sessions. Please contact an admin.", "error")

    conn.close()
    return render_template('reservation.html', user=user_data)

@app.route('/submit_reservation', methods=['POST'])
def submit_reservation():
    if 'username' not in session:
        flash("You must be logged in to make a reservation.", "warning")
        return redirect(url_for('login'))

    student_id = session['student_id']
    purpose = request.form['purpose']
    lab = request.form['lab']
    time_in = request.form['time_in']

    print(f"Debug - Submitting reservation for student: {student_id}")  # Debug print
    print(f"Debug - Form data: purpose={purpose}, lab={lab}, time={time_in}")  # Debug print

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    try:
        # Get current sessions
        cursor.execute("SELECT sessions FROM users WHERE idno = ?", (student_id,))
        user = cursor.fetchone()
        print(f"Debug - User sessions: {user}")  # Debug print

        if user and user[0] > 0:
            new_sessions = user[0] - 1

            # Update sessions in database
            cursor.execute("UPDATE users SET sessions = ? WHERE idno = ?", (new_sessions, student_id))

            # Insert reservation record with status
            cursor.execute("""
                INSERT INTO reservations (idno, purpose, lab, time_in, status) 
                VALUES (?, ?, ?, ?, 'Pending')
            """, (student_id, purpose, lab, time_in))
            
            print(f"Debug - Reservation inserted")  # Debug print
            
            conn.commit()
            flash("Reservation submitted successfully!", "success")
        else:
            flash("No remaining sessions available!", "danger")

    except Exception as e:
        print(f"Error in reservation submission: {e}")
        flash("An error occurred while submitting your reservation.", "error")
    finally:
        conn.close()

    return redirect(url_for('Dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT IDNO, Password, Username FROM users WHERE Username = ?", (username,))
            user = cursor.fetchone()
            
            if user:  # Simplified the check
                session['username'] = username
                session['student_id'] = user[0]
                print(f"Login route: Setting student_id to {user[0]}")
                print(f"Session contents: {session}")
                return redirect(url_for('Dashboard'))
            
        flash("Invalid credentials. Please try again.", "error")
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_data = {
            'idno': request.form['idno'],
            'lastname': request.form['lastname'],
            'firstname': request.form['firstname'],
            'middlename': request.form.get('middlename', ''),  # Use .get() to avoid KeyError
            'course': request.form['course'],
            'year_level': request.form['level'],  # Check if the name matches the form
            'email': request.form['email'],
            'username': request.form['username'],
            'password': generate_password_hash(request.form['password'])  # Hash password
        }
        
        if add_user(user_data):
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        
        flash("Registration failed - Username/Email already exists.", "error")
    
    return render_template('register.html')

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

