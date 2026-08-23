document.addEventListener('DOMContentLoaded', function() {
    // Get sprint and day IDs from data attributes
    var pageData = document.getElementById('page-data');
    var sprintId = pageData?.dataset.sprintId;
    var dayNo = pageData?.dataset.dayNo;
    var csrfToken = document.querySelector('input[name="csrf_token"]')?.value;

    // Rubric checkbox handlers
    document.querySelectorAll('input[type="checkbox"][data-rubric-index]').forEach(function(cb) {
        cb.addEventListener('change', function() {
            var projectIndex = this.dataset.projectIndex;
            var rubricIndex = this.dataset.rubricIndex;
            var checked = this.checked;
            
            fetch('/sprints/' + sprintId + '/day/' + dayNo + '/rubric-check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrfToken
                },
                body: new URLSearchParams({
                    'project_index': projectIndex,
                    'rubric_index': rubricIndex,
                    'checked': checked
                })
            }).then(function(response) {
                return response.json();
            }).then(function(data) {
                if (!data.ok) {
                    console.error('Rubric check failed:', data.error);
                    // Revert checkbox on error
                    document.querySelector('input[data-rubric-index="' + rubricIndex + '"]').checked = !checked;
                }
            }).catch(function(err) {
                console.error('Rubric check error:', err);
                document.querySelector('input[data-rubric-index="' + rubricIndex + '"]').checked = !checked;
            });
        });
    });
    
    // Gap-fill check-item handler (without :has() pseudo-class)
    var gapfillItems = document.querySelectorAll('.check-item');
    gapfillItems.forEach(function(item) {
        var label = item.querySelector('b');
        if (label && label.textContent.includes('Gap-fill addressed')) {
            item.addEventListener('click', function(e) {
                // Don't trigger if clicking on a link/button inside
                if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON') return;
                
                var checked = !item.classList.contains('done');
                fetch('/sprints/' + sprintId + '/day/' + dayNo + '/gapfill-check', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': csrfToken
                    },
                    body: new URLSearchParams({
                        'checked': checked
                    })
                }).then(function(response) {
                    return response.json();
                }).then(function(data) {
                    if (data.ok) {
                        if (checked) item.classList.add('done');
                        else item.classList.remove('done');
                    } else {
                        console.error('Gap-fill check failed:', data.error);
                    }
                }).catch(function(err) {
                    console.error('Gap-fill check error:', err);
                });
            });
        }
    });
});