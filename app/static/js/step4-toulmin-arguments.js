/**
 * Step 4 Review -- Entity-Grounded Toulmin Arguments (E1-F3 Pipeline).
 *
 * Injects compact pro/con arguments into each Decision Point's
 * .dp-arguments-slot container on the Decisions & Arguments tab.
 *
 * Requires:
 *   - window.STEP4_CASE_ID (integer)
 *   - Bootstrap 5 (Collapse, Popover)
 *   - DOM elements: .dp-arguments-slot[data-dp-id] inside #decisionpoints
 */

var entityArgumentsData = null;

// Auto-load on script inclusion
(function() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { loadEntityArguments(); });
    } else {
        loadEntityArguments();
    }
})();

function loadEntityArguments() {
    var caseId = window.STEP4_CASE_ID;
    if (!caseId) return;

    fetch('/scenario_pipeline/case/' + caseId + '/entity_arguments')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success && data.arguments && data.arguments.length > 0) {
                entityArgumentsData = data;
                injectArgumentsIntoDecisionPoints(data);
            }
        })
        .catch(function(err) {
            console.error('Error loading entity arguments:', err);
        });
}

function injectArgumentsIntoDecisionPoints(data) {
    var args = data.arguments || [];
    var validations = data.validations || [];
    var summary = data.pipeline_summary || {};

    if (args.length === 0) return;

    var validationLookup = {};
    validations.forEach(function(v) { validationLookup[v.argument_id] = v; });

    // Group by decision point
    var byDP = {};
    args.forEach(function(arg) {
        var dpId = arg.decision_point_id;
        if (!byDP[dpId]) byDP[dpId] = { pro: [], con: [] };
        byDP[dpId][arg.argument_type].push(arg);
    });

    // Inject into each DP's slot
    var slots = document.querySelectorAll('.dp-arguments-slot');
    slots.forEach(function(slot) {
        var dpId = slot.dataset.dpId;
        var dpArgs = byDP[dpId];
        if (!dpArgs) return;

        var proCount = dpArgs.pro.length;
        var conCount = dpArgs.con.length;
        var total = proCount + conCount;

        var html = '<div class="mt-3 pt-2 border-top">' +
            '<div class="d-flex align-items-center mb-2">' +
            '<small class="text-secondary fw-semibold me-2">Entity-Grounded Arguments</small>' +
            '<span class="badge bg-success me-1">' + proCount + ' pro</span>' +
            '<span class="badge bg-danger">' + conCount + ' con</span>' +
            '</div>';

        // Pro arguments
        if (dpArgs.pro.length > 0) {
            html += '<div class="mb-2">';
            dpArgs.pro.forEach(function(arg, i) {
                html += renderCompactArgument(arg, validationLookup[arg.argument_id], 'success', dpId + '-pro-' + i);
            });
            html += '</div>';
        }

        // Con arguments
        if (dpArgs.con.length > 0) {
            html += '<div class="mb-1">';
            dpArgs.con.forEach(function(arg, i) {
                html += renderCompactArgument(arg, validationLookup[arg.argument_id], 'danger', dpId + '-con-' + i);
            });
            html += '</div>';
        }

        html += '</div>';
        slot.innerHTML = html;
    });

    // Initialize collapse chevrons and popovers
    document.querySelectorAll('.arg-compact-header').forEach(function(header) {
        var target = document.querySelector(header.dataset.bsTarget);
        if (!target) return;
        var chevron = header.querySelector('.arg-chevron');
        if (!chevron) return;
        target.addEventListener('show.bs.collapse', function() {
            chevron.classList.replace('bi-chevron-right', 'bi-chevron-down');
        });
        target.addEventListener('hide.bs.collapse', function() {
            chevron.classList.replace('bi-chevron-down', 'bi-chevron-right');
        });
    });

    if (typeof bootstrap !== 'undefined') {
        document.querySelectorAll('.dp-arguments-slot [data-bs-toggle="popover"]:not([aria-describedby])').forEach(function(el) {
            new bootstrap.Popover(el, { container: 'body', sanitize: false });
        });
    }
}

