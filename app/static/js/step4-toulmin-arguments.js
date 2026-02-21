/**
 * Step 4 Review -- Entity-Grounded Toulmin Arguments (E1-F3 Pipeline).
 *
 * Requires:
 *   - window.STEP4_CASE_ID (integer)
 *   - Bootstrap 5 (Popover component)
 *   - DOM elements: #argumentsContainer, #argument-count (optional),
 *     #generateArgumentsBtn (optional), #argumentsStatus (optional)
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
                renderEntityGroundedArguments(data);
                updateArgumentCount(data.arguments.length);
            }
        })
        .catch(function(err) {
            console.error('Error loading entity arguments:', err);
        });
}

function generateArguments() {
    var caseId = window.STEP4_CASE_ID;
    var btn = document.getElementById('generateArgumentsBtn');
    var status = document.getElementById('argumentsStatus');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Running E1-F3 Pipeline...';
    }
    if (status) status.textContent = 'Analyzing obligations, actions, and generating Toulmin arguments...';

    fetch('/scenario_pipeline/case/' + caseId + '/entity_arguments')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-chat-left-text"></i> Generate Arguments';
            }

            if (data.success) {
                entityArgumentsData = data;
                var summary = data.pipeline_summary;
                if (status) {
                    status.innerHTML =
                        '<span class="text-success">' +
                        summary.total_arguments + ' arguments (' + summary.pro_arguments + ' pro, ' + summary.con_arguments + ' con)' +
                        ' | ' + summary.valid_arguments + ' valid | Score: ' + (summary.average_score * 100).toFixed(0) + '%' +
                        '</span>';
                }
                renderEntityGroundedArguments(data);
                updateArgumentCount(data.arguments.length);
            } else {
                if (status) {
                    status.textContent = data.error || 'Generation failed';
                    status.className = 'ms-2 text-danger';
                }
            }
        })
        .catch(function(err) {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-chat-left-text"></i> Generate Arguments';
            }
            if (status) {
                status.textContent = 'Error: ' + err.message;
                status.className = 'ms-2 text-danger';
            }
            console.error('Generation error:', err);
        });
}

function updateArgumentCount(count) {
    var badge = document.getElementById('argument-count');
    if (!badge) return;
    if (count > 0) {
        badge.textContent = count;
        badge.style.display = 'inline';
    } else {
        badge.style.display = 'none';
    }
}

function renderEntityGroundedArguments(data) {
    var container = document.getElementById('argumentsContainer');
    if (!container) return;

    var args = data.arguments || [];
    var validations = data.validations || [];
    var decisionPoints = data.decision_points || [];
    var summary = data.pipeline_summary || {};

    if (args.length === 0) {
        container.innerHTML =
            '<div class="text-center text-muted py-5">' +
            '<i class="bi bi-chat-left-text" style="font-size: 3rem;"></i>' +
            '<p class="mt-2">No arguments generated yet.</p>' +
            '<p><small>Click "Generate Arguments" to run the E1-F3 entity analysis pipeline.</small></p>' +
            '</div>';
        return;
    }

    var validationLookup = {};
    validations.forEach(function(v) { validationLookup[v.argument_id] = v; });

    var dpLookup = {};
    decisionPoints.forEach(function(dp) { dpLookup[dp.focus_id] = dp; });

    var valSummary = data.validation_summary || {};
    var entityRate = ((valSummary.entity_test_pass_rate || 0) * 100).toFixed(0);
    var foundingRate = ((valSummary.founding_test_pass_rate || 0) * 100).toFixed(0);
    var virtueRate = ((valSummary.virtue_test_pass_rate || 0) * 100).toFixed(0);

    var html =
        '<div class="card mb-4 border-info">' +
        '<div class="card-header bg-info text-white d-flex justify-content-between align-items-center">' +
        '<span><i class="bi bi-graph-up me-2"></i>Entity-Grounded Argument Pipeline (E1-F3)</span>' +
        '<span class="badge bg-light text-dark">Toulmin Structure</span>' +
        '</div>' +
        '<div class="card-body">' +
        '<div class="row text-center">' +
        '<div class="col"><h4 class="text-primary mb-0">' + (summary.decision_points_count || 0) + '</h4><small class="text-muted">Decision Points</small></div>' +
        '<div class="col"><h4 class="text-success mb-0">' + (summary.pro_arguments || 0) + '</h4><small class="text-muted">PRO Arguments</small></div>' +
        '<div class="col"><h4 class="text-danger mb-0">' + (summary.con_arguments || 0) + '</h4><small class="text-muted">CON Arguments</small></div>' +
        '<div class="col"><h4 class="mb-0" style="color: ' + ((summary.valid_arguments / summary.total_arguments > 0.7) ? '#198754' : '#ffc107') + '">' + (summary.valid_arguments || 0) + '/' + (summary.total_arguments || 0) + '</h4><small class="text-muted">Valid</small></div>' +
        '<div class="col"><h4 class="mb-0">' + ((summary.average_score || 0) * 100).toFixed(0) + '%</h4><small class="text-muted">Avg Score</small></div>' +
        '</div>' +
        '<hr>' +
        '<div class="row text-center small">' +
        '<div class="col"><span class="badge ' + (valSummary.entity_test_pass_rate > 0.7 ? 'bg-success' : 'bg-warning') + '">Entity Refs: ' + entityRate + '%</span></div>' +
        '<div class="col"><span class="badge ' + (valSummary.founding_test_pass_rate > 0.9 ? 'bg-success' : 'bg-warning') + '">Founding Value: ' + foundingRate + '%</span></div>' +
        '<div class="col"><span class="badge ' + (valSummary.virtue_test_pass_rate > 0.7 ? 'bg-success' : 'bg-warning') + '">Virtues: ' + virtueRate + '%</span></div>' +
        '</div>' +
        '</div></div>';

    // Group by decision point
    var byDecisionPoint = {};
    args.forEach(function(arg) {
        var dpId = arg.decision_point_id;
        if (!byDecisionPoint[dpId]) byDecisionPoint[dpId] = { pro: [], con: [] };
        if (arg.argument_type === 'pro') byDecisionPoint[dpId].pro.push(arg);
        else byDecisionPoint[dpId].con.push(arg);
    });

    Object.entries(byDecisionPoint).forEach(function(entry) {
        var dpId = entry[0], dpArgs = entry[1];
        var dp = dpLookup[dpId] || {};

        html +=
            '<div class="card mb-4">' +
            '<div class="card-header bg-secondary text-white">' +
            '<div class="d-flex justify-content-between align-items-center">' +
            '<div><i class="bi bi-signpost-split me-2"></i><strong>' + dpId + '</strong>: ' + (dp.focus_description || 'Decision Point') + '</div>' +
            (dp.intensity_score ? '<span class="badge bg-warning text-dark">Intensity: ' + (dp.intensity_score * 100).toFixed(0) + '%</span>' : '') +
            '</div>' +
            '<small class="text-white-50">Role: ' + (dp.role_label || 'Unknown') +
            (dp.obligation_label ? ' | Obligation: ' + dp.obligation_label : '') +
            (dp.constraint_label ? ' | Constraint: ' + dp.constraint_label : '') +
            '</small>' +
            '</div>' +
            '<div class="card-body">' +
            (dp.board_conclusion ? '<div class="alert alert-success mb-3 py-2"><small><strong>Board Resolution:</strong> ' + dp.board_conclusion + '</small></div>' : '') +
            '<div class="row">' +
            '<div class="col-md-6">' +
            '<h6 class="text-success border-bottom pb-2"><i class="bi bi-hand-thumbs-up me-1"></i>PRO Arguments (' + dpArgs.pro.length + ')</h6>' +
            dpArgs.pro.map(function(arg) { return renderToulminArgument(arg, validationLookup[arg.argument_id], 'success'); }).join('') +
            '</div>' +
            '<div class="col-md-6">' +
            '<h6 class="text-danger border-bottom pb-2"><i class="bi bi-hand-thumbs-down me-1"></i>CON Arguments (' + dpArgs.con.length + ')</h6>' +
            dpArgs.con.map(function(arg) { return renderToulminArgument(arg, validationLookup[arg.argument_id], 'danger'); }).join('') +
            '</div>' +
            '</div></div></div>';
    });

    container.innerHTML = html;

    // Initialize popovers for warrant badges
    if (typeof bootstrap !== 'undefined') {
        container.querySelectorAll('[data-bs-toggle="popover"]:not([aria-describedby])').forEach(function(el) {
            new bootstrap.Popover(el, { container: 'body', sanitize: false });
        });
    }
}

function renderToulminArgument(arg, validation, colorClass) {
    var isValid = validation ? validation.is_valid : true;
    var score = validation ? validation.validation_score : 0;

    var validationBadges = '';
    if (validation) {
        var entityOk = validation.entity_validation && validation.entity_validation.is_valid;
        var foundingOk = validation.founding_value_validation && validation.founding_value_validation.is_compliant;
        var virtueOk = validation.virtue_validation && validation.virtue_validation.is_valid;

        validationBadges =
            '<span class="badge ' + (entityOk ? 'bg-success' : 'bg-warning') + ' me-1" title="Entity References"><i class="bi bi-link-45deg"></i></span>' +
            '<span class="badge ' + (foundingOk ? 'bg-success' : 'bg-danger') + ' me-1" title="Founding Value"><i class="bi bi-shield-check"></i></span>' +
            '<span class="badge ' + (virtueOk ? 'bg-success' : 'bg-secondary') + ' me-1" title="Professional Virtues"><i class="bi bi-star"></i></span>';
    }

    var virtueBadges = (arg.professional_virtues || []).map(function(v) {
        return '<span class="badge bg-light text-dark border me-1">' + v + '</span>';
    }).join('');

    var claimText = (arg.claim && arg.claim.text) || '';
    var warrantText = (arg.warrant && arg.warrant.text) || '';
    var warrantLabel = arg.warrant && arg.warrant.entity_label;
    var warrantType = arg.warrant && arg.warrant.entity_type;
    var warrantUri = arg.warrant && arg.warrant.entity_uri;

    var warrantBadge = '';
    if (warrantLabel) {
        var popoverContent = (warrantType ? warrantType.charAt(0).toUpperCase() + warrantType.slice(1) : 'Entity') + ': ' + warrantLabel + (warrantUri ? ' (' + warrantUri + ')' : '');
        warrantBadge = '<span class="badge bg-primary bg-opacity-25 ms-1" data-bs-toggle="popover" data-bs-trigger="hover" data-bs-placement="top" data-bs-content="' + popoverContent + '" style="cursor: help;">' + warrantLabel + '</span>';
    }

    var backingHtml = '';
    if (arg.backing && arg.backing.text) {
        var backingLabel = arg.backing.entity_label ? '<span class="badge bg-info bg-opacity-25 ms-1">' + arg.backing.entity_label + '</span>' : '';
        backingHtml = '<div class="mb-2"><span class="badge bg-info me-1">BACKING</span><span class="small">' + arg.backing.text + '</span>' + backingLabel + '</div>';
    }

    var dataHtml = '';
    if (arg.data && arg.data.length > 0) {
        dataHtml = '<div class="mb-2"><span class="badge bg-secondary me-1">DATA</span><ul class="list-unstyled mb-0 ms-4 small">' +
            arg.data.map(function(d) { return '<li>- ' + d.text + '</li>'; }).join('') +
            '</ul></div>';
    }

    var qualifierHtml = '';
    if (arg.qualifier && arg.qualifier.text) {
        qualifierHtml = '<div class="mb-2"><span class="badge bg-warning text-dark me-1">QUALIFIER</span><span class="small">' + arg.qualifier.text + '</span></div>';
    }

    var rebuttalHtml = '';
    if (arg.rebuttal && arg.rebuttal.text) {
        rebuttalHtml = '<div class="mb-2"><span class="badge bg-danger me-1">REBUTTAL</span><span class="small">' + arg.rebuttal.text + '</span></div>';
    }

    var foundingHtml = '';
    if (arg.founding_good_analysis) {
        foundingHtml = '<div class="small text-muted mt-1"><i class="bi bi-lightbulb me-1"></i>' + arg.founding_good_analysis + '</div>';
    }

    return '<div class="card mb-3 border-' + colorClass + (isValid ? '' : ' opacity-75') + '">' +
        '<div class="card-header bg-' + colorClass + ' bg-opacity-10 py-2">' +
        '<div class="d-flex justify-content-between align-items-center">' +
        '<span class="fw-bold">' + arg.argument_id + '</span>' +
        '<div>' + validationBadges + '<span class="badge ' + (isValid ? 'bg-success' : 'bg-secondary') + '">' + (score * 100).toFixed(0) + '%</span></div>' +
        '</div></div>' +
        '<div class="card-body py-2">' +
        '<div class="mb-2"><span class="badge bg-dark me-1">CLAIM</span><span class="fw-bold">' + claimText + '</span></div>' +
        '<div class="mb-2"><span class="badge bg-primary me-1">WARRANT</span><span>' + warrantText + '</span>' + warrantBadge + '</div>' +
        backingHtml + dataHtml + qualifierHtml + rebuttalHtml +
        '<div class="mt-2 pt-2 border-top"><small class="text-muted">Role: <span class="badge bg-light text-dark border">' + (arg.role_label || 'Unknown') + '</span>' +
        (virtueBadges ? ' | Virtues: ' + virtueBadges : '') +
        '</small></div>' +
        foundingHtml +
        '</div></div>';
}
