// Vue.js App for Agent Case Creation
const AgentCaseCreation = {
    data() {
        return {
            worldId: document.getElementById('worldId').value,
            selectedConcepts: {},
            conversationHistory: [],
            isProcessing: false,
            ontologyCollapsed: false,
            expandedCategories: {},
            loadedConcepts: {},
            conversationId: null,
            canGenerateCase: false
        }
    },
    mounted() {
        this.initializeEventListeners();
        this.updateSelectedSummary();
    },
    methods: {
        initializeEventListeners() {
            // No category checkboxes anymore - concepts are selected individually
            
            // Panel toggle
            const ontologyToggle = document.getElementById('ontologyToggle');
            if (ontologyToggle) {
                ontologyToggle.addEventListener('click', this.toggleOntologyPanel);
            }
            
            // Input handling
            const userInput = document.getElementById('userInput');
            const sendButton = document.getElementById('sendMessage');
            
            if (userInput) {
                userInput.addEventListener('input', this.handleInputChange);
                userInput.addEventListener('keydown', this.handleKeyDown);
            }
            if (sendButton) {
                sendButton.addEventListener('click', this.sendMessage);
            }
            
            // Suggestion clicks
            document.addEventListener('click', (e) => {
                if (e.target.classList.contains('suggestion-item')) {
                    userInput.value = e.target.dataset.prompt;
                    this.handleInputChange();
                }
            });
            
            // Utility buttons
            const selectAllBtn = document.getElementById('selectAllCategories');
            const clearCategoriesBtn = document.getElementById('clearCategories');
            const clearConversationBtn = document.getElementById('clearConversation');
            const generateCaseBtn = document.getElementById('generateCase');
            
            if (selectAllBtn) {
                selectAllBtn.addEventListener('click', this.selectAllCategories);
            }
            if (clearCategoriesBtn) {
                clearCategoriesBtn.addEventListener('click', this.clearCategories);
            }
            if (clearConversationBtn) {
                clearConversationBtn.addEventListener('click', this.clearConversation);
            }
            if (generateCaseBtn) {
                generateCaseBtn.addEventListener('click', this.generateCase);
            }
        },
        
        
        updateSelectedSummary() {
            const summary = document.getElementById('selectedSummary');
            const count = document.getElementById('selectedCount');
            const conceptCount = document.getElementById('selectedConceptCount');
            
            const totalConcepts = Object.values(this.selectedConcepts).reduce((sum, concepts) => sum + concepts.length, 0);
            const categoriesWithConcepts = Object.keys(this.selectedConcepts).filter(cat => this.selectedConcepts[cat].length > 0).length;
            
            count.textContent = categoriesWithConcepts;
            conceptCount.textContent = totalConcepts;
            
            if (totalConcepts > 0) {
                summary.style.display = 'block';
                this.updateSelectedDetails();
            } else {
                summary.style.display = 'none';
            }
        },
        
        updateSelectedDetails() {
            const details = document.getElementById('selectedDetails');
            const conceptsList = document.getElementById('selectedConceptsList');
            
            if (Object.keys(this.selectedConcepts).length > 0) {
                let html = '';
                for (const [category, concepts] of Object.entries(this.selectedConcepts)) {
                    if (concepts.length > 0) {
                        html += `<strong>${category}:</strong> ${concepts.join(', ')}<br>`;
                    }
                }
                conceptsList.innerHTML = html;
                details.style.display = 'block';
            } else {
                details.style.display = 'none';
            }
        },
        
        selectAllCategories() {
            // Expand all categories and select all their concepts
            const categories = document.querySelectorAll('.category-header');
            categories.forEach(async (header) => {
                const categoryName = header.dataset.category;
                // Expand if not already expanded
                if (!this.expandedCategories[categoryName]) {
                    await this.toggleCategoryExpansion(categoryName);
                }
                // Wait for concepts to load, then select all
                setTimeout(() => {
                    const conceptCheckboxes = document.querySelectorAll(`input[data-category="${categoryName}"].concept-select`);
                    conceptCheckboxes.forEach(checkbox => {
                        checkbox.checked = true;
                        this.handleConceptChange(categoryName, checkbox.value, true);
                    });
                }, 500);
            });
        },
        
        clearCategories() {
            // Clear all selected concepts
            document.querySelectorAll('.concept-select').forEach(checkbox => {
                checkbox.checked = false;
            });
            this.selectedConcepts = {};
            // Remove visual feedback from all category headers
            document.querySelectorAll('.category-header').forEach(header => {
                header.classList.remove('has-selected-concepts');
                const conceptCount = header.querySelector('.concept-count');
                conceptCount.classList.remove('has-selections');
                if (conceptCount.dataset.originalCount) {
                    conceptCount.textContent = conceptCount.dataset.originalCount;
                }
            });
            this.updateSelectedSummary();
        },
        
        async toggleCategoryExpansion(categoryName) {
            const header = document.querySelector(`[data-category="${categoryName}"]`);
            const content = document.getElementById(`category_content_${categoryName}`);
            const icon = header.querySelector('.category-expand-icon');
            
            if (this.expandedCategories[categoryName]) {
                // Collapse
                content.classList.remove('expanded');
                header.classList.remove('expanded');
                icon.classList.remove('bi-chevron-down');
                icon.classList.add('bi-chevron-right');
                this.expandedCategories[categoryName] = false;
            } else {
                // Expand
                content.classList.add('expanded');
                header.classList.add('expanded');
                icon.classList.remove('bi-chevron-right');
                icon.classList.add('bi-chevron-down');
                this.expandedCategories[categoryName] = true;
                
                // Load concepts if not already loaded
                if (!this.loadedConcepts[categoryName]) {
                    await this.loadCategoryConcepts(categoryName);
                }
            }
        },
        
        async loadCategoryConcepts(categoryName) {
            const conceptsContainer = document.getElementById(`concepts_${categoryName}`);
            
            try {
                const response = await fetch(`/cases/new/agent/concepts/${categoryName}?world_id=${this.worldId}`);
                const result = await response.json();
                
                if (result.success) {
                    this.renderConcepts(categoryName, result.concepts);
                    this.loadedConcepts[categoryName] = true;
                } else {
                    conceptsContainer.innerHTML = `
                        <div class="text-center text-muted">
                            <i class="bi bi-exclamation-triangle"></i>
                            <small class="d-block">Error loading concepts</small>
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Error loading concepts:', error);
                conceptsContainer.innerHTML = `
                    <div class="text-center text-muted">
                        <i class="bi bi-wifi-off"></i>
                        <small class="d-block">Connection error</small>
                    </div>
                `;
            }
        },
        
        renderConcepts(categoryName, concepts) {
            const conceptsContainer = document.getElementById(`concepts_${categoryName}`);
            
            if (!concepts || concepts.length === 0) {
                conceptsContainer.innerHTML = `
                    <div class="text-center text-muted">
                        <i class="bi bi-inbox"></i>
                        <small class="d-block">No concepts available</small>
                    </div>
                `;
                return;
            }
            
            let html = '';
            concepts.forEach(concept => {
                const conceptName = concept.label || concept.name || concept;
                const conceptDescription = concept.description || '';
                const conceptId = `concept_${categoryName}_${conceptName.replace(/[^a-zA-Z0-9]/g, '_')}`;
                
                html += `
                    <div class="concept-item">
                        <input type="checkbox" 
                               id="${conceptId}"
                               value="${conceptName}"
                               class="concept-select"
                               data-category="${categoryName}"
                               onchange="handleConceptChange('${categoryName}', '${conceptName}', this.checked)">
                        <label for="${conceptId}">${conceptName}</label>
                    </div>
                `;
                
                if (conceptDescription) {
                    html += `<div class="concept-description">${conceptDescription}</div>`;
                }
            });
            
            conceptsContainer.innerHTML = html;
        },
        
        handleConceptChange(categoryName, conceptName, isSelected) {
            if (!this.selectedConcepts[categoryName]) {
                this.selectedConcepts[categoryName] = [];
            }
            
            if (isSelected) {
                if (!this.selectedConcepts[categoryName].includes(conceptName)) {
                    this.selectedConcepts[categoryName].push(conceptName);
                }
            } else {
                this.selectedConcepts[categoryName] = this.selectedConcepts[categoryName].filter(name => name !== conceptName);
            }
            
            // Update visual feedback
            this.updateCategoryVisualFeedback(categoryName);
            this.updateSelectedSummary();
        },
        
        updateCategoryVisualFeedback(categoryName) {
            const header = document.querySelector(`[data-category="${categoryName}"]`);
            const conceptCount = header.querySelector('.concept-count');
            const hasSelectedConcepts = this.selectedConcepts[categoryName] && this.selectedConcepts[categoryName].length > 0;
            
            if (hasSelectedConcepts) {
                header.classList.add('has-selected-concepts');
                conceptCount.classList.add('has-selections');
                conceptCount.textContent = `${conceptCount.dataset.originalCount || conceptCount.textContent} (${this.selectedConcepts[categoryName].length} selected)`;
            } else {
                header.classList.remove('has-selected-concepts');
                conceptCount.classList.remove('has-selections');
                conceptCount.textContent = conceptCount.dataset.originalCount || conceptCount.textContent.split(' (')[0];
            }
            
            // Store original count if not already stored
            if (!conceptCount.dataset.originalCount) {
                conceptCount.dataset.originalCount = conceptCount.textContent.split(' (')[0];
            }
        },
        
        toggleOntologyPanel() {
            const panel = document.getElementById('ontologyPanel');
            const toggle = document.getElementById('ontologyToggle');
            
            this.ontologyCollapsed = !this.ontologyCollapsed;
            
            if (this.ontologyCollapsed) {
                panel.classList.add('collapsed');
                toggle.innerHTML = '<i class="bi bi-chevron-right"></i>';
            } else {
                panel.classList.remove('collapsed');
                toggle.innerHTML = '<i class="bi bi-chevron-left"></i>';
            }
        },
        
        handleInputChange() {
            const input = document.getElementById('userInput');
            const button = document.getElementById('sendMessage');
            
            button.disabled = input.value.trim().length === 0;
        },
        
        handleKeyDown(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        },
        
        async sendMessage() {
            const input = document.getElementById('userInput');
            const message = input.value.trim();
            
            if (!message || this.isProcessing) return;
            
            // Add user message to conversation
            this.addMessage('user', message);
            
            // Clear input and show processing
            input.value = '';
            this.handleInputChange();
            this.showProcessing(true);
            
            try {
                // Send to API
                const response = await fetch('/cases/new/agent/api', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        prompt: message,
                        world_id: this.worldId,
                        selected_categories: Object.keys(this.selectedConcepts).filter(cat => this.selectedConcepts[cat].length > 0),
                        selected_concepts: this.selectedConcepts,
                        conversation_history: this.conversationHistory
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    this.addAgentResponse(result.response);
                } else {
                    this.addMessage('error', result.error || 'An error occurred');
                }
                
            } catch (error) {
                console.error('Error sending message:', error);
                this.addMessage('error', 'Failed to communicate with language model');
            } finally {
                this.showProcessing(false);
            }
        },
        
        addMessage(type, content) {
            const area = document.getElementById('conversationArea');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${type}-message`;
            
            if (type === 'user') {
                messageDiv.innerHTML = `
                    <div class="message-bubble">${this.escapeHtml(content)}</div>
                `;
            } else if (type === 'error') {
                messageDiv.innerHTML = `
                    <div class="message-header">
                        <i class="bi bi-exclamation-triangle text-danger"></i> Error
                    </div>
                    <div class="message-bubble bg-danger text-white">${this.escapeHtml(content)}</div>
                `;
            }
            
            area.appendChild(messageDiv);
            area.scrollTop = area.scrollHeight;
            
            // Add to history
            this.conversationHistory.push({
                type: type,
                content: content,
                timestamp: new Date().toISOString()
            });
            
            // Update case generation capability
            this.updateCaseGenerationStatus();
        },
        
        addAgentResponse(response) {
            const area = document.getElementById('conversationArea');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message agent-message';
            
            let html = `
                <div class="message-header">
                    <i class="bi bi-robot"></i> AI Assistant
                </div>
                <div class="message-bubble">
                    ${this.escapeHtml(response.message)}
            `;
            
            // Add suggestions
            if (response.suggestions && response.suggestions.length > 0) {
                html += '<div class="agent-suggestions"><strong>Suggestions:</strong>';
                response.suggestions.forEach(suggestion => {
                    html += `
                        <div class="suggestion-item" data-prompt="${this.escapeHtml(suggestion.description)}">
                            <strong>${this.escapeHtml(suggestion.title)}</strong><br>
                            <small>${this.escapeHtml(suggestion.description)}</small>
                        </div>
                    `;
                });
                html += '</div>';
            }
            
            // Add next steps
            if (response.next_steps && response.next_steps.length > 0) {
                html += '<div class="next-steps"><strong>Next Steps:</strong>';
                response.next_steps.forEach((step, index) => {
                    html += `
                        <div class="next-step">
                            <div class="step-number">${index + 1}</div>
                            <div>${this.escapeHtml(step)}</div>
                        </div>
                    `;
                });
                html += '</div>';
            }
            
            html += '</div>';
            messageDiv.innerHTML = html;
            
            area.appendChild(messageDiv);
            area.scrollTop = area.scrollHeight;
            
            // Add to history
            this.conversationHistory.push({
                type: 'agent',
                content: response,
                timestamp: new Date().toISOString()
            });
            
            // Update case generation capability
            this.updateCaseGenerationStatus();
        },
        
        showProcessing(show) {
            const indicator = document.getElementById('processingIndicator');
            const button = document.getElementById('sendMessage');
            
            this.isProcessing = show;
            
            if (show) {
                indicator.style.display = 'flex';
                button.disabled = true;
            } else {
                indicator.style.display = 'none';
                this.handleInputChange(); // Re-enable based on input
            }
        },
        
        updateCaseGenerationStatus() {
            const generateBtn = document.getElementById('generateCase');
            
            // Need at least 2 user messages and 1 agent response, plus some ontology selections
            const userMessages = this.conversationHistory.filter(msg => msg.type === 'user').length;
            const agentMessages = this.conversationHistory.filter(msg => msg.type === 'agent').length;
            const hasOntologySelections = Object.values(this.selectedConcepts).some(concepts => concepts.length > 0);
            
            this.canGenerateCase = userMessages >= 2 && agentMessages >= 1 && hasOntologySelections;
            
            if (generateBtn) {
                generateBtn.disabled = !this.canGenerateCase;
                
                if (this.canGenerateCase) {
                    generateBtn.title = 'Generate NSPE-format case from this conversation';
                } else {
                    generateBtn.title = 'Need more conversation and ontology selections to generate case';
                }
            }
        },
        
        async generateCase() {
            if (!this.canGenerateCase) {
                alert('Need more conversation and ontology selections to generate a case.');
                return;
            }
            
            const generateBtn = document.getElementById('generateCase');
            
            try {
                // Show processing state
                generateBtn.disabled = true;
                generateBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Generating...';
                
                // Send conversation and selections to backend for case generation
                const response = await fetch('/cases/new/agent/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        world_id: this.worldId,
                        conversation_history: this.conversationHistory,
                        selected_concepts: this.selectedConcepts,
                        conversation_metadata: {
                            total_messages: this.conversationHistory.length,
                            concept_count: Object.values(this.selectedConcepts).reduce((sum, concepts) => sum + concepts.length, 0),
                            timestamp: new Date().toISOString()
                        }
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Show success message
                    this.addMessage('system', `✅ Case generated successfully! Case ID: ${result.case_id}`);
                    
                    // Redirect to the generated case
                    setTimeout(() => {
                        window.location.href = result.case_url;
                    }, 2000);
                } else {
                    this.addMessage('error', `Failed to generate case: ${result.error || 'Unknown error'}`);
                }
                
            } catch (error) {
                console.error('Error generating case:', error);
                this.addMessage('error', 'Failed to communicate with case generation service');
            } finally {
                // Reset button
                generateBtn.disabled = !this.canGenerateCase;
                generateBtn.innerHTML = '<i class="bi bi-file-earmark-plus"></i> Generate Case';
            }
        },
        
        clearConversation() {
            if (confirm('Clear the entire conversation?')) {
                document.getElementById('conversationArea').innerHTML = `
                    <div class="message agent-message">
                        <div class="message-header">
                            <i class="bi bi-robot"></i> Language Model
                        </div>
                        <div class="message-bubble">
                            <strong>Conversation cleared.</strong> How can I help you create a new case?
                        </div>
                    </div>
                `;
                this.conversationHistory = [];
                this.conversationId = null;
                this.updateCaseGenerationStatus();
            }
        },
        
        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    }
};

// Global functions for onclick handlers  
function toggleCategoryExpansion(categoryName) {
    if (window.agentApp && window.agentApp.toggleCategoryExpansion) {
        window.agentApp.toggleCategoryExpansion(categoryName);
    } else {
        console.error('Agent app not initialized or method not found');
    }
}

function handleConceptChange(categoryName, conceptName, isSelected) {
    if (window.agentApp && window.agentApp.handleConceptChange) {
        window.agentApp.handleConceptChange(categoryName, conceptName, isSelected);
    } else {
        console.error('Agent app not initialized or method not found');
    }
}

// Initialize the Vue app
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing Agent Case Creation interface...');
    
    // Create the app instance properly
    window.agentApp = {};
    
    // Initialize data
    const appData = AgentCaseCreation.data();
    Object.keys(appData).forEach(key => {
        window.agentApp[key] = appData[key];
    });
    
    // Bind methods to the instance with proper 'this' context
    Object.keys(AgentCaseCreation.methods).forEach(methodName => {
        window.agentApp[methodName] = AgentCaseCreation.methods[methodName].bind(window.agentApp);
    });
    
    // Initialize the app
    if (window.agentApp.initializeEventListeners) {
        window.agentApp.initializeEventListeners();
    }
    if (window.agentApp.updateSelectedSummary) {
        window.agentApp.updateSelectedSummary();
    }
    
    console.log('Agent Case Creation interface initialized');
});
