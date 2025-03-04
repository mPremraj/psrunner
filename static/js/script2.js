// static/js/script.js

document.addEventListener('DOMContentLoaded', function() {
    // Initialize dropdowns and buttons on the main page
    const environmentSelect = document.getElementById('environment');
    const activitySelect = document.getElementById('activityType');
    const versionSelect = document.getElementById('version');
    const viewButton = document.getElementById('viewButton');
    const runButton = document.getElementById('runButton');
    
    if (environmentSelect) {
        environmentSelect.addEventListener('change', function() {
            const environment = this.value;
            
            // Reset activity and version dropdowns
            activitySelect.innerHTML = '<option value="">Select Activity Type</option>';
            versionSelect.innerHTML = '<option value="">Select Version</option>';
            activitySelect.disabled = !environment;
            versionSelect.disabled = true;
            viewButton.disabled = true;
            runButton.disabled = true;
            
            if (environment) {
                // Fetch activities for selected environment
                fetch(`/get_activities?environment=${environment}`)
                    .then(response => response.json())
                    .then(activities => {
                        activities.forEach(activity => {
                            const option = document.createElement('option');
                            option.value = activity;
                            option.textContent = activity;
                            activitySelect.appendChild(option);
                        });
                    })
                    .catch(error => {
                        console.error('Error fetching activities:', error);
                    });
            }
        });
    }
    
    if (activitySelect) {
        activitySelect.addEventListener('change', function() {
            const activity = this.value;
            const environment = environmentSelect.value;
            
            // Reset version dropdown
            versionSelect.innerHTML = '<option value="">Select Version</option>';
            versionSelect.disabled = !activity;
            viewButton.disabled = true;
            runButton.disabled = true;
            
            if (environment && activity) {
                // Fetch versions for selected activity
                fetch(`/get_versions?environment=${environment}&activity=${activity}`)
                    .then(response => response.json())
                    .then(versions => {
                        versions.forEach(version => {
                            const option = document.createElement('option');
                            option.value = version;
                            option.textContent = version;
                            versionSelect.appendChild(option);
                        });
                    })
                    .catch(error => {
                        console.error('Error fetching versions:', error);
                    });
            }
        });
    }
    
    if (versionSelect) {
        versionSelect.addEventListener('change', function() {
            const version = this.value;
            viewButton.disabled = !version;
            runButton.disabled = !version;
        });
    }
    
    // View script button
    if (viewButton) {
        viewButton.addEventListener('click', function() {
            const environment = environmentSelect.value;
            const activity = activitySelect.value;
            const version = versionSelect.value;
            
            if (environment && activity && version) {
                fetch(`/get_script?environment=${environment}&activity=${activity}&version=${version}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            alert(data.error);
                            return;
                        }
                        
                        // Show script content
                        document.getElementById('scriptContent').classList.remove('hidden');
                        document.getElementById('scriptPath').textContent = data.path;
                        document.getElementById('scriptPreview').textContent = data.script;
                    })
                    .catch(error => {
                        console.error('Error fetching script:', error);
                        alert('An error occurred while fetching the script.');
                    });
            }
        });
    }
    
    // Close script button
    const closeScriptBtn = document.getElementById('closeScriptBtn');
    if (closeScriptBtn) {
        closeScriptBtn.addEventListener('click', function() {
            document.getElementById('scriptContent').classList.add('hidden');
        });
    }
    
    // Run script button is implemented in-line in index.html due to its complexity
    // and connection with the task status checking functionality

    // Tab handling for all tabs across the application
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', function() {
            const tabSet = this.closest('.output-tabs').nextElementSibling;
            
            // Remove active class from all buttons and panes in this tab set
            this.closest('.output-tabs').querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            tabSet.querySelectorAll('.tab-pane').forEach(pane => {
                pane.classList.remove('active');
            });
            
            // Add active class to clicked button
            this.classList.add('active');
            
            // Show corresponding tab content
            const tabId = this.getAttribute('data-tab');
            tabSet.querySelector(`#${tabId}-content`).classList.add('active');
        });
    });
});