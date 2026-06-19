    // World filter
    document.getElementById('worldFilter').addEventListener('change', function() {
        var params = new URLSearchParams();
        var worldId = this.value;
        if (worldId) params.append('world_id', worldId);
        var currentParams = new URLSearchParams(window.location.search);
        if (currentParams.has('tag')) params.append('tag', currentParams.get('tag'));
        var qs = params.toString();
        window.location.href = '/cases/' + (qs ? '?' + qs : '');
    });

    // Expandable tag filter
    var showMoreBtn = document.getElementById('showMoreTags');
    var showLessBtn = document.getElementById('showLessTags');
    var moreTags = document.getElementById('moreTags');

    if (showMoreBtn) {
        showMoreBtn.addEventListener('click', function(e) {
            e.preventDefault();
            moreTags.classList.remove('d-none');
            showMoreBtn.classList.add('d-none');
            showLessBtn.classList.remove('d-none');
        });
    }

    if (showLessBtn) {
        showLessBtn.addEventListener('click', function(e) {
            e.preventDefault();
            moreTags.classList.add('d-none');
            showLessBtn.classList.add('d-none');
            showMoreBtn.classList.remove('d-none');
        });
    }

    // Compact / Expanded view toggle
    var expandedBtn = document.getElementById('expandedViewBtn');
    var compactBtn = document.getElementById('compactViewBtn');
    var caseContainer = document.querySelector('.container');

    // Restore saved preference
    if (localStorage.getItem('caseViewMode') === 'compact') {
        caseContainer.classList.add('compact-view');
        compactBtn.classList.add('active');
        expandedBtn.classList.remove('active');
    }

    expandedBtn.addEventListener('click', function() {
        caseContainer.classList.remove('compact-view');
        expandedBtn.classList.add('active');
        compactBtn.classList.remove('active');
        localStorage.setItem('caseViewMode', 'expanded');
    });

    compactBtn.addEventListener('click', function() {
        caseContainer.classList.add('compact-view');
        compactBtn.classList.add('active');
        expandedBtn.classList.remove('active');
        localStorage.setItem('caseViewMode', 'compact');
    });
