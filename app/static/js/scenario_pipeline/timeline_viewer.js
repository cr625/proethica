function toggleDetails(sequence) {
    const details = document.getElementById(`details-${sequence}`);
    const toggleText = document.getElementById(`toggle-text-${sequence}`);
    const button = event.target.closest('button');
    const icon = button.querySelector('i');

    if (details.classList.contains('show')) {
        details.classList.remove('show');
        toggleText.textContent = 'Show Details';
        icon.className = 'bi bi-chevron-down';
    } else {
        details.classList.add('show');
        toggleText.textContent = 'Hide Details';
        icon.className = 'bi bi-chevron-up';
    }
}
