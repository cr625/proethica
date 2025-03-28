// Count the number of timeline items (will be set from the template)
let timelineItemCount = 10;

// Initialize the Vue application
document.addEventListener('DOMContentLoaded', function() {
    // This function will be called when the DOM is fully loaded
    
    // Get the timeline item count from the data attribute
    const simulationAppElement = document.getElementById('simulation-app');
    if (simulationAppElement) {
        timelineItemCount = parseInt(simulationAppElement.getAttribute('data-timeline-count') || '10');
    }

    const app = Vue.createApp({
        data() {
            return {
                messages: [], // Keep for compatibility
                userInput: '',
                inputEnabled: true,
                promptOptions: [],
                isProcessing: false,
                statusMessages: [],
                simulationState: {
                    currentStep: 0,
                    totalSteps: timelineItemCount,
                    completed: false,
                    isDecisionPoint: false
                },
                timelineItemStates: {}, // Store states for each timeline item (active, analyzed, etc.)
                sessionId: null,
                scenarioId: parseInt(simulationAppElement.getAttribute('data-scenario-id') || '0')
            };
        },
        created() {
            // Initialize conversation
            this.initializeConversation();
            // Initialize timeline item states
            this.initializeTimelineItemStates();
            // Get prompt options
            this.getPromptOptions();
        },
        methods: {
            initializeConversation() {
                // Keep this for compatibility
                this.messages = [
                    {
                        role: 'assistant',
                        content: 'Click "Start Simulation" to begin the scenario.'
                    }
                ];
            },
            
            initializeTimelineItemStates() {
                // Initialize the timeline item states object
                for (let i = 0; i < timelineItemCount; i++) {
                    this.timelineItemStates[i] = {
                        active: false,
                        isDecision: false,
                        analyzed: false,
                        options: [],
                        llmAnalysis: '',
                        selection: null
                    };
                }
            },
            
            // Timeline Item Management Methods
            isTimelineItemActive(index) {
                return this.timelineItemStates[index] && this.timelineItemStates[index].active === true;
            },
            
            isTimelineItemAnalyzed(index) {
                return this.timelineItemStates[index] && this.timelineItemStates[index].analyzed;
            },
            
            hasTimelineItemSelection(index) {
                return this.timelineItemStates[index] && this.timelineItemStates[index].selection !== null;
            },
            
            getLlmAnalysisFor(index) {
                return this.timelineItemStates[index] ? this.timelineItemStates[index].llmAnalysis : '';
            },
            
            getOptionsForTimelineItem(index) {
                return this.timelineItemStates[index] ? this.timelineItemStates[index].options : [];
            },
            
            getSelectionForTimelineItem(index) {
                return this.timelineItemStates[index] && this.timelineItemStates[index].selection ? 
                    this.timelineItemStates[index].selection : '';
            },
            
            isDecisionPoint(index) {
                return this.timelineItemStates[index] && this.timelineItemStates[index].isDecision;
            },
            
            advanceFromTimelineItem(index) {
                const isDecision = this.isDecisionPoint(index);
                const hasAnalysis = this.isTimelineItemAnalyzed(index);
                const hasSelection = this.hasTimelineItemSelection(index);
                
                // For decision points, we handle them in stages:
                if (isDecision) {
                    // Stage 1: If the decision hasn't been analyzed yet, analyze it but don't advance yet
                    if (!hasAnalysis) {
                        console.log("Decision point - initiating analysis");
                        this.analyzeDecision(index);
                        return;
                    }
                    // Stage 2: If analyzed but no selection yet, keep the item active for user to select
                    else if (!hasSelection) {
                        console.log("Decision point - waiting for user selection");
                        // Don't do anything - user needs to make a selection
                        return;
                    }
                    // Stage 3: Has analysis and selection, now we can advance
                    else {
                        console.log("Decision point - selection made, advancing");
                        // Mark this item as no longer active
                        if (this.timelineItemStates[index]) {
                            this.timelineItemStates[index].active = false;
                        }
                        
                        // Advance to the next step
                        this.advanceSimulation();
                    }
                } 
                // For non-decision items, simply advance
                else {
                    console.log("Regular item - advancing");
                    // Mark this item as no longer active
                    if (this.timelineItemStates[index]) {
                        this.timelineItemStates[index].active = false;
                    }
                    
                    // Advance to the next step
                    this.advanceSimulation();
                }
            },
            
            analyzeDecision(index) {
                // Disable input while processing
                this.inputEnabled = false;
                this.isProcessing = true;
                
                // Show processing indicator
                this.$nextTick(() => {
                    const timelineItems = document.querySelectorAll('.timeline-item');
                    if (timelineItems[index]) {
                        timelineItems[index].scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                });
                
                // Make API call to analyze decision
                axios.post('/simulation/api/analyze', {
                    scenario_id: this.scenarioId,
                    session_id: this.sessionId,
                    timeline_index: index
                })
                .then((response) => {
                    if (response.data.status === 'success') {
                        // Update the timeline item state with analysis
                        if (this.timelineItemStates[index]) {
                            this.timelineItemStates[index].analyzed = true;
                            this.timelineItemStates[index].llmAnalysis = response.data.analysis || 'Decision analyzed.';
                            
                            // Set options for this decision
                            if (response.data.options && response.data.options.length > 0) {
                                this.timelineItemStates[index].options = response.data.options;
                            } else {
                                // Try to get options from the timeline item directly
                                const timelineItems = document.querySelectorAll('.timeline-item');
                                if (timelineItems[index]) {
                                    const optionElements = timelineItems[index].querySelectorAll('.list-group-item');
                                    const options = [];
                                    
                                    optionElements.forEach((element, idx) => {
                                        options.push({
                                            id: idx + 1,
                                            text: element.textContent.trim().replace('Selected', '').trim()
                                        });
                                    });
                                    
                                    if (options.length > 0) {
                                        this.timelineItemStates[index].options = options;
                                    }
                                }
                            }
                        }
                    } else {
                        // Show error message
                        console.error('Error analyzing decision:', response.data.message);
                        
                        // Set a default analysis message
                        if (this.timelineItemStates[index]) {
                            this.timelineItemStates[index].analyzed = true;
                            this.timelineItemStates[index].llmAnalysis = 'Error analyzing decision. Please make your choice.';
                        }
                    }
                    
                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                    
                    // Scroll to the timeline item to ensure it's visible
                    this.$nextTick(() => {
                        const timelineItems = document.querySelectorAll('.timeline-item');
                        if (timelineItems[index]) {
                            timelineItems[index].scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    });
                })
                .catch((error) => {
                    console.error('Error analyzing decision:', error);
                    
                    // Set a default analysis message
                    if (this.timelineItemStates[index]) {
                        this.timelineItemStates[index].analyzed = true;
                        this.timelineItemStates[index].llmAnalysis = 'Error analyzing decision. Please make your choice.';
                    }
                    
                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                });
            },
            
            selectDecisionOption(index, option) {
                // Update the timeline item state with the selection
                if (this.timelineItemStates[index]) {
                    this.timelineItemStates[index].selection = option.text;
                }
                
                // Make the API call to record the decision
                this.inputEnabled = false;
                this.isProcessing = true;
                
                axios.post('/simulation/api/decide', {
                    scenario_id: this.scenarioId,
                    session_id: this.sessionId,
                    decision_index: option.id
                })
                .then((response) => {
                    if (response.data.status === 'success') {
                        // Add new status messages if available
                        if (response.data.status_messages && response.data.status_messages.length > 0) {
                            const filteredMessages = response.data.status_messages.filter(message => 
                                !message.includes("Initialized Agent Orchestrator")
                            );
                            
                            if (filteredMessages.length > 0) {
                                this.statusMessages = [...filteredMessages, ...this.statusMessages];
                                this.scrollStatusToTop();
                            }
                        }
                        
                        // Update the timeline item state with any additional data from the response
                        if (this.timelineItemStates[index]) {
                            // If there's additional information about the selection result, add it
                            if (response.data.selection_result) {
                                this.timelineItemStates[index].selectionResult = response.data.selection_result;
                            }
                        }
                    } else {
                        // Show error message
                        console.error('Error recording decision:', response.data.message);
                    }
                    
                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                    
                    // Scroll to ensure the item is visible
                    this.$nextTick(() => {
                        const timelineItems = document.querySelectorAll('.timeline-item');
                        if (timelineItems[index]) {
                            timelineItems[index].scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    });
                })
                .catch((error) => {
                    console.error('Error recording decision:', error);
                    
                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                });
            },
            // Keep sendMessage for compatibility, but it's not used in the new interface
            sendMessage() {
                if (!this.inputEnabled || !this.userInput.trim() || this.isProcessing) return;

                const userMessage = this.userInput;
                this.userInput = '';
                
                // Show a message that direct messages aren't used in the timeline view
                alert('Please use the timeline interface to interact with the simulation.');
            },
            selectPromptOption(option) {
                // Only handle "Start Simulation" option in the new interface
                if (option.text === 'Start Simulation') {
                    this.advanceSimulation();
                    return;
                }
                
                // For backward compatibility (this shouldn't be called in the new interface)
                console.warn('Deprecated: selectPromptOption called for a non-start option');
            },
            getPromptOptions() {
                // Check if we're at a decision point in the timeline
                const currentStep = this.simulationState.currentStep;

                // If simulation hasn't started yet
                if (currentStep === 0) {
                    this.promptOptions = [
                        {
                            id: 1,
                            text: 'Start Simulation'
                        }
                    ];
                    return;
                }

                // Get all timeline items
                const timelineItems = document.querySelectorAll('.timeline-item');

                // If we've reached the end of the simulation
                if (currentStep >= this.simulationState.totalSteps) {
                    this.simulationState.completed = true;
                    this.promptOptions = [
                        {
                            id: 1,
                            text: 'Simulation Complete'
                        }
                    ];
                    return;
                }

                // In the consolidated interface, we'll only use the "Start Simulation" button
                // Other interactions happen directly in the timeline
                this.promptOptions = [];
            },
            advanceSimulation() {
                // Start or advance the simulation
                const endpoint = this.simulationState.currentStep === 0 ?
                    '/simulation/api/start' : '/simulation/api/advance';

                // Disable input while processing
                this.inputEnabled = false;
                this.isProcessing = true;

                axios.post(endpoint, {
                    scenario_id: this.scenarioId,
                    session_id: this.sessionId
                })
                .then((response) => {
                    if (response.data.status === 'success') {
                        // Add new status messages if available
                        if (response.data.status_messages && response.data.status_messages.length > 0) {
                            // Filter out duplicate initialization messages
                            const filteredMessages = response.data.status_messages.filter(message => 
                                !message.includes("Initialized Agent Orchestrator")
                            );
                            
                            // Only add messages if there are any after filtering
                            if (filteredMessages.length > 0) {
                                // Add new messages to the beginning of the array
                                this.statusMessages = [...filteredMessages, ...this.statusMessages];
                                // Scroll status container to top to show newest messages
                                this.scrollStatusToTop();
                            }
                        }

                        // Update simulation state
                        if (this.simulationState.currentStep === 0) {
                            this.simulationState.currentStep = 1;
                            this.sessionId = response.data.session_id;
                        } else {
                            this.simulationState.currentStep++;
                        }
                        
                        // The current active item index (0-based)
                        const currentActiveIndex = this.simulationState.currentStep - 1;
                        
                        // Deactivate all timeline items
                        for (let i = 0; i < timelineItemCount; i++) {
                            if (this.timelineItemStates[i]) {
                                this.timelineItemStates[i].active = false;
                            }
                        }
                        
                        // Activate only the current item
                        if (this.timelineItemStates[currentActiveIndex]) {
                            this.timelineItemStates[currentActiveIndex].active = true;
                            
                            // Check if this is a decision point
                            const isDecision = response.data.is_decision || false;
                            this.timelineItemStates[currentActiveIndex].isDecision = isDecision;
                            
                            // If it's a decision, setup the initial state before analysis
                            if (isDecision) {
                                this.timelineItemStates[currentActiveIndex].analyzed = false;
                            }
                        }

                        // Check if we've reached the end of the simulation
                        if (this.simulationState.currentStep >= this.simulationState.totalSteps) {
                            this.simulationState.completed = true;
                        }

                        // For compatibility, keep updating the decision point flag and message store
                        this.simulationState.isDecisionPoint = response.data.is_decision;
                        
                        let message = response.data.message;
                        
                        // Replace event and action messages with simpler acknowledgments
                        if (message.startsWith('Event:')) {
                            message = 'Event registered';
                        } else if (message.startsWith('Action:')) {
                            message = 'Action registered';
                        }
                        
                        // Store last message for compatibility
                        this.messages.push({
                            role: 'assistant',
                            content: message
                        });

                        // Always scroll to the most recently added timeline item
                        this.$nextTick(() => {
                            // Get all visible items
                            const visibleItems = Array.from(document.querySelectorAll('.timeline-item[style*="display: block"]'));
                            if (visibleItems.length > 0) {
                                // Scroll to the last visible item (most recently added)
                                const lastItem = visibleItems[visibleItems.length - 1];
                                lastItem.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                
                                // Scroll a bit further to ensure the advance button is visible if present
                                const advanceButton = lastItem.querySelector('.advance-button');
                                if (advanceButton) {
                                    window.scrollBy({
                                        top: 100,
                                        behavior: 'smooth'
                                    });
                                }
                            }
                        });
                    } else {
                        // Show error message
                        console.error('Error advancing simulation:', response.data.message);
                        alert('Error: ' + response.data.message);
                    }

                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                })
                .catch((error) => {
                    // Show error message
                    console.error('Error advancing simulation:', error);
                    alert('Error: ' + (error.response ? error.response.data.message : error.message));

                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                });
            },
            showResetModal() {
                // Show the reset confirmation modal
                const resetModal = new bootstrap.Modal(document.getElementById('resetConfirmationModal'));
                resetModal.show();
            },
            confirmReset() {
                // Reset conversation and simulation state after confirmation
                this.inputEnabled = false;
                this.isProcessing = true;

                // Clear status messages
                this.statusMessages = [];

                axios.post('/simulation/api/reset', {
                    scenario_id: this.scenarioId
                })
                .then((response) => {
                    if (response.data.status === 'success') {
                        // Reset simulation state
                        this.simulationState.currentStep = 0;
                        this.simulationState.completed = false;
                        this.simulationState.isDecisionPoint = false;
                        this.sessionId = response.data.session_id;
                        
                        // Reset timeline item states
                        this.initializeTimelineItemStates();

                        // For compatibility
                        this.messages = [{
                            role: 'assistant',
                            content: response.data.message
                        }];

                        // Update prompt options
                        if (response.data.options && response.data.options.length > 0) {
                            this.promptOptions = response.data.options;
                        } else {
                            this.getPromptOptions();
                        }
                    } else {
                        // Show error message
                        alert('Error resetting simulation: ' + response.data.message);
                    }

                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;

                    // Hide the modal
                    const resetModal = bootstrap.Modal.getInstance(document.getElementById('resetConfirmationModal'));
                    resetModal.hide();
                })
                .catch((error) => {
                    // Show error message
                    alert('Error resetting simulation: ' + (error.response ? error.response.data.message : error.message));

                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;

                    // Hide the modal
                    const resetModal = bootstrap.Modal.getInstance(document.getElementById('resetConfirmationModal'));
                    resetModal.hide();
                });
            },
            scrollToBottom() {
                // Scroll to bottom of conversation when new messages are added
                this.$nextTick(() => {
                    const container = this.$refs.conversation;
                    if (container) {
                        container.scrollTop = container.scrollHeight;
                    }
                });
            },
            scrollStatusToTop() {
                // Scroll status container to ensure the latest entry (at the top) is visible
                this.$nextTick(() => {
                    const statusContainer = document.querySelector('.status-container');
                    if (statusContainer) {
                        // Scroll to top to show the newest messages
                        statusContainer.scrollTop = 0;
                        
                        // Add a small animation to highlight the newest message
                        const newestMessage = statusContainer.querySelector('.status-message:first-child');
                        if (newestMessage) {
                            // Add a highlight class
                            newestMessage.classList.add('status-message-highlight');
                            
                            // Remove the highlight class after animation completes
                            setTimeout(() => {
                                newestMessage.classList.remove('status-message-highlight');
                            }, 1000);
                        }
                    }
                });
            }
        },
        updated() {
            // Scroll to bottom of conversation when new messages are added
            this.scrollToBottom();
            
            // Scroll status container to top when component is updated
            if (this.statusMessages.length > 0) {
                this.scrollStatusToTop();
            }
        }
    }).mount('#simulation-app');
});
