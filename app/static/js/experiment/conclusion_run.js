    document.addEventListener('DOMContentLoaded', function() {
        const confirmCheck = document.getElementById('confirmCheck');
        const runButton = document.getElementById('runButton');
        const progressCard = document.getElementById('progressCard');
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        const progressLog = document.getElementById('progressLog');
        const completionCard = document.getElementById('completionCard');
        const errorCard = document.getElementById('errorCard');
        const errorMessage = document.getElementById('errorMessage');
        
        // Enable or disable run button based on checkbox
        confirmCheck.addEventListener('change', function() {
            runButton.disabled = !confirmCheck.checked;
        });
        
        // Handle run button click
        runButton.addEventListener('click', function() {
            // Disable button and show progress
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running Prediction...';
            progressCard.classList.remove('d-none');
            
            // Add log entry
            addLogEntry('Starting conclusion prediction experiment...');
            
            // Get CSRF token from form (if using CSRF protection)
            const csrfToken = document.querySelector('meta[name=csrf-token]')?.content || '';
            
            // Call API to run conclusion predictions
            fetch((window.CONCLUSION_RUN || {}).predictUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show completion card
                    progressCard.classList.add('d-none');
                    completionCard.classList.remove('d-none');
                    
                    // Add log entries
                    addLogEntry('Conclusion prediction completed successfully.');
                    addLogEntry(data.message);
                } else {
                    // Show error
                    progressCard.classList.add('d-none');
                    errorCard.classList.remove('d-none');
                    errorMessage.textContent = data.error || 'An unknown error occurred.';
                    
                    // Add log entry
                    addLogEntry('Error: ' + (data.error || 'An unknown error occurred.'));
                }
            })
            .catch(error => {
                // Show error
                progressCard.classList.add('d-none');
                errorCard.classList.remove('d-none');
                errorMessage.textContent = error.toString();
                
                // Add log entry
                addLogEntry('Error: ' + error.toString());
            });
            
            // Simulate progress updates for UX
            simulateProgress();
        });
        
        // Function to add log entry
        function addLogEntry(message) {
            const timestamp = new Date().toLocaleTimeString();
            const entry = document.createElement('div');
            entry.innerHTML = `<small class="text-muted">[${timestamp}]</small> ${message}`;
            progressLog.appendChild(entry);
            progressLog.scrollTop = progressLog.scrollHeight;
        }
        
        // Simulate progress for better UX
        function simulateProgress() {
            let progress = 0;
            const numCases = (window.CONCLUSION_RUN || {}).numCases ?? 0;
            const interval = setInterval(() => {
                if (progress >= 100) {
                    clearInterval(interval);
                    return;
                }
                
                progress += 8;
                progressBar.style.width = `${Math.min(progress, 100)}%`;
                
                // Add some realistic-looking progress messages
                if (progress === 8) {
                    addLogEntry('Initializing LLM services...');
                } else if (progress === 16) {
                    addLogEntry('Loading case documents...');
                } else if (progress === 32) {
                    addLogEntry(`Processing ${numCases} case(s)...`);
                } else if (progress === 56) {
                    addLogEntry('Extracting case context (excluding conclusions)...');
                } else if (progress === 72) {
                    addLogEntry('Applying ontology-enhanced reasoning...');
                } else if (progress === 88) {
                    addLogEntry('Generating conclusion predictions...');
                }
                
                progressText.textContent = `Progress: ${Math.min(progress, 100)}%`;
            }, 1200);
        }
    });
