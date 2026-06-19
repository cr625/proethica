    document.addEventListener('DOMContentLoaded', function() {
        // Handle select all checkbox
        const selectAllCheckbox = document.getElementById('selectAll');
        const caseCheckboxes = document.querySelectorAll('.case-checkbox');
        
        selectAllCheckbox.addEventListener('change', function() {
            caseCheckboxes.forEach(checkbox => {
                checkbox.checked = selectAllCheckbox.checked;
            });
        });
        
        // Handle search functionality
        const searchInput = document.getElementById('caseSearch');
        const searchButton = document.getElementById('searchButton');
        const casesTable = document.getElementById('casesTable');
        
        function performSearch() {
            const searchTerm = searchInput.value.toLowerCase();
            const rows = casesTable.querySelectorAll('tbody tr');
            
            rows.forEach(row => {
                const title = row.cells[2].textContent.toLowerCase();
                const type = row.cells[3].textContent.toLowerCase();
                
                if (title.includes(searchTerm) || type.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        }
        
        searchButton.addEventListener('click', performSearch);
        searchInput.addEventListener('keyup', function(event) {
            if (event.key === 'Enter') {
                performSearch();
            }
        });
        
        // Update "Select All" checkbox when individual checkboxes change
        caseCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                const allChecked = Array.from(caseCheckboxes).every(c => c.checked);
                const noneChecked = Array.from(caseCheckboxes).every(c => !c.checked);
                
                if (allChecked) {
                    selectAllCheckbox.checked = true;
                    selectAllCheckbox.indeterminate = false;
                } else if (noneChecked) {
                    selectAllCheckbox.checked = false;
                    selectAllCheckbox.indeterminate = false;
                } else {
                    selectAllCheckbox.indeterminate = true;
                }
            });
        });
    });
