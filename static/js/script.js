// static/js/script.js
document.addEventListener('DOMContentLoaded', function() {
    // Elements for the script runner page
    const environmentSelect = document.getElementById('environment');
    const activityTypeSelect = document.getElementById('activityType');
    const versionSelect = document.getElementById('version');
    const viewButton = document.getElementById('viewButton');
    const runButton = document.getElementById('runButton');
    const scriptContent = document.getElementById('scriptContent');
    const scriptPreview = document.getElementById('scriptPreview');
    const scriptPath = document.getElementById('scriptPath');
    const closeScriptBtn = document.getElementById('closeScriptBtn');
    const executionStatus = document.getElementById('executionStatus');
    const statusIndicator = document.getElementById('statusIndicator');
    const executionResult = document.getElementById('executionResult');
    const outputFilePath = document.getElementById('outputFilePath');
    const stdoutContent = document.getElementById('stdoutContent');
    const stderrContent = document.getElementById('stderrContent');
    
    // Initialize elements if they exist
    if (environmentSelect) {
        // Environment selection change
        environmentSelect.addEventListener('change', function() {
            resetSubsequentSelections('environment');
            if (this.value) {
                fetchActivityTypes(this.value);
            }
        });
        
        // Activity type selection change
        activityTypeSelect.addEventListener('change', function() {
            resetSubsequentSelections('activity');
            if (this.value) {
                fetchVersions(environmentSelect.value, this.value);
            }
        });
        
        // Version selection change
        versionSelect.addEventListener('change', function() {
            if (this.value) {
                viewButton.disabled = false;
                runButton.disabled = false;
            } else {
                viewButton.disabled = true;
                runButton.disabled = true;
            }
        });
        
        // View script button click
        viewButton.addEventListener('click', function() {
            if (versionSelect.value) {
                fetchScriptContent(
                    environmentSelect.value,
                    activityTypeSelect.value,
                    versionSelect.value
                );
            }
        });
        
        // Run script button click
        runButton.addEventListener('click', function() {
            if (versionSelect.value) {
                runScript(
                    environmentSelect.value,
                    activityTypeSelect.value,
                    versionSelect.value
                );
            }
        });
        
        // Close script preview button
        closeScriptBtn.addEventListener('click', function() {
            scriptContent.classList.add('hidden');
        });
    }
    
    // Function to reset dropdowns based on which selection changed
    function resetSubsequentSelections(changedLevel) {
        if (changedLevel === 'environment') {
            activityTypeSelect.innerHTML = '<option value="">Select Activity Type</option>';
            activityTypeSelect.disabled = environmentSelect.value === '';
            
            versionSelect.innerHTML = '<option value="">Select Version</option>';
            versionSelect.disabled = true;
            
            viewButton.disabled = true;
            runButton.disabled = true;
        } else if (changedLevel === 'activity') {
            versionSelect.innerHTML = '<option value="">Select Version</option>';
            versionSelect.disabled = activityTypeSelect.value === '';
            
            viewButton.disabled = true;
            runButton.disabled = true;
        }
    }
    
    // Function to fetch activity types for selected environment
    function fetchActivityTypes(environment) {
        fetch(`/get_activities?environment=${encodeURIComponent(environment)}`)
            .then(response => response.json())
            .then(activities => {
                let options = '<option value="">Select Activity Type</option>';
                activities.forEach(activity => {
                    options += `<option value="${activity}">${activity}</option>`;
                });
                activityTypeSelect.innerHTML = options;
                activityTypeSelect.disabled = activities.length === 0;
            })
            .catch(error => console.error('Error fetching activities:', error));
    }
    
    // Function to fetch versions for selected environment and activity
    function fetchVersions(environment, activity) {
        fetch(`/get_versions?environment=${encodeURIComponent(environment)}&activity=${encodeURIComponent(activity)}`)
            .then(response => response.json())
            .then(versions => {
                let options = '<option value="">Select Version</option>';
                versions.forEach(version => {
                    options += `<option value="${version}">${version}</option>`;
                });
                versionSelect.innerHTML = options;
                versionSelect.disabled = versions.length === 0;
            })
            .catch(error => console.error('Error fetching versions:', error));
    }
    
    // Function to fetch and display script content
    function fetchScriptContent(environment, activity, version) {
        fetch(`/get_script?environment=${encodeURIComponent(environment)}&activity=${encodeURIComponent(activity)}&version=${encodeURIComponent(version)}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }
                
                scriptPreview.textContent = data.script;
                scriptPath.textContent = data.path;
                scriptContent.classList.remove('hidden');
            })
            .catch(error => console.error('Error fetching script content:', error));
    }
    
    // Function to run the selected script
    function runScript(environment, activity, version) {
        // Hide previous execution results
        executionStatus.classList.remove('hidden');
        statusIndicator.classList.remove('hidden');
        executionResult.classList.add('hidden');
        
        // Prepare form data
        const formData = new FormData();
        formData.append('environment', environment);
        formData.append('activity', activity);
        formData.append('version', version);
        
        // Run the script
        fetch('/run_script', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
                executionStatus.classList.add('hidden');
                return;
            }
            
            // Poll for task completion
            pollTaskStatus(data.task_id, data.output_file);
        })
        .catch(error => {
            console.error('Error running script:', error);
            executionStatus.classList.add('hidden');
        });
    }
    
    // Function to poll for task completion
    function pollTaskStatus(taskId, outputFile) {
        const interval = setInterval(() => {
            fetch(`/task_status/${taskId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'completed') {
                        clearInterval(interval);
                        displayTaskResult(data.result, outputFile);
                    }
                })
                .catch(error => {
                    console.error('Error polling task status:', error);
                    clearInterval(interval);
                    executionStatus.classList.add('hidden');
                });
        }, 1000);
    }
    
    // Function to display task result
    function displayTaskResult(result, outputFile) {
        statusIndicator.classList.add('hidden');
        executionResult.classList.remove('hidden');
        
        outputFilePath.textContent = outputFile;
        stdoutContent.textContent = result.stdout || 'No output';
        stderrContent.textContent = result.stderr || 'No errors';
    }
});
