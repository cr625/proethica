document.addEventListener('DOMContentLoaded', function() {
    // Show/hide surfaced considerations text based on radio selection
    const surfacedRadios = document.querySelectorAll('input[name="surfaced_missed_considerations"]');
    const surfacedTextContainer = document.getElementById('surfacedTextContainer');

    surfacedRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            surfacedTextContainer.style.display = this.value === 'yes' ? 'block' : 'none';
        });
    });

    // Check initial state
    const checkedRadio = document.querySelector('input[name="surfaced_missed_considerations"]:checked');
    if (checkedRadio && checkedRadio.value === 'yes') {
        surfacedTextContainer.style.display = 'block';
    }

    // Ranking interactions. Two ways to reorder: drag-and-drop (mouse only,
    // HTML5 D&D) and per-row Move up / Move down buttons (keyboard-friendly,
    // reliable on touch devices, and the recommended path when the drag
    // handles feel uncooperative).
    const container = document.getElementById('rankContainer');
    let draggedItem = null;

    container.querySelectorAll('.rank-item').forEach(item => {
        item.setAttribute('draggable', 'true');

        item.addEventListener('dragstart', function(e) {
            draggedItem = this;
            this.classList.add('dragging');
            // Some browsers (older Safari, some Firefox configs) require a
            // setData call for the drag to register at all.
            if (e.dataTransfer) {
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', this.dataset.view || '');
            }
        });

        item.addEventListener('dragend', function() {
            this.classList.remove('dragging');
            updateRankNumbers();
        });
    });

    // dragover + drop on the CONTAINER (not per-item) so drops in the
    // padding/gap area work and so a fast cursor sweep does not lose the
    // dragged item between two adjacent items.
    container.addEventListener('dragover', function(e) {
        e.preventDefault();
        if (!draggedItem) return;
        const afterElement = getDragAfterElement(container, e.clientY);
        if (afterElement == null) {
            container.appendChild(draggedItem);
        } else if (afterElement !== draggedItem) {
            container.insertBefore(draggedItem, afterElement);
        }
    });
    container.addEventListener('drop', function(e) {
        e.preventDefault();
        // dragend handles classList + updateRankNumbers; nothing more here.
    });

    // Move up / Move down buttons. Always work; no D&D involved.
    container.addEventListener('click', function(e) {
        const upBtn = e.target.closest('.rank-up');
        const downBtn = e.target.closest('.rank-down');
        if (!upBtn && !downBtn) return;
        const row = (upBtn || downBtn).closest('.rank-item');
        if (!row) return;
        if (upBtn) {
            const prev = row.previousElementSibling;
            if (prev) container.insertBefore(row, prev);
        } else {
            const next = row.nextElementSibling;
            if (next) container.insertBefore(next, row);
        }
        updateRankNumbers();
    });

    function getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll('.rank-item:not(.dragging)')];
        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            if (offset < 0 && offset > closest.offset) {
                return { offset: offset, element: child };
            } else {
                return closest;
            }
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    function updateRankNumbers() {
        const items = container.querySelectorAll('.rank-item');
        items.forEach((item, index) => {
            const rankNum = index + 1;
            item.querySelector('.rank-number').textContent = rankNum;
            item.querySelector('input[type="hidden"]').value = rankNum;
            // Disable up on the first row and down on the last row.
            const upBtn = item.querySelector('.rank-up');
            const downBtn = item.querySelector('.rank-down');
            if (upBtn) upBtn.disabled = (index === 0);
            if (downBtn) downBtn.disabled = (index === items.length - 1);
        });
    }

    // Initialize button enabled/disabled state on first render.
    updateRankNumbers();
});
