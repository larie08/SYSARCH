from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from dbhelper import *
import io
import os
import csv
import pandas as pd
from datetime import datetime
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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
        return redirect(url_for('login'))
    
    total_students, current_sitins, total_sitins = get_dashboard_stats()
    purpose_data = get_purpose_data()
    points_leaderboard = get_points_leaderboard()
    student_leaderboard = get_student_leaderboard()
    
    # Chart data setup
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
                         total_sitins=total_sitins,
                         points_leaderboard=points_leaderboard,
                         student_leaderboard=student_leaderboard)

@app.route('/admin/pending_reservations')
def admin_pending_reservations():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    formatted_reservations = get_pending_reservations()
    return render_template('admin/adminreservation.html', reservations=formatted_reservations)

@app.route('/admin/process_reservation/<int:reservation_id>/<string:action>', methods=['POST'])
def process_reservation(reservation_id, action):
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    success, message = process_reservation_action(reservation_id, action)
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    
    print(f"Error processing reservation: {message}")
    return jsonify({'error': message}), 500

@app.route('/admin/add_point', methods=['POST'])
def add_point():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    student_id = data.get('student_id')
    
    success, message = add_student_point(student_id)
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    
    print(f"Error adding point: {message}")
    return jsonify({'error': message}), 500

@app.route('/admin/sit-in')
def admin_sitin():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    users = get_all_users()
    return render_template('admin/adminsitin.html', users=users)

