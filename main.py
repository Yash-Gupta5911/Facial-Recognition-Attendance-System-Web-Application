import pickle
import numpy as np
import cv2
import os
import cvzone
import mysql.connector as my
import datetime
import face_recognition
from tabulate import tabulate

# Database setup
mysql_conn = my.connect(
    host='localhost',
    user='root',
    password='2004',
    database='bcaibm_attendance'
)
mysql_cursor = mysql_conn.cursor()

# Get today's date string
current_date_str = datetime.date.today().strftime("%d/%m/%Y")

# Ensure today's column exists
try:
    mysql_cursor.execute(
        f"ALTER TABLE attendance ADD COLUMN `{current_date_str}` ENUM('Present', 'Absent') DEFAULT 'Absent'"
    )
    print(f"Column '{current_date_str}' added successfully.")
except my.Error as e:
    print("MySQL Error:", e.msg)

# -----------------------------------------
# 1. Face Recognition Loop (Real-Time)
# -----------------------------------------
def run_recognition_loop():
    cap = cv2.VideoCapture(0)
    cap.set(3, 640)
    cap.set(4, 480)

    imgBackground = cv2.imread('D:\\FacialRecognition_Attendance-main\\Face_Recognition\\Resources\\ATTENDANCE SYSTEM.png')

    print("Loading Encode File....")
    with open('EncodeFile.p', 'rb') as file:
        encodeListKnownWithIds = pickle.load(file)
    encodeListKnown, studentIds = encodeListKnownWithIds
    print("Encode File Loaded")

    while True:
        success, img = cap.read()
        if not success:
            print("Failed to read from camera.")
            break

        imgS = cv2.resize(img, (0, 0), None, 0.25, 0.25)
        imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

        faceCurFrame = face_recognition.face_locations(imgS)
        encodeCurFrame = face_recognition.face_encodings(imgS, faceCurFrame)

        imgBackground[162:162 + 480, 55:55 + 640] = img

        for encodeFace, faceLoc in zip(encodeCurFrame, faceCurFrame):
            matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
            faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)

            best_match_index = np.argmin(faceDis)
            best_match_distance = faceDis[best_match_index]

            if matches[best_match_index] and best_match_distance > 0.2:
                student_id = studentIds[best_match_index]
                print("Known Face Detected - Accuracy:", 1 - best_match_distance)

                update_query = f"UPDATE attendance SET `{current_date_str}` = 'Present' WHERE student_id = %s"
                mysql_cursor.execute(update_query, (student_id,))
                mysql_conn.commit()

                try:
                    select_query = "SELECT * FROM attendance WHERE student_id = %s"
                    mysql_cursor.execute(select_query, (student_id,))
                    student_details = mysql_cursor.fetchone()
                    if student_details:
                        print("Student Details:", student_details)
                except Exception as e:
                    print("Error fetching student details:", e)

                y1, x2, y2, x1 = [coord * 4 for coord in faceLoc]
                bbox = 55 + x1, 162 + y1, x2 - x1, y2 - y1
                imgBackground = cvzone.cornerRect(imgBackground, bbox, rt=0)
            else:
                print("Unknown Face Detected")

        cv2.imshow("Face Attendance", imgBackground)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

# -----------------------------------------
# 2. Mark Student Present
# -----------------------------------------
def mark_present():
    student_idP = int(input("Enter the student id : "))
    select_query = "SELECT name FROM attendance WHERE student_id = %s"
    mysql_cursor.execute(select_query, (student_idP,))
    student_info = mysql_cursor.fetchone()

    if student_info:
        student_name = student_info[0]
        update_query = f"UPDATE attendance SET `{current_date_str}` = 'Present' WHERE student_id = %s AND `{current_date_str}` = 'Absent'"
        try:
            mysql_cursor.execute(update_query, (student_idP,))
            mysql_conn.commit()
            print("Attendance marked as present for student ID:", student_idP, "Name:", student_name)
        except my.Error as e:
            print("MySQL Error:", e.msg)
    else:
        print("Provided student ID does not match any student ID in the database.")

# -----------------------------------------
# 3. Mark Student Absent
# -----------------------------------------
def mark_absent():
    student_idA = int(input("Enter the student id : "))
    select_query = "SELECT name FROM attendance WHERE student_id = %s"
    mysql_cursor.execute(select_query, (student_idA,))
    student_info = mysql_cursor.fetchone()

    if student_info:
        student_name = student_info[0]
        update_query = f"UPDATE attendance SET `{current_date_str}` = 'Absent' WHERE student_id = %s AND `{current_date_str}` = 'Present'"
        try:
            mysql_cursor.execute(update_query, (student_idA,))
            mysql_conn.commit()
            print("Attendance marked absent for student ID:", student_idA, "Name:", student_name)
        except my.Error as e:
            print("MySQL Error:", e.msg)
    else:
        print("Provided student ID does not match any student ID in the database.")

