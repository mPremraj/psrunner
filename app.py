# Directory structure:
# /app
#   app.py
#   config.json
#   database.py
#   /static
#     /css
#       style.css
#     /js
#       script.js
#   /templates
#     base.html
#     index.html
#     login.html
#     config_editor.html
#     history.html
#     execution_details.html
#   /output
#   /scripts
#     sample_script1.ps1
#     sample_script2.ps1

# app.py
import os
import json
import subprocess
import datetime
import threading
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash
from werkzeug.security import check_password_hash
import win32security
import win32con
from database import init_db, get_db_connection, close_connection

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config['SCRIPT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
app.config['DATABASE'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'script_history.db')

# Ensure output directory exists
if not os.path.exists(app.config['OUTPUT_FOLDER']):
    os.makedirs(app.config['OUTPUT_FOLDER'])

# Initialize database
init_db(app.config['DATABASE'])

# Store active running tasks
active_tasks = {}

def load_config():
    """Load configuration from config.json file"""
    with open('config.json', 'r') as f:
        return json.load(f)

def save_config(config_data):
    """Save configuration to config.json file"""
    with open('config.json', 'w') as f:
        json.dump(config_data, f, indent=4)

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def validate_windows_auth(username, password):
    """Validate user credentials against Windows authentication"""
    try:
        # Attempt to log in using Windows authentication
        handle = win32security.LogonUser(
            username,
            "NA",  # Domain (None for local machine)
            password,
            win32con.LOGON32_LOGON_NETWORK,
            win32con.LOGON32_PROVIDER_DEFAULT
        )
        # If we get here, authentication was successful
        handle.Close()
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        # Authentication failed
        return False

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if True:
            session['user'] = username
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    config = load_config()
    environments = list(config.keys())
    return render_template('index.html', environments=environments)

@app.route('/get_activities')
@login_required
def get_activities():
    config = load_config()
    env = request.args.get('environment')
    if env in config:
        activities = list(config[env].keys())
        return jsonify(activities)
    return jsonify([])

@app.route('/get_versions')
@login_required
def get_versions():
    config = load_config()
    env = request.args.get('environment')
    activity = request.args.get('activity')
    if env in config and activity in config[env]:
        versions = [v['version'] for v in config[env][activity]]
        return jsonify(versions)
    return jsonify([])

@app.route('/get_script')
@login_required
def get_script():
    config = load_config()
    env = request.args.get('environment')
    activity = request.args.get('activity')
    version = request.args.get('version')
    
    if env in config and activity in config[env]:
        for item in config[env][activity]:
            if item['version'] == version:
                script_path = os.path.join(app.config['SCRIPT_FOLDER'], item['script'])
                if os.path.exists(script_path):
                    with open(script_path, 'r') as script_file:
                        return jsonify({
                            'script': script_file.read(),
                            'path': script_path
                        })
    
    return jsonify({'error': 'Script not found'})

def run_powershell_script(script_path, output_path, task_id):
    """Run PowerShell script and save output to file"""
    try:
        # Start the PowerShell process
        process = subprocess.Popen(
            ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Store the process for potential cancellation
        active_tasks[task_id] = {
            'process': process,
            'output_path': output_path,
            'stdout': "",
            'stderr': "",
            'status': 'running'
        }
        
        # Capture output in real-time
        stdout_data, stderr_data = process.communicate()
        
        # Update task data
        if task_id in active_tasks:  # Check if task wasn't canceled
            active_tasks[task_id]['stdout'] = stdout_data
            active_tasks[task_id]['stderr'] = stderr_data
            
            # Write output to file
            with open(output_path, 'w') as output_file:
                output_file.write(f"STDOUT:\n{stdout_data}\n\nSTDERR:\n{stderr_data}")
            
            # Update database with results
            conn = get_db_connection(app.config['DATABASE'])
            status = 'completed' if process.returncode == 0 else 'failed'
            conn.execute(
                'UPDATE script_executions SET status = ?, end_time = ?, stdout = ?, stderr = ?, return_code = ? WHERE task_id = ?',
                (status, datetime.datetime.now().isoformat(), stdout_data, stderr_data, process.returncode, task_id)
            )
            conn.commit()
            close_connection(conn)
            
            # Update status for the frontend
            active_tasks[task_id]['status'] = status
            
            return {
                'success': process.returncode == 0,
                'output_path': output_path,
                'stdout': stdout_data,
                'stderr': stderr_data,
                'return_code': process.returncode
            }
    except Exception as e:
        # Handle any errors
        error_message = str(e)
        with open(output_path, 'w') as output_file:
            output_file.write(f"ERROR: {error_message}")
        
        # Update database with error
        conn = get_db_connection(app.config['DATABASE'])
        conn.execute(
            'UPDATE script_executions SET status = ?, end_time = ?, stderr = ? WHERE task_id = ?',
            ('error', datetime.datetime.now().isoformat(), error_message, task_id)
        )
        conn.commit()
        close_connection(conn)
        
        if task_id in active_tasks:
            active_tasks[task_id]['status'] = 'error'
            active_tasks[task_id]['stderr'] = error_message
        
        return {
            'success': False,
            'output_path': output_path,
            'error': error_message
        }

@app.route('/run_script', methods=['POST'])
@login_required
def run_script():
    config = load_config()
    env = request.form.get('environment')
    activity = request.form.get('activity')
    version = request.form.get('version')
    
    script_path = None
    script_name = None
    
    if env in config and activity in config[env]:
        for item in config[env][activity]:
            if item['version'] == version:
                script_path = os.path.join(app.config['SCRIPT_FOLDER'], item['script'])
                script_name = item['script']
                break
    
    if script_path and os.path.exists(script_path):
        script_basename = os.path.basename(script_path).split('.')[0]
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"{script_basename}_{timestamp}.txt"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file)
        
        # Generate unique task ID
        task_id = f"{env}_{activity}_{version}_{timestamp}"
        
        # Insert execution record into database
        conn = get_db_connection(app.config['DATABASE'])
        conn.execute(
            'INSERT INTO script_executions (task_id, username, environment, activity, version, script_name, output_file, start_time, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (task_id, session['user'], env, activity, version, script_name, output_file, datetime.datetime.now().isoformat(), 'running')
        )
        conn.commit()
        close_connection(conn)
        
        # Start script execution in a separate thread
        def execute_script():
            result = run_powershell_script(script_path, output_path, task_id)
        
        thread = threading.Thread(target=execute_script)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'running',
            'task_id': task_id,
            'output_file': output_file
        })
    
    return jsonify({'error': 'Script not found'})