@app.route('/admin/search_student/<student_id>')
def search_student(student_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        student = search_student_by_id(student_id)
        if student:
            return jsonify(student)
        return jsonify({'error': f'No student found with ID: {student_id}'}), 404
            
    except Exception as e:
        print(f"Error searching student: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/reset_session', methods=['POST'])
def reset_session():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    student_id = data.get('student_id')
    course = data.get('course')
    
    # Set session limit based on course
    session_limit = 30 if course in ['BSIT', 'BSCS'] else 15
    
    success, error = reset_student_sessions(student_id, course, session_limit)
    
    if success:
        return jsonify({'success': True})
    
    error_message = error or 'Student not found'
    print(f"Error resetting session: {error_message}")
    return jsonify({'success': False, 'error': error_message}), 500

@app.route('/admin/reset_all_sessions', methods=['POST'])
def reset_all_sessions():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    success, message = reset_all_student_sessions()
    
    if success:
        return jsonify({'success': True, 'message': message})
    
    print(f"Error resetting all sessions: {message}")
    return jsonify({'success': False, 'error': message}), 500

@app.route('/admin/resources', methods=['GET', 'POST'])
def admin_resources():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        lab_name = request.form.get('lab_name')
        pc_count = request.form.get('pc_count')
        status = request.form.get('status')
        description = request.form.get('description')
        
        if add_lab_resource(lab_name, pc_count, status, description):
            flash('Laboratory resource added successfully', 'success')
        else:
            flash('Failed to add laboratory resource', 'error')
    
    resources = get_lab_resources()
    return render_template('admin/adminlabresources.html', resources=resources)

@app.route('/admin/resources/edit/<int:resource_id>', methods=['GET', 'POST'])
def edit_resource(resource_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        lab_name = request.form.get('lab_name')
        pc_count = request.form.get('pc_count')
        status = request.form.get('status')
        description = request.form.get('description')
        
        if update_lab_resource(resource_id, lab_name, pc_count, status, description):
            flash('Laboratory resource updated successfully', 'success')
        else:
            flash('Failed to update laboratory resource', 'error')
        return redirect(url_for('admin_resources'))
    
    resource = get_resource_by_id(resource_id)
    if resource:
        return render_template('admin/adminresources.html', resource=resource)
    
    flash('Resource not found', 'error')
    return redirect(url_for('admin_resources'))

@app.route('/admin/resources/delete/<int:resource_id>')
def delete_resource(resource_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    if delete_lab_resource(resource_id):
        flash('Laboratory resource deleted successfully', 'success')
    else:
        flash('Failed to delete laboratory resource', 'error')
    
    return redirect(url_for('admin_resources'))

@app.route('/admin/reports')
def admin_reports():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    records = get_completed_reports()
    return render_template('admin/reports.html', records=records)

@app.route('/admin/export_report')
def export_report():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Get filter parameters
        export_format = request.args.get('format', '').lower()
        lab = request.args.get('lab')
        purpose = request.args.get('purpose')
        date = request.args.get('date')
        
        # Get filtered records
        filtered_records = get_filtered_records(lab, purpose, date)
        
        if not filtered_records:
            return jsonify({'error': 'No records found'}), 404
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Generate the report based on format
        if export_format == 'csv':
            output = export_to_csv(filtered_records)
            mimetype = 'text/csv'
            filename = f'sit_in_report_{timestamp}.csv'
        elif export_format == 'excel':
            output = export_to_excel(filtered_records)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f'sit_in_report_{timestamp}.xlsx'
        elif export_format == 'pdf':
            output = export_to_pdf(filtered_records)
            mimetype = 'application/pdf'
            filename = f'sit_in_report_{timestamp}.pdf'
        else:
            return jsonify({'error': 'Invalid export format'}), 400
        
        if output is None:
            return jsonify({'error': 'Failed to generate report'}), 500
            
        # Send the file with proper headers
        response = send_file(
            output,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
        
        # Add headers to prevent caching
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
    
    except Exception as e:
        print(f"Export error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/feedback')
def admin_feedback():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    formatted_feedbacks = get_all_feedbacks()
    return render_template('admin/feedback.html', feedbacks=formatted_feedbacks)

@app.route('/admin/announcement', methods=['GET', 'POST'])
def admin_announcement():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        author = request.form.get('author')
        admin_id = session['admin_id']
        
        if add_announcement(admin_id, title, message, author):
            flash('Announcement added successfully', 'success')
        else:
            flash('Failed to add announcement', 'error')
    
    announcements = get_announcements()
    authors = ['CSS Admin', 'CSS Dean', 'Sit-in Supervisor']
    
    return render_template('admin/adminannouncement.html', 
                         announcements=announcements,
                         authors=authors)

@app.route('/admin/announcement/delete/<int:announcement_id>')
def delete_announcement(announcement_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    if delete_announcement_by_id(announcement_id):
        flash('Announcement deleted successfully', 'success')
    else:
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
        
        if update_announcement(announcement_id, title, message, admin_id):
            flash('Announcement updated successfully', 'success')
        else:
            flash('Failed to update announcement', 'error')
        return redirect(url_for('admin_announcement'))
    
    announcement = get_announcement_by_id(announcement_id)
    if announcement:
        return render_template('admin/adminannouncement.html', announcement=announcement)
    
    flash('Announcement not found', 'error')
    return redirect(url_for('admin_announcement'))

@app.route('/admin/sit_in_student', methods=['POST'])
def sit_in_student():
    data = request.get_json()
    student_id = data.get('student_id')
    purpose = standardize_purpose(data.get('purpose', '').strip())
    laboratory = data.get('laboratory')
    
    if not all([student_id, purpose, laboratory]):
        return jsonify({'error': 'Missing required data'}), 400
    
    success, result = create_sit_in_session(student_id, purpose, laboratory)
    
    if success:
        return jsonify({
            'success': True,
            'remaining_sessions': result,
            'message': f'Sit-in recorded successfully. {result} sessions remaining.'
        })
    
    return jsonify({'error': result}), 500

@app.route('/admin/current-sitin')
def admin_current_sitin():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    update_null_sessions()
    current_sitins = get_current_sitins()
    return render_template('admin/admincurrentsitin.html', sitins=current_sitins)

@app.route('/admin/records')
def admin_records():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    completed_sitins = get_completed_sitins()
    purpose_counts = get_purpose_statistics()
    lab_counts = get_lab_statistics()
    
    return render_template('admin/records.html', 
                         records=completed_sitins,
                         purpose_counts=purpose_counts,
                         lab_counts=lab_counts)

@app.route('/admin/logout_student', methods=['POST'])
def logout_student():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.get_json()
    student_id = data.get('student_id')
    
    success, result = logout_student_session(student_id)
    
    if success:
        return jsonify({
            'success': True,
            'logout_time': result
        })
    return jsonify({'error': result}), 500

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))
#admin route


#STUDENT ROUTES
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    reservations = get_all_reservations()
    return render_template('student/index.html', reservations=reservations)

@app.route('/Dashboard')
def Dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    rejection_message = session.pop('rejection_message', None)
    
    print(f"Debug - User in session: {session['username']}")
    print(f"Debug - Student ID: {session['student_id']}")
    
    reservations = get_user_reservations(session['student_id'])
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
                success, result = save_profile_photo(file, app.config['UPLOAD_FOLDER'])
                if success:
                    data['photo'] = result
                else:
                    flash('Error uploading photo.', 'error')

        if update_user_profile(session['student_id'], data):
            flash('Profile updated successfully!', 'success')
        else:
            flash('Error updating profile.', 'error')
        return redirect(url_for('Profile'))

    user_profile = get_user_profile(session['student_id'])
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
    announcements = get_student_announcements()
    return render_template('student/announcement.html', announcements=announcements)

@app.route('/Resources')
def Resources():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    resources = get_student_resources(session['student_id'])
    return render_template('student/lab.html', resources=resources)

@app.route('/Session')
def Session():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    total_sessions, available_sessions, used_sessions = get_user_session_info(session['student_id'])
    
    return render_template('student/session.html', 
                         total_sessions=total_sessions,
                         available_sessions=available_sessions,
                         used_sessions=used_sessions)

@app.route('/submit_reservation', methods=['POST'])
def submit_reservation():
    if 'username' not in session:
        print("No username in session")
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.get_json()
    student_id = session.get('student_id')
    purpose = data.get('purpose')
    laboratory = data.get('laboratory')
    
    print(f"Received reservation request - Student ID: {student_id}, Purpose: {purpose}, Lab: {laboratory}")
    
    success, new_id, result = create_reservation(student_id, purpose, laboratory)
    
    if success:
        print(f"Created reservation with ID: {new_id}")
        print(f"Newly created reservation: {result}")
        return jsonify({
            'success': True,
            'message': 'Reservation submitted for approval'
        })
    
    print(f"Error submitting reservation: {result}")
    return jsonify({'error': result}), 500

@app.route('/History')
def History():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    history = get_user_history(session['student_id'])
    return render_template('student/history.html', history=history)

@app.route('/delete_record/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    if delete_user_record(record_id, session['student_id']):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Record not found'}), 404

@app.route('/Reservation')
def Reservation():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = get_user_reservation_data(session['student_id'])
    if not user:
        flash('Error loading user data', 'error')
        return redirect(url_for('Dashboard'))
        
    return render_template('student/reservation.html', user=user)

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    data = request.get_json()
    feedback_text = data.get('feedback')
    reservation_id = data.get('reservation_id')

    if not feedback_text:
        return jsonify({'success': False, 'error': 'Feedback text is required'}), 400
    if not reservation_id:
        return jsonify({'success': False, 'error': 'Reservation ID is required'}), 400

    if add_user_feedback(session['student_id'], reservation_id, feedback_text):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to submit feedback'}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            user_data = {
                'idno': request.form['idno'],
                'lastname': request.form['lastname'],
                'firstname': request.form['firstname'],
                'middlename': request.form.get('middlename', ''),
                'course': request.form['course'],
                'year_level': request.form['level'],
                'email': request.form['email'],
                'username': request.form['username'],
                'password': generate_password_hash(request.form['password']),
                'address': request.form.get('address', '')
            }
            
            is_valid, error_msg = validate_registration_data(user_data)
            if not is_valid:
                flash(error_msg, "error")
                return render_template('register.html')
            
            success, session_limit, error = process_registration(user_data, user_data['course'])
            if success:
                flash(f"Registration successful! Your session limit is {session_limit}.", "success")
                return redirect(url_for('login'))
            
            flash(error or "Registration failed. Please try again.", "error")
            
        except Exception as e:
            print(f"Registration error: {e}")
            flash("Registration failed. Please try again.", "error")
            
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
    app.run()

