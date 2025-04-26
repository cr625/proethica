/**
 * Ontology Diff Viewer JavaScript
 * 
 * This script handles the interaction with the diff viewer interface,
 * allowing users to compare different versions of an ontology.
 */

// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    // Set up diff modal events
    setupDiffModal();
    
    // Set up compare buttons on version list items
    setupCompareButtons();
});

/**
 * Set up the diff modal
 */
function setupDiffModal() {
    // Close button event
    document.getElementById('closeDiffBtn').addEventListener('click', function() {
        document.getElementById('diffModal').classList.remove('show');
        document.getElementById('diffModalBackdrop').style.display = 'none';
    });
    
    // Format toggle
    document.getElementById('diffFormatToggle').addEventListener('change', function() {
        // If we already have versions selected, reload the diff with the new format
        const fromVersion = document.getElementById('diffFromVersion').value;
        const toVersion = document.getElementById('diffToVersion').value;
        
        if (fromVersion && toVersion) {
            loadDiff(fromVersion, toVersion);
        }
    });
    
    // Version selection changes
    document.getElementById('diffFromVersion').addEventListener('change', function() {
        const fromVersion = this.value;
        const toVersion = document.getElementById('diffToVersion').value;
        
        if (fromVersion && toVersion) {
            loadDiff(fromVersion, toVersion);
        }
    });
    
    document.getElementById('diffToVersion').addEventListener('change', function() {
        const fromVersion = document.getElementById('diffFromVersion').value;
        const toVersion = this.value;
        
        if (fromVersion && toVersion) {
            loadDiff(fromVersion, toVersion);
        }
    });
}

/**
 * Set up compare buttons on version list items
 */
function setupCompareButtons() {
    // This will be called whenever the version list is updated
    // Add a mutation observer to the version list to detect when it's updated
    const versionList = document.getElementById('versionList');
    
    // Create a new MutationObserver
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                // Version list was updated, add compare buttons to each item
                addCompareButtonsToVersions();
            }
        });
    });
    
    // Start observing
    observer.observe(versionList, { childList: true });
}

/**
 * Add compare buttons to each version item in the list
 */
function addCompareButtonsToVersions() {
    // Get all version items
    const versionItems = document.querySelectorAll('#versionList li');
    
    // Remove any existing compare buttons first
    document.querySelectorAll('.compare-version-btn').forEach(btn => {
        btn.remove();
    });
    
    // Add a compare button to each item
    versionItems.forEach(item => {
        // Skip items without version data
        if (!item.dataset.versionNumber) {
            return;
        }
        
        // Create the compare button
        const compareBtn = document.createElement('button');
        compareBtn.className = 'btn btn-sm btn-outline-secondary compare-version-btn';
        compareBtn.innerHTML = 'Compare';
        compareBtn.setAttribute('title', 'Compare this version with another');
        
        // Add click handler
        compareBtn.addEventListener('click', function(e) {
            e.stopPropagation(); // Don't trigger the version loading
            
            const versionNumber = item.dataset.versionNumber;
            showDiffModal(versionNumber);
        });
        
        // Add the button to the item
        const versionInfo = item.querySelector('.version-info');
        if (versionInfo) {
            versionInfo.appendChild(compareBtn);
        } else {
            // No .version-info div, just append to the item
            item.appendChild(compareBtn);
        }
    });
}

/**
 * Show the diff modal for comparing versions
 * 
 * @param {string} fromVersion - The version number to compare from (optional)
 */
