# Directory structure:
# /app
#   app.py
#   config.json
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
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash
from werkzeug.security import check_password_hash
import win32security
import win32con

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config['SCRIPT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

# Ensure output directory exists
if not os.path.exists(app.config['OUTPUT_FOLDER']):
    os.makedirs(app.config['OUTPUT_FOLDER'])

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
        return True

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
        return True

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if validate_windows_auth(username, password):
            session['user'] = username
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         username = request.form.get('username')
#         password = request.form.get('password')
        
#         if validate_windows_auth(username, password):
#             session['user'] = username
#             return redirect(url_for('index'))
#         else:
#             flash('Invalid username or password')
    
#     return render_template('login.html')

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

def run_powershell_script(script_path, output_path):
    """Run PowerShell script and save output to file"""
    try:
        # Execute the PowerShell script
        result = subprocess.run(
            ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', script_path],
            capture_output=True,
            text=True
        )
        
        # Write output to file
        with open(output_path, 'w') as output_file:
            output_file.write(f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
        
        return {
            'success': True,
            'output_path': output_path,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    except Exception as e:
        # Handle any errors
        error_message = str(e)
        with open(output_path, 'w') as output_file:
            output_file.write(f"ERROR: {error_message}")
        
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
    if env in config and activity in config[env]:
        for item in config[env][activity]:
            if item['version'] == version:
                script_path = os.path.join(app.config['SCRIPT_FOLDER'], item['script'])
                break
    
    if script_path and os.path.exists(script_path):
        script_name = os.path.basename(script_path).split('.')[0]
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"{script_name}_{timestamp}.txt"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_file)
        
        # Start script execution in a separate thread
        task_id = f"{env}_{activity}_{version}_{timestamp}"
        session['current_task'] = task_id
        
        def execute_script():
            result = run_powershell_script(script_path, output_path)
            # Store result for frontend to retrieve
            app.config[f'task_{task_id}'] = result
        
        thread = threading.Thread(target=execute_script)
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
    # Check if task has completed
    if f'task_{task_id}' in app.config:
        result = app.config[f'task_{task_id}']
        # Clean up task data after retrieval
        if 'current_task' in session and session['current_task'] == task_id:
            session.pop('current_task', None)
        return jsonify({'status': 'completed', 'result': result})
    
    return jsonify({'status': 'running'})

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
