from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import pyodbc
import os
from flask_mail import Mail,Message
from flask import Flask, request, jsonify
import random
import time
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'adesh.saminathan998@ptuniv.edu.in'  # Replace with your Gmail email
app.config['MAIL_PASSWORD'] = 'qvjkmmdpieabzytv'  # Replace with your Gmail password (or app-specific password)
app.config['MAIL_DEFAULT_SENDER'] = 'adesh.saminathan998@ptuniv.edu.in'  # Optional, set to your Gmail

# Initialize Flask-Mail
mail = Mail(app)

# Temporary storage for OTPs
otp_storage = {}

# Secret key for sessions
app.secret_key = 'your_secret_key'

# Oracle Database configuration with DSN (example, adjust according to your configuration)
connection_string = (
    "DSN=my_oracle_dsn;"  # Replace with your DSN name
    "UID=rogadesh;"  # Replace with Oracle username
    "PWD=rogadesh;"  # Replace with Oracle password
)

# Establish a connection to Oracle DB
def get_db_connection():
    return pyodbc.connect(connection_string)

@app.route('/')
def index():
    return redirect(url_for('login'))  # Redirects to the signup page on startup

@app.route('/welcome')
def welcome():
    return render_template('student.html')

# Signup route to register a new user
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        if not name or not email or not username or not password:
            return render_template('signup.html', error="All fields are mandatory.")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if the username already exists
            cursor.execute("SELECT username FROM user_credentials WHERE username = ?", (username,))
            if cursor.fetchone():
                return render_template('signup.html', error="Username already exists. Please choose another.")

            # Insert user data into the table
            cursor.execute(
                """
                INSERT INTO user_credentials (created_at, name, email, username, password)
                VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?)
                """,
                (name, email, username, password)
            )
            conn.commit()

            return redirect(url_for('login'))

        except pyodbc.Error as e:
            return render_template('signup.html', error=f"Database error: {str(e)}")

        finally:
            cursor.close()
            conn.close()

    return render_template('signup.html')

# Route to check if email already exists
@app.route('/check-email', methods=['POST'])
def check_email():
    data = request.get_json()
    email = data.get('email')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the email exists in the database
        cursor.execute("SELECT COUNT(*) FROM user_credentials WHERE email = ?", (email,))
        exists = cursor.fetchone()[0] > 0

        return jsonify({'exists': exists})

    except pyodbc.Error as e:
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()
        conn.close()

# Route to check if username already exists
@app.route('/check-username', methods=['POST'])
def check_username():
    data = request.get_json()
    username = data.get('username')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the username exists in the database
        cursor.execute("SELECT COUNT(*) FROM user_credentials WHERE username = ?", (username,))
        exists = cursor.fetchone()[0] > 0

        return jsonify({'exists': exists})

    except pyodbc.Error as e:
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()
        conn.close()

# Login route to authenticate the user
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Fetch user data
            cursor.execute("SELECT password FROM user_credentials WHERE username = ?", (username,))
            result = cursor.fetchone()

            if result and result[0] == password:  # Compare plaintext passwords
                return redirect(url_for('welcome'))

            error = "Invalid username or password."
            return render_template('login.html', error=error)

        except pyodbc.Error as e:
            return render_template('login.html', error=f"Database error: {str(e)}")

        finally:
            cursor.close()
            conn.close()

    return render_template('login.html')

