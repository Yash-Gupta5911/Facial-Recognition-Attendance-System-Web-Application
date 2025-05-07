import os
from flask import Flask, render_template, redirect, url_for, request, session
from threading import Thread
from main import check_attendance_all, run_recognition_loop, get_student_attendance_web
from flask import session
import mysql.connector as my
from PIL import Image, ImageDraw, ImageFont
import random
import io
from flask import send_file
import pandas as pd
from flask import send_file
import io

# Database setup
db = mysql.connector.connect(
    host=os.environ.get('DB_HOST'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD'),
    database=os.environ.get('DB_NAME')
)
mysql_cursor = mysql_conn.cursor()


app = Flask(__name__)
app.secret_key = 'e3f4a9cbd8224c90bfb4a7e2a1dfebc8'  # Required for session management

# ---------------------------- Routes ----------------------------

@app.route('/')
def home():
    return "Facial Recognition Attendance System"

@app.route('/captcha')
def captcha():
    captcha_text = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=5))
    session['captcha_text'] = captcha_text

    img = Image.new('RGB', (150, 50), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((10, 10), captcha_text, font=font, fill=(0, 0, 0))

    buffer = io.BytesIO()
    img.save(buffer, 'PNG')
    buffer.seek(0)
    return send_file(buffer, mimetype='image/png')

# ---------------------------- Admin Login ----------------------------



@app.route('/admin', methods=['GET', 'POST'])
def admin_page():
    if request.method == 'POST':
        admin_id = request.form.get("admin_id")
        admin_password = request.form.get("admin_password")
        user_captcha = request.form.get("captcha")

        # Check if CAPTCHA matches
        if user_captcha != session.get('captcha_text'):
            return "Invalid CAPTCHA", 403

        # Check admin credentials
        if admin_id == 'admin123' and admin_password == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return "Invalid Admin Credentials", 401

    return render_template("admin_login.html")



@app.route('/admin/dashboard')
def admin_dashboard():
    session['admin_logged_in'] = True

    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_page'))

    try:
        columns, records = check_attendance_all(return_data=True)
        message = "Attendance Records"

        # Attendance columns start from index 3 (after student_id, name, course)
        date_columns = columns[4:]

        attendance_data = []
        for record in records:
            student_data = {
                'student_id': record[0],
                'name': record[1],
                'course': record[2]
            }

            total_days = len(date_columns)
            present_count = 0

            # Add each date column's attendance and count "Present"
            for idx, date in enumerate(date_columns, start=3):
                status = record[idx]
                student_data[date] = status
                if status and status.strip().lower() == "present":
                    present_count += 1

            # Calculate attendance percentage
            if total_days > 0:
                percent = (present_count / total_days) * 100
                student_data['attendance_percent'] = f"{percent:.2f}%"
            else:
                student_data['attendance_percent'] = "N/A"

            attendance_data.append(student_data)

    except Exception as e:
        attendance_data, date_columns = [], []
        message = f"Error loading records: {e}"

    return render_template("admin_page.html", attendance_data=attendance_data, date_columns=date_columns, message=message)





@app.route('/logout')
def logout():
    if session.get('admin_logged_in'):
        session.clear()
        return redirect(url_for('admin_page'))
    elif session.get('student_logged_in'):
        session.clear()
        return redirect(url_for('student_login'))
    else:
        session.clear()
        return redirect(url_for('home'))






@app.route('/student', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        student_id = request.form.get("student_id")
        student_password = request.form.get("student_password")
        user_captcha = request.form.get("captcha")

        # CAPTCHA check
        if user_captcha != session.get('captcha_text'):
            return "Invalid CAPTCHA", 403

        # Check password from DB
        mysql_cursor.execute("SELECT password FROM attendance WHERE student_id = %s", (student_id,))
        result = mysql_cursor.fetchone()

        if result:
            db_password = result[0]
            if student_password == db_password:
                # Set session and redirect to dashboard
                session['student_logged_in'] = True
                session['student_id'] = student_id
                return redirect(url_for('student_dashboard'))
            else:
                return "Incorrect password", 401
        else:
            return "Student ID not found", 404

    return render_template("student_login.html")


@app.route('/student/dashboard')
def student_dashboard():
    if not session.get('student_logged_in'):
        return redirect(url_for('student_login'))

    student_id = session.get('student_id')
    headers, data = get_student_attendance_web(student_id)

    if data:
        attendance_values = data[4:]  # Skip ID, name, course, password
        total_classes = len(attendance_values)
        present_count = attendance_values.count("Present")
        percentage = round((present_count / total_classes) * 100, 2) if total_classes > 0 else 0

        attendance_data = list(zip(headers[4:], attendance_values))

        return render_template('student_dashboard.html',
                               attendance_data=attendance_data,
                               name=data[1],
                               student_id=data[0],
                               course=data[2],
                               total_classes=total_classes,
                               present_count=present_count,
                               percentage=percentage)
    else:
        return "Attendance data not found.", 404
    


@app.route('/download/attendance')
def download_attendance():
    columns, records = check_attendance_all(return_data=True)
    df = pd.DataFrame(records, columns=columns)

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    return send_file(buffer, download_name="attendance_records.xlsx", as_attachment=True)



@app.route('/debarred/export')
def download_debarred_list():
    threshold = request.args.get('threshold', type=int)
    if threshold is None:
        return "Invalid percentage input", 400

    columns, records = check_attendance_all(return_data=True)
    df = pd.DataFrame(records, columns=columns)

    attendance_columns = columns[3:]
    df["Present"] = df[attendance_columns].apply(lambda row: list(row).count("Present"), axis=1)
    df["Total"] = df[attendance_columns].notna().sum(axis=1)
    df["Percentage"] = (df["Present"] / df["Total"]) * 100
    df["Status"] = df["Percentage"].apply(lambda p: "Debarred" if p < threshold else "Allowed")

    final_df = df[["student_id", "name", "course", "Status"]]

    buffer = io.BytesIO()
    final_df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    return send_file(buffer, download_name=f"debarred_below_{threshold}.xlsx", as_attachment=True)




# ---------------------------- Run Flask + Face Recognition ----------------------------

if __name__ == '__main__':
    Thread(target=run_recognition_loop, daemon=True).start()
    app.run(debug=True)
