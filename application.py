from flask import Flask, request, jsonify, render_template, send_file
import psycopg2
import os

# Flask app setup
app = Flask(__name__)

# Configurations
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database configuration
DB_HOST = 'localhost'
DB_NAME = 'postgres'
DB_USER = 'postgres'
DB_PASSWORD = '123456'

def get_db_connection():
    """Establish a connection to the database."""
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def create_tables():
    """Create necessary tables if they do not exist."""
    connection = get_db_connection()
    cursor = connection.cursor()

    # File table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file (
            id SERIAL PRIMARY KEY,
            private_key VARCHAR(255) NOT NULL UNIQUE,
            file_name VARCHAR(255) NOT NULL,
            file_type VARCHAR(255) NOT NULL,
            file_path VARCHAR(255) NOT NULL
        );
    """)

    # Feedback table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            feedback_text TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    connection.commit()
    cursor.close()
    connection.close()

# Create tables at startup
create_tables()

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    """Handles feedback submission."""
    try:
        data = request.json
        feedback_text = data.get('feedback')

        if not feedback_text or not feedback_text.strip():
            return jsonify({"error": "Feedback cannot be empty"}), 400

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("INSERT INTO feedback (feedback_text) VALUES (%s);", (feedback_text,))
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Feedback submitted successfully!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/send', methods=['POST'])
def send_message():
    """Handles file upload and storage."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    private_key = request.form.get('privateKey')

    if not private_key or not file:
        return jsonify({'error': 'Private key and file are required.'}), 400

    # Check if the file exceeds the max size limit
    if file.content_length > MAX_FILE_SIZE:
        return jsonify({'error': 'File exceeds maximum allowed size (5GB).'}), 400

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        # Check if the private key already exists
        cursor.execute("SELECT * FROM file WHERE private_key = %s;", (private_key,))
        if cursor.fetchone():
            return jsonify({'error': 'Private key already exists. Use a unique key.'}), 400

        # Save the file to the filesystem
        file_name = file.filename
        file_type = file.content_type
        file_path = os.path.join(UPLOAD_FOLDER, file_name)
        file.save(file_path)

        # Insert file metadata into the database
        cursor.execute("""
            INSERT INTO file (private_key, file_name, file_type, file_path)
            VALUES (%s, %s, %s, %s);
        """, (private_key, file_name, file_type, file_path))
        connection.commit()

        return jsonify({'success': True, 'message': 'File uploaded and stored successfully!'}), 200

    except Exception as e:
        connection.rollback()
        return jsonify({'error': 'Failed to store file.', 'details': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/receive', methods=['POST'])
def receive_message():
    """Handles file retrieval by private key."""
    data = request.get_json()
    private_key = data.get('privateKey')

    if not private_key:
        return jsonify({'error': 'Private key is required.'}), 400

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        # Retrieve file metadata from the database
        cursor.execute("SELECT file_name, file_type, file_path FROM file WHERE private_key = %s;", (private_key,))
        file = cursor.fetchone()

        if not file:
            return jsonify({'error': 'File not found.'}), 404

        file_name, file_type, file_path = file

        # Ensure the file exists on the filesystem
        if not os.path.exists(file_path):
            return jsonify({'error': 'File is missing on the server.'}), 500

        # Send the file as a downloadable response
        return send_file(file_path, as_attachment=True, download_name=file_name, mimetype=file_type)

    except Exception as e:
        return jsonify({'error': 'Failed to retrieve file.', 'details': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/')
def index():
    """Renders the home page."""
    return render_template('home.html')

@app.route('/home')
def home():
    """Renders the home page."""
    return render_template('home.html')

@app.route('/about')
def about():
    """Renders the about page."""
    return render_template('about.html')

@app.route('/send')
def send():
    """Renders the send file page."""
    return render_template('send.html')

@app.route('/receive')
def receive():
    """Renders the receive file page."""
    return render_template('receive.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)