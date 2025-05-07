from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, make_response
from dbhelper import *
import io
import os
import csv
import pandas as pd
import xlsxwriter
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static')
app.secret_key = 'tonifowlersupersecretkey'

DATABASE_URL = os.environ.get('POSTGRES_URL', 'postgresql://user:password@localhost:5432/rubi_sysarch')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
RESOURCE_FOLDER = os.path.join(app.static_folder, 'resources')
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'resources')


app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  

app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'resources')

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
    purposes = ['C#', 'C', 'ASP.NET', 'Java', 'Php','Database', 'Digital Logic & Design', 'Embedded Designs & IOT', 'System Integration & Architecture', 'Computer Application', 'Project Management', 'IT Trends', 'Technopreneurship', 'Capstone']
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
        return redirect(url_for('admin_login'))
    
    reservations = get_pending_reservations()  # Ensure this function includes all necessary fields
    return render_template('admin/adminreservation.html', reservations=reservations)

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

@app.route('/admin/reservation_logs')
def reservation_logs():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    reservation_logs = get_reservation_logs()  # Fetch accepted and rejected reservations
    return render_template('admin/adminlogs.html', reservations=reservation_logs)

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

@app.route('/admin/computer_control', methods=['GET', 'POST'])
def admin_computer_control():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    lab = request.args.get('lab', 'default_lab') 
    
    if request.method == 'POST':
        # Update computer status
        computer_id = request.form.get('computer_id')
        new_status = request.form.get('status')
        
        try:
            if update_computer_status(lab, computer_id, new_status):
                flash(f'Computer {computer_id} status updated to {new_status}', 'success')
            else:
                flash(f'Failed to update status for computer {computer_id}', 'error')
        except Exception as e:
            flash(f'Error updating computer status: {str(e)}', 'error')
    
    try:
        computers = get_lab_computers(lab)  # Fetch all computers for the lab
        # Ensure all 50 computers are listed
        all_computers = [{'id': i, 'status': 'available'} for i in range(1, 51)]
        for computer in computers:
            all_computers[computer['id'] - 1]['status'] = computer['status']
    except Exception as e:
        flash(f'Error fetching computers for lab {lab}: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/admincomputer.html', computers=all_computers)

@app.route('/admin/update_computer_status', methods=['POST'])
def update_computer_status_route():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    lab = data.get('lab')
    computers = data.get('computers')
    status = data.get('status')
    
    if not all([lab, computers, status]):
        return jsonify({'success': False, 'message': 'Missing required data'}), 400
    
    success = update_multiple_computer_status(lab, computers, status)
    
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Failed to update status'})

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

