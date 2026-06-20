    document.addEventListener('DOMContentLoaded', function () {
        // Handle citation buttons
        document.querySelectorAll('.get-citation').forEach(button => {
            button.addEventListener('click', function () {
                const itemKey = this.getAttribute('data-item-key');
                const container = this.nextElementSibling;
                const citationText = container.querySelector('.citation-text');

                // Toggle visibility
                if (container.classList.contains('d-none')) {
                    container.classList.remove('d-none');

                    // Get citation in APA format by default
                    getCitation(itemKey, 'apa', citationText);
                } else {
                    container.classList.add('d-none');
                }
            });
        });

        // Handle citation style buttons
        document.querySelectorAll('.citation-style').forEach(button => {
            button.addEventListener('click', function () {
                const style = this.getAttribute('data-style');
                const container = this.closest('.citation-container');
                const itemKey = container.parentElement.querySelector('.get-citation').getAttribute('data-item-key');
                const citationText = container.querySelector('.citation-text');

                // Get citation in selected format
                getCitation(itemKey, style, citationText);

                // Update active button
                container.querySelectorAll('.citation-style').forEach(btn => {
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline-secondary');
                });
                this.classList.remove('btn-outline-secondary');
                this.classList.add('btn-primary');
            });
        });

        // Function to get citation
        function getCitation(itemKey, style, citationElement) {
            citationElement.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div> Loading citation...';

            fetch(`/worlds/${(window.WORLD_REFERENCES || {}).worldId}/references/${itemKey}/citation?style=${style}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        citationElement.innerHTML = data.citation;
                    } else {
                        citationElement.innerHTML = `<div class="text-danger">Error: ${data.message}</div>`;
                    }
                })
                .catch(error => {
                    citationElement.innerHTML = `<div class="text-danger">Error: ${error.message}</div>`;
                });
        }

        // Handle reference type change
        document.getElementById('referenceType').addEventListener('change', function () {
            const type = this.value;
            const journalFields = document.querySelectorAll('.journal-field');

            if (type === 'journalArticle') {
                journalFields.forEach(field => field.style.display = 'block');
            } else {
                journalFields.forEach(field => field.style.display = 'none');
            }
        });

        // Handle add author button
        document.getElementById('addAuthorBtn').addEventListener('click', function () {
            const authorsContainer = document.getElementById('authorsContainer');
            const authorRow = document.querySelector('.author-row').cloneNode(true);

            // Clear input values
            authorRow.querySelectorAll('input').forEach(input => input.value = '');

            // Add remove button event listener
            authorRow.querySelector('.remove-author').addEventListener('click', function () {
                this.closest('.author-row').remove();
            });

            // Insert before the add button
            authorsContainer.insertBefore(authorRow, document.getElementById('addAuthorBtn'));
        });

        // Handle remove author button for initial row
        document.querySelector('.remove-author').addEventListener('click', function () {
            if (document.querySelectorAll('.author-row').length > 1) {
                this.closest('.author-row').remove();
            }
        });

        // Handle save reference button
        document.getElementById('saveReferenceBtn').addEventListener('click', function () {
            const form = document.getElementById('addReferenceForm');
            const formData = new FormData(form);

            // Prepare data
            const data = {
                item_type: formData.get('item_type'),
                title: formData.get('title'),
                creators: [],
                additional_fields: {}
            };

            // Get authors
            const lastNames = formData.getAll('lastName[]');
            const firstNames = formData.getAll('firstName[]');

            for (let i = 0; i < lastNames.length; i++) {
                if (lastNames[i]) {
                    data.creators.push({
                        creatorType: 'author',
                        lastName: lastNames[i],
                        firstName: firstNames[i] || ''
                    });
                }
            }

            // Get additional fields
            const additionalFields = ['publicationTitle', 'date', 'volume', 'issue', 'pages', 'DOI', 'url', 'abstractNote'];
            additionalFields.forEach(field => {
                const value = formData.get(field);
                if (value) {
                    data.additional_fields[field] = value;
                }
            });

            // Send request
            fetch(`/worlds/${(window.WORLD_REFERENCES || {}).worldId}/references/add`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Close modal
                        const modal = bootstrap.Modal.getInstance(document.getElementById('addReferenceModal'));
                        modal.hide();

                        // Reload page to show new reference
                        window.location.reload();
                    } else {
                        alert(`Error: ${data.message}`);
                    }
                })
                .catch(error => {
                    alert(`Error: ${error.message}`);
                });
        });
    });