# Insert student
@app.route("/insert_student", methods=["POST"])
def insert_student():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO buffer (register_number, name, department, cgpa, attendance)
            VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(query, (
            data["register_number"], data["name"], data["department"],
            data["cgpa"], data["attendance"]
        ))

        conn.commit()
        return jsonify({"message": "Student Record inserted successfully into the Buffer!"}), 201

    except pyodbc.IntegrityError:  # Handle duplicate primary key error
        return jsonify({"error": "Register Number already exists!"}), 400

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/check_record_exists", methods=["POST"])
def check_record_exists():
    data = request.json
    register_number = data.get("register_number")

    if not register_number:
        return jsonify({"exists": False, "error": "Register number is required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM buffer WHERE register_number = ?", (register_number,))
        record_count = cursor.fetchone()[0]
        return jsonify({"exists": record_count > 0}), 200
    except pyodbc.Error as e:
        return jsonify({"exists": False, "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/update_student", methods=["PUT"])
def update_student():
    data = request.json
    try:
        # Ensure the required data is present in the request
        if not all(key in data for key in ["register_number", "field", "new_value"]):
            return jsonify({"error": "Missing data for one or more fields."}), 400

        # Extract the data fields
        register_number = data["register_number"]
        field = data["field"]
        new_value = data["new_value"]

        # Check if the field is valid
        valid_fields = ["name", "department", "cgpa", "attendance"]
        if field not in valid_fields:
            return jsonify({"error": f"Invalid field: {field}"}), 400

        # Validate the field data
        error_message = None
        if field == "name" and not new_value.strip():
            error_message = "Name cannot be empty."
        elif field == "cgpa":
            try:
                cgpa_value = float(new_value)
                if cgpa_value < 0 or cgpa_value > 10:
                    error_message = "CGPA must be between 0 and 10."
            except ValueError:
                error_message = "CGPA must be a valid number."
        elif field == "attendance":
            try:
                attendance_value = int(new_value)
                if attendance_value < 0 or attendance_value >= 100:
                    error_message = "Attendance must be an integer less than 100."
            except ValueError:
                error_message = "Attendance must be a valid number."
        elif field == "department" and new_value not in ["IT", "CSE", "ECE", "EEE", "EIE", "CIVIL", "MECH", "MT"]:
            error_message = "Invalid department."

        if error_message:
            return jsonify({"error": error_message}), 400

        # Connect to the database and update the student record
        conn = get_db_connection()
        cursor = conn.cursor()

        # Dynamically generate SQL query with parameterized values
        query = f"UPDATE buffer SET {field} = ? WHERE register_number = ?"
        cursor.execute(query, (new_value, register_number))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "No student found with the given register number."}), 404

        return jsonify({"message": "Student Record updated successfully in Buffer!"}), 200

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()




