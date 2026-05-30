/**
 * 根据 window.allowedPages 隐藏无权限的页面元素。
 * 元素需设置 data-page-permission="page_key"。
 */
(function () {
    function applyPagePermissionFilter() {
        var allowed = window.allowedPages || [];
        var allowedSet = {};
        allowed.forEach(function (k) { allowedSet[k] = true; });

        document.querySelectorAll('[data-page-permission]').forEach(function (el) {
            var perm = el.getAttribute('data-page-permission');
            if (perm && !allowedSet[perm]) {
                el.style.display = 'none';
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyPagePermissionFilter);
    } else {
        applyPagePermissionFilter();
    }
})();
