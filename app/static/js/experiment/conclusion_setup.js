  document.addEventListener('DOMContentLoaded', function() {
    // Handle case selection
    const caseCards = document.querySelectorAll('.case-card');
    const selectedCasesList = document.getElementById('selected-cases-list');
    const selectedCountBadge = document.getElementById('selected-count');
    
    updateSelectedCasesList();
    
    caseCards.forEach(card => {
      card.addEventListener('click', function(e) {
        // Don't toggle if clicking on the checkbox directly
        if (e.target.type !== 'checkbox') {
          const checkbox = this.querySelector('input[type="checkbox"]');
          checkbox.checked = !checkbox.checked;
        }
        
        // Update UI
        this.classList.toggle('selected', this.querySelector('input[type="checkbox"]').checked);
        updateSelectedCasesList();
      });
    });
    
    // Search functionality
    document.getElementById('search-cases').addEventListener('input', function(e) {
      const searchText = this.value.toLowerCase();
      
      caseCards.forEach(card => {
        const title = card.querySelector('label').innerText.toLowerCase();
        const description = card.querySelector('small').innerText.toLowerCase();
        
        if (title.includes(searchText) || description.includes(searchText)) {
          card.style.display = '';
        } else {
          card.style.display = 'none';
        }
      });
    });
    
    // Form validation
    document.getElementById('setup-form').addEventListener('submit', function(e) {
      const selectedCases = document.querySelectorAll('input[name="selected_cases"]:checked');
      
      if (selectedCases.length === 0) {
        e.preventDefault();
        alert('Please select at least one case for the experiment.');
        return false;
      }
      
      if (document.getElementById('experiment-name').value.trim() === '') {
        e.preventDefault();
        alert('Please enter an experiment name.');
        return false;
      }
      
      return true;
    });
    
    function updateSelectedCasesList() {
      const selectedCases = document.querySelectorAll('input[name="selected_cases"]:checked');
      selectedCasesList.innerHTML = '';
      selectedCountBadge.textContent = selectedCases.length;
      
      selectedCases.forEach(checkbox => {
        const caseTitle = checkbox.closest('.case-card').querySelector('label').innerText;
        const listItem = document.createElement('li');
        listItem.className = 'list-group-item d-flex justify-content-between align-items-center';
        listItem.innerHTML = `
          ${caseTitle}
          <button type="button" class="btn btn-sm btn-outline-danger remove-case" data-case-id="${checkbox.value}">
            Remove
          </button>
        `;
        selectedCasesList.appendChild(listItem);
      });
      
      // Add event listeners to remove buttons
      document.querySelectorAll('.remove-case').forEach(button => {
        button.addEventListener('click', function() {
          const caseId = this.getAttribute('data-case-id');
          const checkbox = document.querySelector(`input[value="${caseId}"]`);
          checkbox.checked = false;
          checkbox.closest('.case-card').classList.remove('selected');
          updateSelectedCasesList();
        });
      });
    }
  });
