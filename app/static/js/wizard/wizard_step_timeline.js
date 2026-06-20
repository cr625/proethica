let selectedOption = null;
const scenarioId = (window.WIZARD_STEP_TIMELINE || {}).scenarioId;
const currentStep = (window.WIZARD_STEP_TIMELINE || {}).currentStep;

function selectOption(optionId) {
    // Remove previous selection
    document.querySelectorAll('.option-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Add selection to clicked card
    const selectedCard = document.querySelector(`[data-option="${optionId}"]`);
    selectedCard.classList.add('selected');
    
    // Update radio button
    document.getElementById(`option${Array.from(selectedCard.parentNode.children).indexOf(selectedCard) + 1}`).checked = true;
    
    // Enable continue button
    selectedOption = optionId;
    document.getElementById('continueBtn').disabled = false;
}

function submitDecision() {
    if (!selectedOption) {
        alert('Please select an option before continuing.');
        return;
    }
    
    // Submit the choice
    fetch(`/scenarios/${scenarioId}/wizard/step/${currentStep}/choice`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            option_id: selectedOption
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Navigate to next step
            const nextStep = currentStep + 1;
            if (nextStep <= (window.WIZARD_STEP_TIMELINE || {}).totalSteps) {
                window.location.href = `/scenarios/${scenarioId}/wizard/step/${nextStep}`;
            } else {
                window.location.href = `/scenarios/${scenarioId}/wizard/summary`;
            }
        } else {
            alert('Error submitting choice: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error submitting choice. Please try again.');
    });
}

function continueNext() {
    // For event steps, just go to next step
    const nextStep = currentStep + 1;
    if (nextStep <= (window.WIZARD_STEP_TIMELINE || {}).totalSteps) {
        window.location.href = `/scenarios/${scenarioId}/wizard/step/${nextStep}`;
    } else {
        window.location.href = `/scenarios/${scenarioId}/wizard/summary`;
    }
}

function goBack() {
    const prevStep = currentStep - 1;
    if (prevStep >= 1) {
        window.location.href = `/scenarios/${scenarioId}/wizard/step/${prevStep}`;
    }
}

// Handle option card clicks for radio button selection
document.querySelectorAll('.option-card').forEach(card => {
    card.addEventListener('click', function(e) {
        // Don't trigger if clicking on radio button directly
        if (e.target.type !== 'radio') {
            const optionId = this.getAttribute('data-option');
            selectOption(optionId);
        }
    });
});
