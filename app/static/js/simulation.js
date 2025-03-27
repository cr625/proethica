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
                messages: [],
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
                sessionId: null,
                scenarioId: parseInt(simulationAppElement.getAttribute('data-scenario-id') || '0')
            };
        },
        created() {
            // Initialize conversation
            this.initializeConversation();
            // Get prompt options
            this.getPromptOptions();
        },
        methods: {
            initializeConversation() {
                // Initialize with a simple welcome message
                this.messages = [
                    {
                        role: 'assistant',
                        content: 'Click "Start Simulation" to begin the scenario.'
                    }
                ];
            },
            sendMessage() {
                if (!this.inputEnabled || !this.userInput.trim() || this.isProcessing) return;

                // Add user message to conversation
                this.messages.push({ role: 'user', content: this.userInput });

                // Clear input and disable it while processing
                const userMessage = this.userInput;
                this.userInput = '';
                this.inputEnabled = true;
                this.isProcessing = true;
                this.promptOptions = [];

                // Scroll to bottom
                this.scrollToBottom();

                // Simulate API call with timeout
                setTimeout(() => {
                    // Add assistant response to conversation
                    this.messages.push({
                        role: 'assistant',
                        content: 'I understand your question about "' + userMessage + '". In this simulation, you can explore the scenario timeline and make decisions at key points. Would you like to know more about a specific event or character?'
                    });

                    // Re-enable input
                    this.isProcessing = false;
                    this.getPromptOptions();
                    this.scrollToBottom();
                }, 1000);
            },
            selectPromptOption(option) {
                // If the option is "Start Simulation" or "Advance Simulation", call advanceSimulation
                if (option.text === 'Start Simulation' || option.text === 'Advance Simulation') {
                    this.advanceSimulation();
                    return;
                }

                // Otherwise, handle as a decision option
                this.messages.push({ role: 'user', content: option.text });

                // Clear prompt options and disable input while processing
                this.promptOptions = [];
                this.inputEnabled = false;
                this.isProcessing = true;

                // Scroll to bottom
                this.scrollToBottom();

                // Make decision API call
                axios.post('/simulation/api/decide', {
                    scenario_id: this.scenarioId,
                    session_id: this.sessionId,
                    decision_index: option.id
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

                        // Add assistant response to conversation
                        this.messages.push({
                            role: 'assistant',
                            content: response.data.message
                        });

                        // Update simulation state
                        this.simulationState.currentStep++;

                        // Check if we've reached the end of the simulation
                        if (this.simulationState.currentStep >= this.simulationState.totalSteps) {
                            this.simulationState.completed = true;
                        }

                        this.simulationState.isDecisionPoint = response.data.is_decision;

                        // Update prompt options
                        if (response.data.options && response.data.options.length > 0) {
                            this.promptOptions = response.data.options;
                        } else {
                            this.getPromptOptions();
                        }
                    } else {
                        // Show error message
                        this.messages.push({
                            role: 'assistant',
                            content: 'Error: ' + response.data.message
                        });
                    }

                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                    this.scrollToBottom();

                    // Scroll to the bottom of the page to keep the Simulation State card in view
                    window.scrollTo(0, document.body.scrollHeight);
                })
                .catch((error) => {
                    // Show error message
                    this.messages.push({
                        role: 'assistant',
                        content: 'Error: ' + (error.response ? error.response.data.message : error.message)
                    });

                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                    this.scrollToBottom();
                });
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

                // Check if the current step is a decision
                if (currentStep > 0 && currentStep <= timelineItems.length) {
                    const currentItem = timelineItems[currentStep - 1];
                    const isDecision = currentItem.querySelector('.badge.bg-warning') !== null;

                    if (isDecision) {
                        // If it's a decision, get the options
                        const optionElements = currentItem.querySelectorAll('.list-group-item');
                        const options = [];

                        optionElements.forEach((element, index) => {
                            options.push({
                                id: index + 1,
                                text: element.textContent.trim().replace('Selected', '').trim()
                            });
                        });

                        if (options.length > 0) {
                            // Set isDecisionPoint flag to true
                            this.simulationState.isDecisionPoint = true;
                            this.promptOptions = options;
                            return;
                        }
                    }

                    // Not a decision point
                    this.simulationState.isDecisionPoint = false;
                }

                // Default to "Advance Simulation" if not at a decision point
                this.promptOptions = [
                    {
                        id: 1,
                        text: 'Advance Simulation'
                    }
                ];
            },
            advanceSimulation() {
                // Start or advance the simulation
                const endpoint = this.simulationState.currentStep === 0 ?
                    '/simulation/api/start' : '/simulation/api/advance';

                // Disable input while processing
                this.inputEnabled = false;
                this.isProcessing = true;

                // Show thinking message
                this.messages.push({
                    role: 'assistant',
                    content: 'Processing...'
                });

                this.scrollToBottom();

                axios.post(endpoint, {
                    scenario_id: this.scenarioId,
                    session_id: this.sessionId
                })
                .then((response) => {
                    if (response.data.status === 'success') {
                        // Remove thinking message
                        this.messages.pop();

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

                        // Check if we've reached the end of the simulation
                        if (this.simulationState.currentStep >= this.simulationState.totalSteps) {
                            this.simulationState.completed = true;
                        }

                        // Update decision point flag
                        this.simulationState.isDecisionPoint = response.data.is_decision;

                        // Add message to conversation
                        this.messages.push({
                            role: 'assistant',
                            content: response.data.message
                        });

                        // Update prompt options
                        if (response.data.options && response.data.options.length > 0) {
                            this.promptOptions = response.data.options;
                        } else {
                            this.getPromptOptions();
                        }

                        this.scrollToBottom();

                        // Scroll to the bottom of the page to show the simulation state
                        window.scrollTo(0, document.body.scrollHeight);
                    } else {
                        // Show error message
                        this.messages.pop(); // Remove thinking message
                        this.messages.push({
                            role: 'assistant',
                            content: 'Error: ' + response.data.message
                        });
                        this.scrollToBottom();
                    }

                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                })
                .catch((error) => {
                    // Show error message
                    this.messages.pop(); // Remove thinking message
                    this.messages.push({
                        role: 'assistant',
                        content: 'Error: ' + (error.response ? error.response.data.message : error.message)
                    });
                    this.scrollToBottom();

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

                // Show thinking message
                this.messages = [{
                    role: 'assistant',
                    content: 'Resetting simulation...'
                }];

                // Clear status messages
                this.statusMessages = [];

                this.scrollToBottom();

                axios.post('/simulation/api/reset', {
                    scenario_id: this.scenarioId
                })
                .then((response) => {
                    if (response.data.status === 'success') {
                        // Update simulation state
                        this.simulationState.currentStep = 0;
                        this.simulationState.completed = false;
                        this.simulationState.isDecisionPoint = false;
                        this.sessionId = response.data.session_id;

                        // Update messages
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
                        this.messages = [{
                            role: 'assistant',
                            content: 'Error resetting simulation: ' + response.data.message
                        }];
                    }

                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                    this.scrollToBottom();

                    // Hide the modal
                    const resetModal = bootstrap.Modal.getInstance(document.getElementById('resetConfirmationModal'));
                    resetModal.hide();
                })
                .catch((error) => {
                    // Show error message
                    this.messages = [{
                        role: 'assistant',
                        content: 'Error resetting simulation: ' + (error.response ? error.response.data.message : error.message)
                    }];

                    // Re-enable input
                    this.inputEnabled = true;
                    this.isProcessing = false;
                    this.scrollToBottom();

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