# -----------------------------------------
# 4. Check Today's Attendance
# -----------------------------------------
def check_attendance():
    try:
        select_query = f"SELECT student_id, name, `{current_date_str}` FROM attendance"
        mysql_cursor.execute(select_query)
        results = mysql_cursor.fetchall()

        headers = ["Student ID", "Name", current_date_str]
        data = [[row[0], row[1], row[2]] for row in results]
        print(tabulate(data, headers=headers, tablefmt="grid"))

    except my.Error as e:
        print("MySQL Error:", e.msg)

# -----------------------------------------
# 5. Check Attendance for a Specific Date
# -----------------------------------------
def check_attendanceForSpecificDate():
    try:
        specific_date = input("Enter the date (DD/MM/YYYY) to check attendance: ")
        select_query = f"SELECT student_id, name, `{specific_date}` FROM attendance"
        mysql_cursor.execute(select_query)
        results = mysql_cursor.fetchall()

        headers = ["Student ID", "Name", specific_date]
        data = [[row[0], row[1], row[2]] for row in results]
        print(tabulate(data, headers=headers, tablefmt="grid"))

    except my.Error as e:
        print("MySQL Error:", e.msg)

# -----------------------------------------
# 6. Get a Specific Student's Full Attendance
# -----------------------------------------
def get_student_attendance():
    student_id = input("Enter the student ID: ")

    try:
        mysql_cursor.execute("SHOW COLUMNS FROM attendance")
        columns = mysql_cursor.fetchall()
        date_columns = [col[0] for col in columns if col[0] not in ['student_id', 'name', 'course']]

        select_query = f"SELECT student_id, name, {', '.join(['`'+col+'`' for col in date_columns])} FROM attendance WHERE student_id = %s"
        mysql_cursor.execute(select_query, (student_id,))
        result = mysql_cursor.fetchone()

        if result:
            student_id, student_name, *attendance_values = result
            headers = ["Student ID", "Name"] + date_columns
            values = [str(student_id), student_name] + [str(val) for val in attendance_values]

            print("\nAttendance Record:")
            for header, value in zip(headers, values):
                print(f"{header}: {value}")
        else:
            print("No attendance records found for the given student ID.")

    except my.Error as e:
        print("MySQL Error:", e.msg)

# -----------------------------------------
# 7. Get All Attendance Records (also used in app.py)
# -----------------------------------------
def check_attendance_all(return_data=False):
    try:
        select_query = "SELECT * FROM attendance"
        mysql_cursor.execute(select_query)
        results = mysql_cursor.fetchall()
        column_names = [desc[0] for desc in mysql_cursor.description]

        if return_data:
            return column_names, results
        else:
            print("\t".join(column_names))
            for row in results:
                print("\t".join(str(item) for item in row))

    except my.Error as e:
        print("MySQL Error:", e.msg)
        if return_data:
            return [], []
        
def get_student_attendance_web(student_id):
    try:
        mysql_cursor.execute("SHOW COLUMNS FROM attendance")
        columns = mysql_cursor.fetchall()
        date_columns = [col[0] for col in columns if col[0] not in ['student_id', 'name', 'course']]

        query = f"SELECT student_id, name, course, {', '.join(['`'+col+'`' for col in date_columns])} FROM attendance WHERE student_id = %s"
        mysql_cursor.execute(query, (student_id,))
        result = mysql_cursor.fetchone()

        if result:
            student_id, name, course, *attendance = result
            headers = ["Student ID", "Name", "Course"] + date_columns
            values = [student_id, name, course] + attendance
            return headers, values
        else:
            return [], []
    except my.Error as e:
        print("MySQL Error:", e.msg)
        return [], []


# -----------------------------------------
# Optional CLI interface (for testing manually)
# -----------------------------------------
if __name__ == "__main__":
    run_recognition_loop()

    while True:
        print("\nChoose an option:")
        print("1. Mark someone present")
        print("2. Mark someone absent")
        print("3. Check attendance")
        print("4. Check attendance for Specific Date")
        print("5. Get Attendance for a Specific Student")
        print("6. Get All Attendance Records")
        print("7. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            mark_present()
        elif choice == '2':
            mark_absent()
        elif choice == '3':
            check_attendance()
        elif choice == '4':
            check_attendanceForSpecificDate()
        elif choice == '5':
            get_student_attendance()
        elif choice == '6':
            check_attendance_all()
            print("Attendance records fetched successfully.")
        elif choice == '7':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")
