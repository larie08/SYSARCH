from flask import Flask, render_template, request, redirect, url_for, session, flash
from dbhelper import *
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'tonifowlersupersecretkey'

with app.app_context():
    create_tables()

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('Dashboard'))  # Redirect to dashboard if logged in
    return redirect(url_for('login'))

@app.route('/Dashboard')
def Dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/Profile')
def Profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute("SELECT lastname, firstname, middlename, course, level, email FROM users WHERE idno = ?", (123456,)) #missing sessions and address
    users = cursor.fetchone()

    conn.close()
    return render_template('profile.html', users=users)

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
    return render_template('history.html')

@app.route('/Reservation')
def Reservation():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('reservation.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if check_user(username, password):
            session['username'] = username
            return redirect(url_for('Dashboard'))
        
        flash("Invalid credentials. Please try again.", "error")
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_data = (
            request.form['idno'],
            request.form['lastname'],
            request.form['firstname'],
            request.form['middlename'],
            request.form['course'],
            request.form['level'],
            request.form['email'],
            request.form['username'],
            request.form['password']
        )
        
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
