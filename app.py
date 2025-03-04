import os
import json
import subprocess
import datetime
import threading
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash
from werkzeug.security import check_password_hash
import win32security
import win32con

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config['SCRIPT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
app.config['HISTORY_FILE'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'script_history.xml')

# Ensure output directory exists
if not os.path.exists(app.config['OUTPUT_FOLDER']):
    os.makedirs(app.config['OUTPUT_FOLDER'])

# Store active running tasks
active_tasks = {}

def init_history_file():
    """Initialize XML history file if it doesn't exist"""
    if not os.path.exists(app.config['HISTORY_FILE']):
        root = ET.Element('script_executions')
        tree = ET.ElementTree(root)
        tree.write(app.config['HISTORY_FILE'], encoding='utf-8', xml_declaration=True)

def save_execution_record(task_id, username, env, activity, version, script_name, output_file, start_time, status):
    """Save execution record to XML file"""
    try:
        tree = ET.parse(app.config['HISTORY_FILE'])
        root = tree.getroot()

        # Create new execution record
        execution = ET.SubElement(root, 'execution')
        ET.SubElement(execution, 'id').text = str(len(root.findall('execution')) + 1)
        ET.SubElement(execution, 'task_id').text = task_id
        ET.SubElement(execution, 'username').text = username
        ET.SubElement(execution, 'environment').text = env
        ET.SubElement(execution, 'activity').text = activity
        ET.SubElement(execution, 'version').text = version
        ET.SubElement(execution, 'script_name').text = script_name
        ET.SubElement(execution, 'output_file').text = output_file
        ET.SubElement(execution, 'start_time').text = start_time
        ET.SubElement(execution, 'end_time').text = ""
        ET.SubElement(execution, 'status').text = status
        ET.SubElement(execution, 'stdout').text = ""
        ET.SubElement(execution, 'stderr').text = ""

        # Pretty print and save
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        with open(app.config['HISTORY_FILE'], 'w') as f:
            f.write(reparsed.toprettyxml(indent="  "))

    except Exception as e:
        print(f"Error saving execution record: {e}")

def update_execution_record(task_id, status=None, end_time=None, stdout=None, stderr=None):
    """Update execution record in XML file"""
    try:
        tree = ET.parse(app.config['HISTORY_FILE'])
        root = tree.getroot()

        for execution in root.findall('execution'):
            if execution.find('task_id').text == task_id:
                if status:
                    execution.find('status').text = status
                if end_time:
                    execution.find('end_time').text = end_time
                if stdout is not None:
                    execution.find('stdout').text = stdout
                if stderr is not None:
                    execution.find('stderr').text = stderr

                # Pretty print and save
                rough_string = ET.tostring(root, 'utf-8')
                reparsed = minidom.parseString(rough_string)
                with open(app.config['HISTORY_FILE'], 'w') as f:
                    f.write(reparsed.toprettyxml(indent="  "))
                break

    except Exception as e:
        print(f"Error updating execution record: {e}")

def get_execution_history():
    """Retrieve execution history from XML file"""
    try:
        tree = ET.parse(app.config['HISTORY_FILE'])
        root = tree.getroot()

        history_items = []
        for execution in root.findall('execution'):
            history_items.append({
                'id': execution.find('id').text,
                'task_id': execution.find('task_id').text,
                'environment': execution.find('environment').text,
                'activity': execution.find('activity').text,
                'version': execution.find('version').text,
                'script_name': execution.find('script_name').text,
                'start_time': execution.find('start_time').text,
                'end_time': execution.find('end_time').text or '',
                'status': execution.find('status').text,
                'username': execution.find('username').text
            })

        # Sort by start time, most recent first
        return sorted(history_items, key=lambda x: x['start_time'], reverse=True)

    except Exception as e:
        print(f"Error retrieving execution history: {e}")
        return []

def get_executiondetails(task_id):
    """Retrieve specific execution details from XML file"""
    try:
        tree = ET.parse(app.config['HISTORY_FILE'])
        root = tree.getroot()

        for execution in root.findall('execution'):
            if execution.find('task_id').text == task_id:
                # Convert XML element to dictionary
                details = {
                    'id': execution.find('id').text,
                    'task_id': execution.find('task_id').text,
                    'environment': execution.find('environment').text,
                    'activity': execution.find('activity').text,
                    'version': execution.find('version').text,
                    'script_name': execution.find('script_name').text,
                    'output_file': execution.find('output_file').text,
                    'start_time': execution.find('start_time').text,
                    'end_time': execution.find('end_time').text or '',
                    'status': execution.find('status').text,
                    'username': execution.find('username').text,
                    'stdout': execution.find('stdout').text or '',
                    'stderr': execution.find('stderr').text or ''
                }
                return details

    except Exception as e:
        print(f"Error retrieving execution details: {e}")
        return None

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def load_config():
    """Load configuration from config.json file"""
    with open('config.json', 'r') as f:
        return json.load(f)

def save_config(config_data):
    """Save configuration to config.json file"""
    with open('config.json', 'w') as f:
        json.dump(config_data, f, indent=4)

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
        
        if True:  # Replace with actual authentication if needed
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
            
            # Update XML with results
            status = 'completed' if process.returncode == 0 else 'failed'
            update_execution_record(
                task_id, 
                status=status, 
                end_time=datetime.datetime.now().isoformat(),
                stdout=stdout_data,
                stderr=stderr_data
            )
            
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
        
        # Update XML with error
        update_execution_record(
            task_id, 
            status='error', 
            end_time=datetime.datetime.now().isoformat(),
            stderr=error_message
        )
        
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
        
        # Insert execution record
        save_execution_record(
            task_id, session['user'], env, activity, version, 
            script_name, output_file, datetime.datetime.now().isoformat(), 'running'
        )
        
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
    
    # Check XML for completed/failed/canceled tasks
    executiondetails = get_executiondetails(task_id)
    
    if executiondetails:
        return jsonify({
            'status': executiondetails['status'],
            'stdout': executiondetails['stdout'] or "",
            'stderr': executiondetails['stderr'] or ""
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
            
            # Update XML record
            update_execution_record(
                task_id, 
                status='canceled', 
                end_time=datetime.datetime.now().isoformat()
            )
            
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
    history_items = get_execution_history()
    return jsonify(history_items)

@app.route('/executiondetails/<string:execution_id>')
@login_required
def executiondetails(execution_id):
    # Convert numeric ID to task_id by searching through XML history
    try:
        tree = ET.parse(app.config['HISTORY_FILE'])
        root = tree.getroot()

        for execution in root.findall('execution'):
            if execution.find('id').text == str(execution_id):
                task_id = execution.find('task_id').text
                break
        else:
            flash('Execution record not found')
            return redirect(url_for('history'))

        # Now fetch the details using task_id
        execution = get_executiondetails(task_id)
        
        if execution:
            # Check if output file exists and get content
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], execution['output_file'])
            output_content = ""
            if os.path.exists(output_path):
                with open(output_path, 'r') as f:
                    output_content = f.read()
            
            # Add task_id to execution details to match frontend expectations
            execution['id'] = execution_id
            
            return render_template('executiondetails.html', execution=execution, output_content=output_content)
        
        flash('Execution record not found')
        return redirect(url_for('history'))

    except Exception as e:
        print(f"Error in execution_details: {e}")
        flash('An error occurred while retrieving execution details')
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
    # Initialize XML history file before running app
    init_history_file()
    app.run(debug=True)
           