@app.route('/admin/lab_schedules', methods=['GET', 'POST'])
def admin_lab_schedules():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        lab_number = request.form.get('lab_number')
        schedule_date = request.form.get('schedule_date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        description = request.form.get('description')
        
        # Validate and parse the schedule_date
        try:
            schedule_date = datetime.strptime(schedule_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
            return redirect(url_for('admin_lab_schedules'))
        
        if add_lab_schedule(lab_number, schedule_date, start_time, end_time, description):
            flash('Lab schedule added successfully', 'success')
        else:
            flash('Failed to add lab schedule', 'error')
    
    schedules = get_lab_schedules()
    return render_template('admin/adminlabschedule.html', schedules=schedules)

@app.route('/admin/lab_schedules/delete/<int:schedule_id>')
def delete_lab_schedule_route(schedule_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    if delete_lab_schedule(schedule_id):
        flash('Lab schedule deleted successfully', 'success')
    else:
        flash('Failed to delete lab schedule', 'error')
    
    return redirect(url_for('admin_lab_schedules'))

@app.route('/download_lab_schedule_pdf')
def download_lab_schedule_pdf():
    if 'admin_id' not in session and 'username' not in session:
        return redirect(url_for('login'))
    
    # Get all lab schedules
    schedules = get_lab_schedules()
    
    # Generate PDF
    pdf_buffer = generate_lab_schedule_pdf(schedules)
    
    # Create response
    response = make_response(pdf_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=lab_schedules.pdf'
    
    return response

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
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
    data = request.get_json()
    student_id = data.get('student_id')
    purpose = data.get('purpose')
    lab = data.get('lab')  # Changed from 'laboratory' to match frontend
    computer_number = data.get('computer_number')
    
    # Validate required fields
    if not all([student_id, purpose, lab, computer_number]):
        return jsonify({
            'success': False, 
            'error': 'Missing required fields (student_id, purpose, lab, computer_number)'
        }), 400

    try:
        # First check remaining sessions
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sessions FROM users WHERE idno = ?", (student_id,))
            result = cursor.fetchone()
            
            if not result:
                return jsonify({'success': False, 'error': 'Student not found'})
                
            remaining_sessions = int(result[0]) if result[0] is not None else 0
            
            if remaining_sessions <= 0:
                return jsonify({
                    'success': False, 
                    'error': 'No remaining sessions available'
                })
                
            # Proceed with sit-in if sessions available
            cursor.execute("""
                INSERT INTO reservations (idno, purpose, lab, computer_number, status, time_in)
                VALUES (?, ?, ?, ?, 'Active', datetime('now', 'localtime'))
            """, (student_id, purpose, lab, computer_number))
            
            # Deduct one session
            cursor.execute("""
                UPDATE users 
                SET sessions = sessions - 1 
                WHERE idno = ?
            """, (student_id,))
            
            conn.commit()
            
        return jsonify({
            'success': True,
            'message': 'Sit-in recorded successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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

@app.route('/admin/get-resources/<folder>')
def get_resources(folder):
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    folder_path = os.path.join(RESOURCE_FOLDER, folder)
    if not os.path.exists(folder_path):
        return jsonify([])
    
    try:
        files = []
        for f in os.listdir(folder_path):
            file_path = os.path.join(folder_path, f)
            if os.path.isfile(file_path):
                files.append({
                    'name': f,
                    'size': os.path.getsize(file_path),
                    'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                })
        return jsonify(files)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/upload-resource', methods=['POST'])
def upload_resource():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    if 'files[]' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    folder = request.form.get('folder')
    if not folder:
        return jsonify({'error': 'No folder specified'}), 400
    
    folder_path = os.path.join(RESOURCE_FOLDER, folder)
    os.makedirs(folder_path, exist_ok=True)
    
    files = request.files.getlist('files[]')
    uploaded_files = []
    
    try:
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(folder_path, filename)
                file.save(file_path)
                uploaded_files.append(filename)
        
        return jsonify({
            'success': True,
            'files': uploaded_files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/delete-resource', methods=['POST'])
def delete_resource_file():  # <-- Renamed to avoid conflict
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    folder = data.get('folder')
    filename = data.get('filename')
    
    if not folder or not filename:
        return jsonify({'error': 'Folder and filename are required'}), 400
    
    # Handle spaces and special characters in folder names
    folder = folder.replace(' ', '_')
    safe_filename = secure_filename(filename)
    file_path = os.path.join(RESOURCE_FOLDER, folder, safe_filename)
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({
                'success': True,
                'message': f'File {filename} deleted successfully'
            })
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        print(f"Error deleting file: {str(e)}")  # For debugging
        return jsonify({'error': str(e)}), 500

@app.route('/preview-resource/<folder>/<filename>')
def preview_resource(folder, filename):
    if 'username' not in session and 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Sanitize the filename and create the full path
    safe_filename = secure_filename(filename)
    file_path = os.path.join(RESOURCE_FOLDER, folder, safe_filename)
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Get the file's mime type
        mime_type = None
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
            mime_type = f'image/{file_ext[1:]}'
        elif file_ext == '.pdf':
            mime_type = 'application/pdf'
        elif file_ext in ['.txt', '.csv']:
            mime_type = 'text/plain'
        else:
            mime_type = 'application/octet-stream'
        
        return send_file(
            file_path,
            mimetype=mime_type,
            as_attachment=False,
            download_name=safe_filename
        )
    except Exception as e:
        print(f"Preview error: {str(e)}")  # For debugging
        return jsonify({'error': str(e)}), 500

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
    points_data = get_user_points_and_sessions(session['student_id'])
    points = points_data['points']
    
    lab_schedules = get_lab_schedules()
    reservations = get_user_reservations(session['student_id'])
        
    return render_template('student/index.html', 
                         username=session['username'],
                         reservations=reservations,
                         rejection_message=rejection_message,
                         points=points,
                         lab_schedules=lab_schedules)  

@app.route('/quick_reserve', methods=['POST'])
def handle_quick_reserve():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    student_id = session['student_id']
    lab = data.get('lab')
    computer = data.get('computer')
    schedule_date = data.get('date')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    purpose = data.get('purpose')
    
    if not all([lab, computer, schedule_date, start_time, end_time, purpose]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    success, message = quick_reserve(
        student_id, lab, computer, schedule_date,
        start_time, end_time, purpose
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Reservation submitted successfully! Waiting for admin approval.'
        })
    
    return jsonify({
        'success': False,
        'error': message
    }), 400

@app.route('/get-points')
def get_points():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    points_data = get_user_points_and_sessions(session['student_id'])
    return jsonify({
        'success': True,
        'points': points_data['points']
    })

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
    
    student_id = session.get('student_id')
    completed_purposes = get_student_completed_purposes(student_id)
    
    # Create resources array with all completed purposes
    resources = []
    for purpose in completed_purposes:
        resource = {
            'name': purpose,
            'folder': purpose.replace(' ', '_'),
            'files': []
        }
        
        # Check for files in the resource folder
        folder_path = os.path.join(app.root_path, 'static', 'resources', purpose.replace(' ', '_'))
        if os.path.exists(folder_path):
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path):
                    resource['files'].append({
                        'name': file,
                        'type': os.path.splitext(file)[1][1:] if '.' in file else '',
                        'size': os.path.getsize(file_path)
                    })
        
        # Add the resource even if it has no files
        resources.append(resource)
    
    print("Resources:", resources)  # Debug print
    return render_template('student/lab.html', resources=resources)

@app.route('/student/download-resource/<folder>/<filename>')
def download_student_resource(folder, filename):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    student_id = session.get('student_id')
    # Verify student has completed the sit-in for this resource
    completed_purposes = get_student_completed_purposes(student_id)
    if folder.replace('_', ' ') not in completed_purposes:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        file_path = os.path.join(RESOURCE_FOLDER, folder, secure_filename(filename))
        if os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=filename
            )
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/Session')
def Session():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    total_sessions, available_sessions, used_sessions = get_user_session_info(session['student_id'])
    
    return render_template('student/session.html', 
                         total_sessions=total_sessions,
                         available_sessions=available_sessions,
                         used_sessions=used_sessions)

@app.route('/get-computers/<lab>')
def get_lab_computers_status(lab):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    computers = get_lab_computers(lab)
    return jsonify(computers)

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

@app.route('/Reservation', methods=['GET', 'POST'])
def Reservation():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            data = request.get_json() if request.is_json else request.form
            student_id = data.get('student_id')
            lab = data.get('lab')
            computer = data.get('computer')
            time_in = data.get('time_in')
            purpose = data.get('purpose')
            
            # Create reservation in database
            success, new_id, result = create_reservation(student_id, lab, computer, time_in, purpose)
            
            if success:
                if request.is_json:
                    return jsonify({
                        'success': True,
                        'message': 'Reservation submitted successfully! Waiting for admin approval.'
                    })
                flash('Reservation submitted successfully! Waiting for admin approval.', 'success')
                return redirect(url_for('Dashboard'))
            else:
                if request.is_json:
                    return jsonify({'success': False, 'error': 'Failed to submit reservation'})
                flash('Failed to submit reservation. Please try again.', 'error')
                return redirect(url_for('Reservation'))
            
        except Exception as e:
            print(f"Reservation error: {e}")
            if request.is_json:
                return jsonify({'success': False, 'error': str(e)})
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('Reservation'))
    
    # GET request - show form
    user = get_user_reservation_data(session['student_id'])
    if not user:
        flash('Error loading user data', 'error')
        return redirect(url_for('Dashboard'))
        
    return render_template('student/reservation.html', user=user)

@app.route('/submit_reservation', methods=['POST'])
def submit_reservation():
    if 'username' not in session:
        print("No username in session")
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.get_json()
    student_id = session.get('student_id')
    lab = data.get('lab')  # Changed from 'laboratory' to 'lab'
    computer = data.get('computer')  # Changed from 'computer_number' to 'computer'
    time_in = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    purpose = data.get('purpose')
    
    print(f"Received reservation request - Student ID: {student_id}, Purpose: {purpose}, Lab: {lab}")
    
    if not all([student_id, lab, computer, purpose]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    success, new_id, result = create_reservation(
        student_id=student_id,
        lab=lab,
        computer=computer,
        time_in=time_in,
        purpose=purpose
    )
    
    if success:
        print(f"Created reservation with ID: {new_id}")
        print(f"Newly created reservation: {result}")
        return jsonify({
            'success': True,
            'message': 'Reservation submitted for approval'
        })
    
    print(f"Error submitting reservation: {result}")
    return jsonify({'error': result}), 500

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
        idno = request.form.get('idno')
        lastname = request.form.get('lastname')
        firstname = request.form.get('firstname')
        middlename = request.form.get('middlename', '')  # Optional field
        level = request.form.get('level')
        course = request.form.get('course')
        address = request.form.get('address')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user already exists
        if user_exists(idno, username, email):
            flash('User with this ID, username, or email already exists', 'error')
            return render_template('student/register.html', error='Registration failed')
        
        # Set session limit based on course
        session_limit = 30 if course in ['BSIT', 'BSCS'] else 15
        
        # Register the user
        if register_user(idno, lastname, firstname, middlename, level, course, address, username, email, password, session_limit):
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Registration failed', 'error')
            return render_template('student/register.html', error='Registration failed')
    
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