@app.route("/delete_student/<register_number>", methods=["DELETE"])
def delete_student(register_number):
    try:
        print(f"Attempting to delete student with register number: {register_number}")
        
        # Establish database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # SQL query to delete a student from the buffer table
        query = "DELETE FROM buffer WHERE register_number = ?"
        cursor.execute(query, (register_number,))

        conn.commit()

        # Check if any row was deleted
        if cursor.rowcount == 0:
            print("No student found with the given register number.")
            return jsonify({"message": "No student found with the given register number."}), 404

        print("Student deleted successfully.")
        return jsonify({"message": "Student Record deleted successfully from Buffer!"}), 200

    except pyodbc.Error as e:
        print(f"Database error: {str(e)}")
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/commit_student", methods=["POST"])
def commit_student():
    data = request.json
    try:
        # Check if all fields are present in the request
        required_fields = ["register_number", "name", "department", "cgpa", "attendance"]
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            return jsonify({"error": f"All fields are mandatory. Missing: {', '.join(missing_fields)}"}), 400

        # Establishing a database connection
        conn = get_db_connection()  # Adjust this to your connection logic
        cursor = conn.cursor()

        # Check if the register number already exists
        check_query = "SELECT COUNT(*) FROM students WHERE register_number = ?"
        cursor.execute(check_query, data["register_number"])
        if cursor.fetchone()[0] > 0:
            return jsonify({"error": "Register number already exists in the Database!"}), 400

        # SQL query to insert data into the 'students' table
        insert_query = """
            INSERT INTO students (register_number, name, department, cgpa, attendance)
            VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(insert_query, (
            data["register_number"], data["name"], data["department"],
            data["cgpa"], data["attendance"]
        ))

        # Commit the transaction to the database
        conn.commit()
        return jsonify({"message": "Student Record inserted successfully into the Database!"}), 201

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get_students", methods=["GET"])
def get_students():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = "SELECT register_number, name, department, cgpa, attendance FROM buffer"
        cursor.execute(query)
        rows = cursor.fetchall()

        # Convert rows into a list of dictionaries
        buffer = [
            {
                "register_number": row[0],
                "name": row[1],
                "department": row[2],
                "cgpa": row[3],
                "attendance": row[4]
            }
            for row in rows
        ]

        return jsonify(buffer), 200

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/buffer_records")
def buffer_records():
    return render_template('buffer_records.html')

@app.route("/database_records")
def database_records():
    return render_template('database_records.html')

@app.route("/student_page")
def student_page():
    return render_template('student.html')

@app.route("/search_student")
def search_student():
    return render_template('search_student.html')

@app.route("/add_marks")
def add_marks():
    return render_template('add_marks.html')

@app.route("/view_marks")
def view_marks():
    return render_template('view_marks.html')

@app.route("/get_students_records", methods=["GET"])
def get_students_records():
    try:
        # Establishing a database connection
        conn = get_db_connection()  # Replace with your DB connection logic
        cursor = conn.cursor()

        # SQL query to fetch all records from the students table
        query = "SELECT register_number, name, department, cgpa, attendance FROM students"
        cursor.execute(query)
        
        # Fetch all rows
        records = cursor.fetchall()

        # Prepare data to return
        students_data = []
        for record in records:
            students_data.append({
                "register_number": record[0],
                "name": record[1],
                "department": record[2],
                "cgpa": record[3],
                "attendance": record[4]
            })

        # Return the records as JSON
        return jsonify(students_data), 200

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/get_buffer_records", methods=["GET"])
def get_buffer_records():
    try:
        # Establishing a database connection
        conn = get_db_connection()  # Adjust this as per your database connection setup
        cursor = conn.cursor()

        # SQL query to fetch all records from the buffer table
        query = "SELECT register_number, name, department, cgpa, attendance FROM buffer"
        cursor.execute(query)
        
        # Fetch all rows
        records = cursor.fetchall()

        # Prepare data to return
        buffer_data = []
        for record in records:
            buffer_data.append({
                "register_number": record[0],
                "name": record[1],
                "department": record[2],
                "cgpa": record[3],
                "attendance": record[4]
            })

        # Return the records as JSON
        return jsonify(buffer_data), 200

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/get_register_numbers", methods=["GET"])
def get_register_numbers():
    try:
        # Establish a connection to the database
        conn = get_db_connection()  # Replace with your database connection logic
        cursor = conn.cursor()

        # Query to fetch all register numbers from the students table
        query = "SELECT register_number FROM students"
        cursor.execute(query)

        # Fetch all register numbers
        records = cursor.fetchall()

        # Extract the register numbers into a list
        register_numbers = [record[0] for record in records]

        # Return the list of register numbers as JSON
        return jsonify(register_numbers)

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@app.route('/fetch_student_details_by_register_number/<register_number>')
def fetch_student_details_by_register_number(register_number):
    try:
        conn = get_db_connection()  # Ensure this is correctly defined
        cursor = conn.cursor()
        
        # Log the register number being fetched
        print(f"Fetching details for register number: {register_number}")
        
        cursor.execute("SELECT * FROM students WHERE register_number = ?", (register_number,))
        student = cursor.fetchone()

        if student:
            # Log the retrieved student data
            print(f"Found student: {student}")
            conn.close()

            # Return student details as JSON
            return jsonify({
                "register_number": student[0],
                "name": student[1],
                "department": student[2],
                "cgpa": student[3],
                "attendance": student[4]
            })
        else:
            conn.close()
            return jsonify({"error": "Student not found"}), 404

    except Exception as e:
        print(f"Error fetching student details: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/getStudentDetailsFromBuffer/<register_number>', methods=['GET'])
def get_student_details_from_buffer(register_number):
    try:
        # Establish a connection to the database
        conn = get_db_connection()  # Replace with your database connection logic
        cursor = conn.cursor()

        # Query to fetch student details for a given register number
        query = """
        SELECT register_number, name, department, cgpa, attendance 
        FROM buffer 
        WHERE register_number = ?
        """
        cursor.execute(query, (register_number,))

        # Fetch the student record
        record = cursor.fetchone()

        if record:
            # Prepare the student details as a dictionary
            student_data = {
                "register_number": record[0],
                "name": record[1],
                "department": record[2],
                "cgpa": record[3],
                "attendance": record[4]
            }
            # Return the student details as JSON
            return jsonify(student_data)
        else:
            # Return error if no student found
            return jsonify({"error": "Student not found"}), 404

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


@app.route('/search_students', methods=['GET'])
def search_students():
    register_prefix = request.args.get('register_number', '').strip()

    if not register_prefix:
        return jsonify({'error': 'Register number prefix is required'}), 400

    # Optional: Validate the prefix length (e.g., at least 3 characters)
    if len(register_prefix) < 3:
        return jsonify({'error': 'Register number prefix must be at least 3 characters long'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query to fetch matching student records
        query = """
            SELECT register_number, name, department, cgpa, attendance
            FROM students
            WHERE register_number LIKE ?
        """
        cursor.execute(query, (register_prefix + '%',))
        results = cursor.fetchall()

        if not results:
            return jsonify({"error": "No students found with the given register number prefix."}), 404

        # Format the results as a list of dictionaries
        students = [
            {
                'register_number': row[0],
                'name': row[1],
                'department': row[2],
                'cgpa': row[3],
                'attendance': row[4],
            }
            for row in results
        ]
        return jsonify(students), 200

    except Exception as e:
        print("Error searching students:", e)
        return jsonify({'error': 'An unexpected error occurred while searching for students.'}), 500

    finally:
        # Ensure the cursor and connection are closed
        cursor.close()
        conn.close()

@app.route('/send_email')
def send_email():
    try:
        msg = Message('Test Email from Flask', recipients=['your_email@gmail.com'])  # Replace with your email
        msg.body = 'This is a test email.'
        mail.send(msg)
        return "Test email sent successfully!"
    except Exception as e:
        return f"Error sending email: {e}"


# Route to render the change password page
@app.route('/change_password')
def change_password():
    return render_template('change_password.html')

# Endpoint to handle OTP request
@app.route('/request_otp', methods=['POST'])
def request_otp():
    data = request.get_json()
    print(f"Received data: {data}")  # Debug log to see what is being received
    username = data.get('username')
    email = data.get('email')

    # Check if the username exists in the database
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM user_credentials WHERE username=?", (username,))
    user = cursor.fetchone()

    if not user or user[0] != email:
        print("Username or email is incorrect.")
        return jsonify({"success": False, "message": "Username or email is incorrect"}), 400

    otp = str(random.randint(100000, 999999))
    otp_storage[email] = {
        "otp": otp,
        "expiry": time.time() + 300  # OTP expires in 5 minutes
    }

    try:
        send_otp_to_email(email, otp)
    except Exception as e:
        print("Error sending OTP:", e)
        return jsonify({"success": False, "message": "Something went wrong. Please try again."}), 500

    return jsonify({"success": True, "message": "OTP sent to your email!"})

# Function to send OTP to email
def send_otp_to_email(email, otp):
    msg = Message('Your OTP Code', recipients=[email])
    msg.body = f'Your OTP code is: {otp}'
    mail.send(msg)

# Endpoint to verify OTP
@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    # Check if OTP exists and is not expired
    if email not in otp_storage:
        return jsonify({"success": False, "message": "OTP request not found"}), 400

    stored_otp = otp_storage[email]
    if time.time() > stored_otp['expiry']:
        del otp_storage[email]  # OTP expired, remove it
        return jsonify({"success": False, "message": "OTP has expired. Please request a new one."}), 400

    if stored_otp['otp'] != otp:
        return jsonify({"success": False, "message": "Invalid OTP."}), 400

    # OTP is valid, allow to proceed to reset password page
    return jsonify({"success": True, "message": "OTP verified successfully!"})

# Route for the reset password page
@app.route('/reset_password')
def reset_password():
    return render_template('reset_password.html')

# Endpoint to reset the password
@app.route('/reset_password', methods=['POST'])
def reset_user_password():
    # Get the data sent from the client
    data = request.get_json()

    # Extract the fields from the received JSON
    email = data.get('email')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    # Basic validation checks
    if not email or not new_password or not confirm_password:
        return jsonify({"success": False, "message": "All fields are mandatory."}), 400

    if new_password != confirm_password:
        return jsonify({"success": False, "message": "Passwords do not match."}), 400

    try:
        # Database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the email exists in the database
        cursor.execute("SELECT email FROM user_credentials WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "Invalid email."}), 400

        # Update the password in the database (as plain text as requested)
        cursor.execute("UPDATE user_credentials SET password = ? WHERE email = ?", (new_password, email))
        conn.commit()

        return jsonify({"success": True, "message": "Password reset successfully!"})

    except pyodbc.Error as e:
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"success": False, "message": f"Something went wrong: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/validate_register_number/<register_number>", methods=["GET"])
def validate_register_number(register_number):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = "SELECT department FROM students WHERE register_number = ?"
        cursor.execute(query, (register_number,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"valid": False, "error": "Register number does not exist."}), 404

        department = result[0]
        if department != "IT":
            return jsonify({"valid": False, "error": "Student is not from the IT department."}), 400

        return jsonify({"valid": True, "department": department}), 200

    except pyodbc.Error as e:
        return jsonify({"valid": False, "error": f"Database error: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/check_marks_submission/<register_number>", methods=["GET"])
def check_marks_submission(register_number):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query to check if marks have already been submitted for the student
        query = "SELECT COUNT(*) FROM marks WHERE register_number = ?"
        cursor.execute(query, (register_number,))
        result = cursor.fetchone()

        if result and result[0] > 0:
            return jsonify({"submitted": True}), 200
        else:
            return jsonify({"submitted": False}), 200

    except pyodbc.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/add_subject_marks", methods=["POST"])
def add_subject_marks():
    try:
        data = request.get_json()
        reg_number = data.get("register_number")
        subjects = data.get("subjects")

        if not reg_number or not subjects:
            return jsonify({"error": "Invalid data provided."}), 400

        # Prepare data for insertion
        marks_data = (
            reg_number,
            subjects["Computer Networks"][0], subjects["Computer Networks"][1], subjects["Computer Networks"][2],
            subjects["Object Oriented Analysis and Design"][0], subjects["Object Oriented Analysis and Design"][1], subjects["Object Oriented Analysis and Design"][2],
            subjects["Resource Management and Graph Theory"][0], subjects["Resource Management and Graph Theory"][1], subjects["Resource Management and Graph Theory"][2],
            subjects["Information Coding Techniques"][0], subjects["Information Coding Techniques"][1], subjects["Information Coding Techniques"][2],
            subjects["Database Management Systems"][0], subjects["Database Management Systems"][1], subjects["Database Management Systems"][2],
        )

        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert marks into the table
        query = """
            INSERT INTO marks (
                register_number,
                CN_Test1, CN_Test2, CN_Test3,
                OOAD_Test1, OOAD_Test2, OOAD_Test3,
                RMGT_Test1, RMGT_Test2, RMGT_Test3,
                ICT_Test1, ICT_Test2, ICT_Test3,
                DBMS_Test1, DBMS_Test2, DBMS_Test3
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, marks_data)
        conn.commit()

        return jsonify({"message": "Marks successfully submitted!"}), 200

    except pyodbc.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()

