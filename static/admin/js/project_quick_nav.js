(function () {
    function initQuickNav() {
        var body = document.body;
        if (!body) return;
        if (!body.classList.contains('model-projectaudit')) return;

        var groups = [];
        var fieldsets = document.querySelectorAll('fieldset.module.aligned');
        fieldsets.forEach(function (fieldset, idx) {
            var titleNode = fieldset.querySelector('h2');
            if (!titleNode) return;
            var title = titleNode.textContent.trim();
            if (!title) return;
            if (!fieldset.id) {
                fieldset.id = 'project-section-' + idx;
            }
            groups.push({title: title, id: fieldset.id});
        });

        var inlineGroup = document.querySelector('.inline-group');
        if (inlineGroup) {
            if (!inlineGroup.id) {
                inlineGroup.id = 'project-section-coordinates-inline';
            }
            groups.push({title: '坐标明细', id: inlineGroup.id});
        }

        if (!groups.length) return;
        if (document.querySelector('.project-quick-nav')) return;

        var nav = document.createElement('div');
        nav.className = 'project-quick-nav';

        var title = document.createElement('div');
        title.className = 'nav-title';
        title.textContent = '快速导航';
        nav.appendChild(title);

        groups.forEach(function (group) {
            var link = document.createElement('a');
            link.href = '#' + group.id;
            link.textContent = group.title;
            nav.appendChild(link);
        });

        document.body.appendChild(nav);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initQuickNav);
    } else {
        initQuickNav();
    }
})();
