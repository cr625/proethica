  document.addEventListener('DOMContentLoaded', function() {
    // Toggle diff view
    document.getElementById('show-diff-view').addEventListener('click', function() {
      const diffView = document.getElementById('diff-view');
      
      if (diffView.classList.contains('show')) {
        diffView.classList.remove('show');
        this.textContent = 'Show Differences';
      } else {
        // Get prediction texts
        const predictions = document.querySelectorAll('.prediction-text');
        if (predictions.length < 2) return;
        
        const baselineText = predictions[0].innerHTML;
        const proethicaText = predictions[1].innerHTML;
        
        // Generate diff
        const diff = Diff.diffWords(baselineText, proethicaText);
        
        // Display diff
        const diffContent = document.getElementById('diff-content');
        diffContent.innerHTML = '';
        
        diff.forEach(part => {
          const span = document.createElement('span');
          span.textContent = part.value;
          
          if (part.added) {
            span.className = 'diff-highlight-add';
          } else if (part.removed) {
            span.className = 'diff-highlight-remove';
          }
          
          diffContent.appendChild(span);
        });
        
        diffView.classList.add('show');
        this.textContent = 'Hide Differences';
      }
    });
    
    // Toggle entity highlighting
    document.getElementById('highlight-entities').addEventListener('click', function() {
      const predictions = document.querySelectorAll('.prediction-card');
      const isHighlighting = this.getAttribute('data-highlighting') === 'true';
      
      if (isHighlighting) {
        // Remove highlighting
        document.querySelectorAll('.highlighted-term').forEach(el => {
          const text = el.textContent;
          el.outerHTML = text;
        });
        
        this.setAttribute('data-highlighting', 'false');
        this.textContent = 'Highlight Ontology Entities';
      } else {
        // Add highlighting
        predictions.forEach(container => {
          const entityTags = container.querySelectorAll('.entity-tag');
          const predictionText = container.querySelector('.prediction-text');
          
          if (entityTags.length > 0 && predictionText) {
            let text = predictionText.innerHTML;
            
            entityTags.forEach(tag => {
              const term = tag.textContent;
              // Only highlight if term is substantial (not just a few characters)
              if (term && term.length > 3) {
                const regex = new RegExp(`\\b${term}\\b`, 'gi');
                text = text.replace(regex, `<span class="highlighted-term">$&</span>`);
              }
            });
            
            predictionText.innerHTML = text;
          }
        });
        
        this.setAttribute('data-highlighting', 'true');
        this.textContent = 'Remove Highlighting';
      }
    });
    
    // Form validation
    document.getElementById('evaluation-form').addEventListener('submit', function(e) {
      const inputs = this.querySelectorAll('input[type="number"]');
      let valid = true;
      
      inputs.forEach(input => {
        const value = parseInt(input.value);
        if (isNaN(value) || value < 0 || value > 10) {
          valid = false;
          input.classList.add('is-invalid');
        } else {
          input.classList.remove('is-invalid');
        }
      });
      
      if (!valid) {
        e.preventDefault();
        alert('Please ensure all rating scores are between 0 and 10.');
      }
    });
  });