@app.route('/getStudentMarksAndDetails/<register_number>', methods=['GET'])
def get_student_marks_and_details(register_number):
    try:
        # Establish a connection to the database
        conn = get_db_connection()  # Replace with your actual database connection logic
        cursor = conn.cursor()

        # Query to fetch student details (name) from the students table
        student_query = """
        SELECT name 
        FROM students 
        WHERE register_number = ?
        """
        cursor.execute(student_query, (register_number,))
        student_record = cursor.fetchone()

        if not student_record:
            return jsonify({"error": "Student not found"}), 404

        student_name = student_record[0]

        # Query to fetch student marks from the marks table
        marks_query = """
        SELECT CN_Test1, CN_Test2, CN_Test3, 
               OOAD_Test1, OOAD_Test2, OOAD_Test3, 
               RMGT_Test1, RMGT_Test2, RMGT_Test3,
               ICT_Test1, ICT_Test2, ICT_Test3,
               DBMS_Test1, DBMS_Test2, DBMS_Test3
        FROM marks
        WHERE register_number = ?
        """
        cursor.execute(marks_query, (register_number,))
        marks_record = cursor.fetchone()

        if not marks_record:
            return jsonify({"error": "Marks not found for the student"}), 404

        # Prepare the student data along with the marks
        student_data = {
            "register_number": register_number,
            "name": student_name,
            "CN_Test1": marks_record[0],
            "CN_Test2": marks_record[1],
            "CN_Test3": marks_record[2],
            "OOAD_Test1": marks_record[3],
            "OOAD_Test2": marks_record[4],
            "OOAD_Test3": marks_record[5],
            "RMGT_Test1": marks_record[6],
            "RMGT_Test2": marks_record[7],
            "RMGT_Test3": marks_record[8],
            "ICT_Test1": marks_record[9],
            "ICT_Test2": marks_record[10],
            "ICT_Test3": marks_record[11],
            "DBMS_Test1": marks_record[12],
            "DBMS_Test2": marks_record[13],
            "DBMS_Test3": marks_record[14]
        }

        # Return the student details and marks as JSON
        return jsonify(student_data)

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@app.route('/fetch_register_numbers', methods=['GET'])  # Updated route
def fetch_register_numbers():  # Renamed function
    try:
        # Establish a connection to the database
        conn = get_db_connection()  # Replace with your database connection logic
        cursor = conn.cursor()

        # Query to fetch register numbers from the marks table
        query = "SELECT register_number FROM marks"
        cursor.execute(query)

        # Fetch all register numbers
        records = cursor.fetchall()
        register_numbers = [record[0] for record in records]

        # Return the register numbers as JSON
        return jsonify(register_numbers)

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    app.run(debug=True)