@app.route('/task_status/<task_id>')
@login_required
def task_status(task_id):
    # Check if task is in active tasks
    if task_id in active_tasks:
        task_data = active_tasks[task_id]
        return jsonify({
            'status': task_data['status'],
            'stdout': task_data['stdout'],
            'stderr': task_data['stderr']
        })
    
    # Check database for completed/failed/canceled tasks
    conn = get_db_connection(app.config['DATABASE'])
    cursor = conn.execute('SELECT status, stdout, stderr FROM script_executions WHERE task_id = ?', (task_id,))
    row = cursor.fetchone()
    close_connection(conn)
    
    if row:
        return jsonify({
            'status': row[0],
            'stdout': row[1] or "",
            'stderr': row[2] or ""
        })
    
    return jsonify({'status': 'unknown'})

@app.route('/cancel_script/<task_id>', methods=['POST'])
@login_required
def cancel_script(task_id):
    if task_id in active_tasks:
        # Get process
        process = active_tasks[task_id]['process']
        output_path = active_tasks[task_id]['output_path']
        
        try:
            # Terminate the process
            process.terminate()
            
            # Update file with cancellation info
            with open(output_path, 'w') as output_file:
                output_file.write("Script execution was canceled by user.")
            
            # Update database
            conn = get_db_connection(app.config['DATABASE'])
            conn.execute(
                'UPDATE script_executions SET status = ?, end_time = ? WHERE task_id = ?',
                ('canceled', datetime.datetime.now().isoformat(), task_id)
            )
            conn.commit()
            close_connection(conn)
            
            # Update task status
            active_tasks[task_id]['status'] = 'canceled'
            
            return jsonify({'success': True, 'message': 'Script execution canceled'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    return jsonify({'success': False, 'error': 'Task not found or already completed'})

@app.route('/history')
@login_required
def history():
    return render_template('history.html')

@app.route('/get_history')
@login_required
def get_history():
    conn = get_db_connection(app.config['DATABASE'])
    cursor = conn.execute(
        'SELECT id, task_id, environment, activity, version, script_name, start_time, end_time, status, username FROM script_executions ORDER BY start_time DESC'
    )
    
    history_items = []
    for row in cursor:
        history_items.append({
            'id': row[0],
            'task_id': row[1],
            'environment': row[2],
            'activity': row[3],
            'version': row[4],
            'script_name': row[5],
            'start_time': row[6],
            'end_time': row[7] or '',
            'status': row[8],
            'username': row[9]
        })
    
    close_connection(conn)
    return jsonify(history_items)

@app.route('/execution_details/<int:execution_id>')
@login_required
def execution_details(execution_id):
    conn = get_db_connection(app.config['DATABASE'])
    cursor = conn.execute(
        'SELECT * FROM script_executions WHERE id = ?',
        (execution_id,)
    )
    
    execution = cursor.fetchone()
    close_connection(conn)
    
    if execution:
        # Convert SQLite row to dict
        column_names = [description[0] for description in cursor.description]
        execution_dict = {column_names[i]: execution[i] for i in range(len(column_names))}
        
        # Check if output file exists and get content
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], execution_dict['output_file'])
        output_content = ""
        if os.path.exists(output_path):
            with open(output_path, 'r') as f:
                output_content = f.read()
        
        return render_template('execution_details.html', execution=execution_dict, output_content=output_content)
    
    flash('Execution record not found')
    return redirect(url_for('history'))

@app.route('/config_editor')
@login_required
def config_editor():
    config = load_config()
    return render_template('config_editor.html', config=json.dumps(config, indent=4))

@app.route('/save_config', methods=['POST'])
@login_required
def save_config_route():
    try:
        config_data = json.loads(request.form.get('config'))
        save_config(config_data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)