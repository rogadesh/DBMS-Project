from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import pyodbc
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)

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
    return redirect(url_for('signup'))  # Redirects to the signup page on startup

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

# Change Password route to allow users to change their password
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if not new_password or not confirm_password:
            return render_template('change_password.html', error="All fields are mandatory.")

        if new_password != confirm_password:
            return render_template('change_password.html', error="Passwords do not match.")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if user exists
            cursor.execute("SELECT username FROM user_credentials WHERE username = ? AND email = ?", (username, email))
            if not cursor.fetchone():
                return render_template('change_password.html', error="Invalid username or email.")

            # Update the password
            cursor.execute("UPDATE user_credentials SET password = ? WHERE username = ?", (new_password, username))
            conn.commit()

            return render_template('change_password.html', success=True)

        except pyodbc.Error as e:
            return render_template('change_password.html', error=f"Database error: {str(e)}")

        finally:
            cursor.close()
            conn.close()

    return render_template('change_password.html')

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
        return jsonify({"message": "Student inserted successfully!"}), 201

    except pyodbc.IntegrityError:  # Handle duplicate primary key error
        return jsonify({"error": "Register number already exists!"}), 400

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

# Update student
@app.route("/update_student", methods=["PUT"])
def update_student():
    data = request.json
    try:
        # Check if all required data is present
        if not all(key in data for key in ["register_number", "name", "department", "cgpa", "attendance"]):
            return jsonify({"error": "Missing data for one or more fields."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            UPDATE buffer
            SET name = ?, department = ?, cgpa = ?, attendance = ?
            WHERE register_number = ?
        """
        cursor.execute(query, (
            data["name"], data["department"], data["cgpa"],
            data["attendance"], data["register_number"]
        ))

        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "No student found with the given register number."}), 404

        return jsonify({"message": "Student updated successfully!"}), 200

    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

# Delete student
@app.route("/delete_student/<register_number>", methods=["DELETE"])
def delete_student(register_number):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = "DELETE FROM buffer WHERE register_number = ?"
        cursor.execute(query, (register_number,))

        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "No student found with the given register number."}), 404

        return jsonify({"message": "Student deleted successfully!"}), 200

    except pyodbc.Error as e:
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
            return jsonify({"error": "Register number already exists in the students table!"}), 400

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
        return jsonify({"message": "Student record inserted successfully into students table!"}), 201

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

@app.route('/getStudentDetails/<register_number>', methods=['GET'])
def get_student_details(register_number):
    try:
        # Use the pre-existing database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query to fetch the student details
        cursor.execute("SELECT register_number, name, department, cgpa, attendance FROM students WHERE register_number = ?", register_number)
        row = cursor.fetchone()

        if row:
            # Map row data to JSON response
            student = {
                "register_number": row[0],
                "name": row[1],
                "department": row[2],
                "cgpa": row[3],
                "attendance": row[4],
            }
            return jsonify(student)
        else:
            return jsonify(None), 404  # No student found

    except Exception as e:
        print("Error fetching student details:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/search_students', methods=['GET'])
def search_students():
    register_prefix = request.args.get('register_number', '')
    if not register_prefix:
        return jsonify({'error': 'Register number prefix is required'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT register_number, name, department, cgpa, attendance
            FROM students
            WHERE register_number LIKE ?
        """
        cursor.execute(query, (register_prefix + '%',))
        results = cursor.fetchall()
        conn.close()

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
        return jsonify(students)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
if __name__ == "__main__":
    app.run(debug=True)
