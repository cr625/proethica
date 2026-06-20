// Progress tracking
function updateProgress() {
  const form = document.getElementById('evaluationForm');
  const radioGroups = new Set();
  form.querySelectorAll('input[type="radio"]').forEach(radio => {
    radioGroups.add(radio.name);
  });

  let filledGroups = 0;
  radioGroups.forEach(name => {
    if (form.querySelector(`input[name="${name}"]:checked`)) {
      filledGroups++;
    }
  });

  // Check preference and justification
  const preference = document.getElementById('overallPreference').value;
  const justification = document.getElementById('preferenceJustification').value.trim();

  let totalItems = radioGroups.size + 2; // +2 for preference and justification
  let completedItems = filledGroups;
  if (preference) completedItems++;
  if (justification.length >= 10) completedItems++;

  const progress = (completedItems / totalItems) * 100;
  document.getElementById('progressBar').style.width = progress + '%';
}

// Preference selection
function selectPreference(value) {
  const buttons = document.querySelectorAll('.preference-btn');
  buttons.forEach(btn => btn.classList.remove('selected'));

  const selectedBtn = document.querySelector(`[data-value="${value}"]`);
  if (selectedBtn) {
    selectedBtn.classList.add('selected');
  }

  document.getElementById('overallPreference').value = value;
  updateProgress();
}

// Scale selection visual feedback
document.addEventListener('DOMContentLoaded', function() {
  const radioButtons = document.querySelectorAll('input[type="radio"]');

  radioButtons.forEach(radio => {
    radio.addEventListener('change', function() {
      // Remove selected class from siblings
      const name = this.name;
      const siblings = document.querySelectorAll(`input[name="${name}"]`);
      siblings.forEach(sibling => {
        sibling.closest('.scale-option').classList.remove('selected');
      });

      // Add selected class to current
      this.closest('.scale-option').classList.add('selected');
      updateProgress();
    });
  });

  // Update progress on justification input
  document.getElementById('preferenceJustification').addEventListener('input', updateProgress);

  // Initialize progress
  updateProgress();
});

// Form validation before submit
document.getElementById('evaluationForm').addEventListener('submit', function(e) {
  const preference = document.getElementById('overallPreference').value;
  if (preference === '') {
    e.preventDefault();
    alert('Please select an overall preference before submitting.');
    return false;
  }

  const justification = document.getElementById('preferenceJustification').value.trim();
  if (justification.length < 10) {
    e.preventDefault();
    alert('Please provide a brief justification for your preference (at least 10 characters).');
    return false;
  }

  // Validate all radio groups
  const form = this;
  const radioGroups = new Set();
  form.querySelectorAll('input[type="radio"][required]').forEach(radio => {
    radioGroups.add(radio.name);
  });

  for (let group of radioGroups) {
    if (!form.querySelector(`input[name="${group}"]:checked`)) {
      e.preventDefault();
      alert('Please complete all evaluation ratings before submitting.');
      return false;
    }
  }

  return true;
});
