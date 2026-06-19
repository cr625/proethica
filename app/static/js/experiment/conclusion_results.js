  document.addEventListener('DOMContentLoaded', function() {
    // Highlight ontology terms in prediction text
    const predictions = document.querySelectorAll('.prediction-container');
    
    predictions.forEach(container => {
      const entityTags = container.querySelectorAll('.entity-tag');
      const predictionText = container.querySelector('.prediction-content');
      
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
  });