function renderCompactArgument(arg, validation, colorClass, uid) {
    var claimText = (arg.claim && arg.claim.text) || '';
    var truncatedClaim = claimText.length > 80 ? claimText.substring(0, 80) + '...' : claimText;
    var score = validation ? validation.validation_score : 0;
    var isValid = validation ? validation.is_valid : true;
    var argType = arg.argument_type;

    // Compact header
    var header =
        '<div class="arg-compact-header d-flex align-items-center p-1 rounded mb-1" ' +
        'data-bs-toggle="collapse" data-bs-target="#arg-' + uid + '" role="button" ' +
        'aria-expanded="false" style="cursor: pointer; border: 1px solid transparent;" ' +
        'onmouseover="this.style.backgroundColor=\'#f8f9fa\';this.style.borderColor=\'#dee2e6\'" ' +
        'onmouseout="this.style.backgroundColor=\'\';this.style.borderColor=\'transparent\'">' +
        '<i class="bi bi-chevron-right arg-chevron me-1" style="font-size: 0.65rem; color: #6c757d;"></i>' +
        '<i class="bi bi-hand-thumbs-' + (argType === 'pro' ? 'up' : 'down') +
        ' text-' + colorClass + ' me-1"></i>' +
        '<span class="small text-muted me-1">' + arg.argument_id + '</span>' +
        '<span class="small flex-grow-1">' + truncatedClaim + '</span>' +
        '<span class="badge ' + (isValid ? 'bg-' + colorClass : 'bg-secondary') +
        ' ms-1" style="font-size: 0.6rem;">' + (score * 100).toFixed(0) + '%</span>' +
        '</div>';

    // Expanded detail (Toulmin structure)
    var warrantText = (arg.warrant && arg.warrant.text) || '';
    var warrantLabel = arg.warrant && arg.warrant.entity_label;

    var detail = '<div class="collapse" id="arg-' + uid + '">' +
        '<div class="ps-4 pe-2 pb-2 pt-1 small" style="border-left: 2px solid ' +
        (colorClass === 'success' ? '#198754' : '#dc3545') + ';">';

    // Claim
    detail += '<div class="mb-1"><span class="badge bg-dark me-1" style="font-size: 0.6rem;">CLAIM</span>' +
        '<strong>' + claimText + '</strong></div>';

    // Warrant
    if (warrantText) {
        detail += '<div class="mb-1"><span class="badge bg-primary me-1" style="font-size: 0.6rem;">WARRANT</span>' +
            warrantText;
        if (warrantLabel) {
            detail += ' <span class="badge bg-primary bg-opacity-25" style="font-size: 0.6rem;">' + warrantLabel + '</span>';
        }
        detail += '</div>';
    }

    // Backing
    if (arg.backing && arg.backing.text) {
        detail += '<div class="mb-1"><span class="badge bg-info me-1" style="font-size: 0.6rem;">BACKING</span>' +
            arg.backing.text;
        if (arg.backing.entity_label) {
            detail += ' <span class="badge bg-info bg-opacity-25" style="font-size: 0.6rem;">' + arg.backing.entity_label + '</span>';
        }
        detail += '</div>';
    }

    // Data
    if (arg.data && arg.data.length > 0) {
        detail += '<div class="mb-1"><span class="badge bg-secondary me-1" style="font-size: 0.6rem;">DATA</span>';
        arg.data.forEach(function(d) { detail += d.text + '; '; });
        detail += '</div>';
    }

    // Rebuttal
    if (arg.rebuttal && arg.rebuttal.text) {
        detail += '<div class="mb-1"><span class="badge bg-danger me-1" style="font-size: 0.6rem;">REBUTTAL</span>' +
            arg.rebuttal.text + '</div>';
    }

    // Qualifier
    if (arg.qualifier && arg.qualifier.text) {
        detail += '<div class="mb-1"><span class="badge bg-warning text-dark me-1" style="font-size: 0.6rem;">QUALIFIER</span>' +
            arg.qualifier.text + '</div>';
    }

    // Validation details
    if (validation) {
        var entityOk = validation.entity_validation && validation.entity_validation.is_valid;
        var foundingOk = validation.founding_value_validation && validation.founding_value_validation.is_compliant;
        var virtueOk = validation.virtue_validation && validation.virtue_validation.is_valid;
        detail += '<div class="mt-1 d-flex gap-1">' +
            '<span class="badge ' + (entityOk ? 'bg-success' : 'bg-warning') + '" style="font-size: 0.6rem;" title="Entity References"><i class="bi bi-link-45deg"></i></span>' +
            '<span class="badge ' + (foundingOk ? 'bg-success' : 'bg-danger') + '" style="font-size: 0.6rem;" title="Founding Value"><i class="bi bi-shield-check"></i></span>' +
            '<span class="badge ' + (virtueOk ? 'bg-success' : 'bg-secondary') + '" style="font-size: 0.6rem;" title="Professional Virtues"><i class="bi bi-star"></i></span>';
        if (arg.professional_virtues && arg.professional_virtues.length > 0) {
            arg.professional_virtues.forEach(function(v) {
                detail += '<span class="badge bg-light text-dark border" style="font-size: 0.6rem;">' + v + '</span>';
            });
        }
        detail += '</div>';
    }

    detail += '</div></div>';

    return header + detail;
}
