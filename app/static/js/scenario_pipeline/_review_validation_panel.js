var validationDemoActive = false;

function toggleValidationDemo() {
    validationDemoActive = !validationDemoActive;
    var toggle = document.getElementById('validationDemoToggle');
    var panel = document.getElementById('validationDemoPanel');
    var qcTab = document.getElementById('questions-tab');

    if (validationDemoActive) {
        panel.classList.add('show');
        toggle.classList.remove('btn-outline-info');
        toggle.classList.add('btn-info');
        toggle.innerHTML = '<i class="bi bi-x-lg"></i> Close Demo';

        if (qcTab) {
            qcTab.closest('li').style.display = 'none';
        }

        updateValidationPanelForTab();
    } else {
        panel.classList.remove('show');
        toggle.classList.remove('btn-info');
        toggle.classList.add('btn-outline-info');
        toggle.innerHTML = '<i class="bi bi-clipboard-check"></i> Validation Demo';

        if (qcTab) {
            qcTab.closest('li').style.display = '';
        }
    }
}

function updateValidationPanelForTab() {
    var activeTab = document.querySelector('#reviewTabs .nav-link.active');
    if (!activeTab) return;

    var tabId = activeTab.id;
    var viewTitle = document.getElementById('validationViewTitle');
    var likertContent = document.getElementById('validationLikertContent');

    var viewConfig = {
        'provisions-tab': {
            name: 'Provisions',
            icon: 'bi-file-text',
            color: '#6c757d',
            questions: [
                'The code provision mapping helped me identify which professional standards apply to this case.',
                'The connections between provisions and case facts were clear and useful.',
                'This view helped me understand the normative foundation for evaluating the case.'
            ]
        },
        'decision-points-tab': {
            name: 'Decisions',
            icon: 'bi-signpost-split',
            color: '#0d6efd',
            questions: [
                'The decision points helped me understand the choices the professional faced.',
                'The alternatives presented gave useful context for evaluation.',
                'This view helped me trace how the professional\'s actions related to their obligations.'
            ]
        },
        'narrative-tab': {
            name: 'Narrative',
            icon: 'bi-book',
            color: '#198754',
            questions: [
                'The character profiles and timeline helped me understand the situation.',
                'The relationship information clarified who was involved and how.',
                'The sequence of events and decisions was clear.'
            ]
        },
        'fullgraph-tab': {
            name: 'Entities',
            icon: 'bi-diagram-3',
            color: '#0d6efd',
            questions: [
                'The entity graph helped me see the key participants and concepts.',
                'The relationships between entities clarified the case structure.',
                'This view provided useful context for understanding the ethical situation.'
            ]
        },
        'richanalysis-tab': {
            name: 'Analysis',
            icon: 'bi-lightbulb',
            color: '#fd7e14',
            questions: [
                'The analysis view helped me understand the ethical dimensions.',
                'The rich analysis surfaced considerations I might have missed.',
                'This view was useful for forming my own ethical judgment.'
            ]
        }
    };

    var config = viewConfig[tabId] || viewConfig['provisions-tab'];

    viewTitle.innerHTML = '<i class="bi ' + config.icon + '" style="color: ' + config.color + ';"></i> ' + config.name + ' View';

    var html = '';
    config.questions.forEach(function(q, idx) {
        html += '<div class="validation-likert-question mb-4">' +
            '<div class="likert-statement">' + q + '</div>' +
            '<div class="likert-scale-row">';
        for (var i = 1; i <= 7; i++) {
            html += '<div class="likert-option">' +
                '<input type="radio" name="demo_q' + idx + '" id="demo_q' + idx + '_' + i + '" value="' + i + '">' +
                '<label for="demo_q' + idx + '_' + i + '">' +
                '<span class="likert-circle">' + i + '</span>' +
                '</label></div>';
        }
        html += '</div>' +
            '<div class="scale-anchors">' +
            '<span>Strongly Disagree</span>' +
            '<span>Strongly Agree</span>' +
            '</div></div>';
    });

    likertContent.innerHTML = html;

    likertContent.querySelectorAll('input[type="radio"]').forEach(function(input) {
        input.addEventListener('change', function() {
            var val = parseInt(this.value);
            var circle = this.nextElementSibling.querySelector('.likert-circle');
            if (val <= 2) circle.style.background = '#dc3545';
            else if (val === 3) circle.style.background = '#fd7e14';
            else if (val === 4) circle.style.background = '#ffc107';
            else if (val === 5) circle.style.background = '#20c997';
            else circle.style.background = '#198754';
            circle.style.borderColor = circle.style.background;
            circle.style.color = val === 4 ? '#212529' : 'white';
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('#reviewTabs .nav-link').forEach(function(tab) {
        tab.addEventListener('shown.bs.tab', function() {
            if (validationDemoActive) {
                updateValidationPanelForTab();
            }
        });
    });

    var urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('validation_mode') === '1') {
        toggleValidationDemo();
    }
});
