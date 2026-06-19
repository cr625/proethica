    document.addEventListener('DOMContentLoaded', function () {
        // Get all tab buttons and input type fields
        const fileTabs = document.querySelectorAll('.nav-link:not(.disabled)');
        const inputTypeFile = document.getElementById('input_type_file');
        const inputTypeUrl = document.getElementById('input_type_url');
        const inputTypeText = document.getElementById('input_type_text');

        // Initialize - text tab is active by default, others are disabled
        inputTypeFile.disabled = true;
        inputTypeUrl.disabled = true;
        inputTypeText.disabled = false;

        // Add event listeners to non-disabled tabs only
        fileTabs.forEach(tab => {
            tab.addEventListener('click', function () {
                // Disable all input type fields
                inputTypeFile.disabled = true;
                inputTypeUrl.disabled = true;
                inputTypeText.disabled = true;

                // Enable the selected input type field (only text tab should be clickable)
                if (this.id === 'text-tab') {
                    inputTypeText.disabled = false;
                }
            });
        });

        // Form validation - only validate text input since other tabs are disabled
        const form = document.getElementById('guidelineForm');
        form.addEventListener('submit', function (event) {
            let isValid = true;
            const textInput = document.getElementById('guidelines_text');
            
            if (!textInput.value.trim()) {
                alert('Please enter some guidelines text.');
                isValid = false;
            }

            if (!isValid) {
                event.preventDefault();
            }
        });
    });