function showDiffModal(fromVersion = null) {
    // Get all available versions from the versionList
    const versions = [];
    document.querySelectorAll('#versionList li').forEach(item => {
        if (item.dataset.versionNumber) {
            versions.push({
                number: item.dataset.versionNumber,
                label: `v${item.dataset.versionNumber} - ${item.querySelector('.version-date').innerText}`
            });
        }
    });
    
    // Sort versions by number (descending)
    versions.sort((a, b) => b.number - a.number);
    
    // Populate the from version dropdown
    const fromSelect = document.getElementById('diffFromVersion');
    fromSelect.innerHTML = '';
    
    versions.forEach(version => {
        const option = document.createElement('option');
        option.value = version.number;
        option.innerText = version.label;
        
        // Select the provided fromVersion if specified
        if (fromVersion && version.number === fromVersion) {
            option.selected = true;
        }
        
        fromSelect.appendChild(option);
    });
    
    // Populate the to version dropdown
    const toSelect = document.getElementById('diffToVersion');
    toSelect.innerHTML = '';
    
    versions.forEach(version => {
        const option = document.createElement('option');
        option.value = version.number;
        option.innerText = version.label;
        
        // Select the newest version by default (first one since we sorted desc)
        if (version === versions[0]) {
            option.selected = true;
        }
        
        toSelect.appendChild(option);
    });
    
    // Show the modal
    document.getElementById('diffModal').classList.add('show');
    document.getElementById('diffModalBackdrop').style.display = 'block';
    
    // Load the diff if versions are selected
    const selectedFromVersion = fromSelect.value;
    const selectedToVersion = toSelect.value;
    
    if (selectedFromVersion && selectedToVersion) {
        loadDiff(selectedFromVersion, selectedToVersion);
    }
}

/**
 * Load and display the diff between two versions
 * 
 * @param {string} fromVersion - The version number to compare from
 * @param {string} toVersion - The version number to compare to
 */
function loadDiff(fromVersion, toVersion) {
    // Show loading indicator
    const diffContent = document.getElementById('diffContent');
    diffContent.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading diff...</p>
        </div>
    `;
    
    // Get the format from the toggle
    const format = document.getElementById('diffFormatToggle').checked ? 'split' : 'unified';
    
    // Make request to the API
    const url = `/ontology-editor/api/versions/${currentOntologyId}/diff?from=${fromVersion}&to=${toVersion}&format=${format}`;
    
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load diff');
            }
            return response.json();
        })
        .then(data => {
            // Display the diff
            if (format === 'unified') {
                // For unified diff, we need to format it as code
                diffContent.innerHTML = `
                    <pre class="diff-unified">${escapeHtml(data.diff)}</pre>
                `;
            } else {
                // For split diff, it's already HTML
                diffContent.innerHTML = data.diff;
            }
            
            // Update metadata
            document.getElementById('diffFromInfo').innerText = 
                `Version ${data.from_version.number} - ${formatDate(data.from_version.created_at)}`;
                
            document.getElementById('diffToInfo').innerText = 
                `Version ${data.to_version.number} - ${formatDate(data.to_version.created_at)}`;
                
            // Add commit messages if available
            if (data.from_version.commit_message) {
                document.getElementById('diffFromCommit').innerText = data.from_version.commit_message;
                document.getElementById('diffFromCommitSection').style.display = 'block';
            } else {
                document.getElementById('diffFromCommitSection').style.display = 'none';
            }
            
            if (data.to_version.commit_message) {
                document.getElementById('diffToCommit').innerText = data.to_version.commit_message;
                document.getElementById('diffToCommitSection').style.display = 'block';
            } else {
                document.getElementById('diffToCommitSection').style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Error loading diff:', error);
            diffContent.innerHTML = `
                <div class="alert alert-danger">
                    Error loading diff: ${error.message}
                </div>
            `;
        });
}

/**
 * Format a date string
 * 
 * @param {string} dateStr - ISO date string
 * @returns {string} - Formatted date
 */
function formatDate(dateStr) {
    if (!dateStr) return 'Unknown date';
    
    const date = new Date(dateStr);
    return date.toLocaleString();
}

/**
 * Escape HTML special characters
 * 
 * @param {string} html - String that might contain HTML
 * @returns {string} - Escaped string
 */
function escapeHtml(html) {
    const div = document.createElement('div');
    div.textContent = html;
    return div.innerHTML;
}
