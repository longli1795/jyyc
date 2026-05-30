/**
 * 同步数据：弹窗选择目标用户/用户组并 POST /api/data-management/sync
 */
(function () {
    async function openSyncDataModal() {
        const modalEl = document.getElementById('syncDataModal');
        if (!modalEl) return;

        const modal = new bootstrap.Modal(modalEl);
        document.getElementById('syncResult').textContent = '';
        try {
            const r = await fetch('/api/data-management/sync-targets');
            const j = await r.json();
            if (!j.success) {
                document.getElementById('syncResult').textContent = j.message || '获取目标失败';
                return;
            }
            const users = j.data.users || [];
            const groups = j.data.groups || [];
            const userSel = document.getElementById('syncUserIds');
            const groupSel = document.getElementById('syncGroupIds');
            userSel.innerHTML = users.map(function (u) {
                return '<option value="' + u.id + '">' + (u.display_name || u.username) + (u.group_name ? ' (' + u.group_name + ')' : '') + '</option>';
            }).join('');
            groupSel.innerHTML = groups.map(function (g) {
                return '<option value="' + g.id + '">' + g.name + '</option>';
            }).join('');
        } catch (e) {
            document.getElementById('syncResult').textContent = '加载失败: ' + e.message;
        }
        modal.show();
    }

    function initSyncModalListeners() {
        const typeUsers = document.getElementById('syncTypeUsers');
        const typeGroups = document.getElementById('syncTypeGroups');
        const typeAll = document.getElementById('syncTypeAll');
        const usersWrap = document.getElementById('syncUsersWrap');
        const groupsWrap = document.getElementById('syncGroupsWrap');
        const submitBtn = document.getElementById('syncSubmitBtn');
        if (!submitBtn) return;

        function toggle() {
            const v = document.querySelector('input[name="syncTargetType"]:checked');
            usersWrap.style.display = (v && v.value === 'users') ? 'block' : 'none';
            groupsWrap.style.display = (v && v.value === 'groups') ? 'block' : 'none';
        }
        if (typeUsers) typeUsers.addEventListener('change', toggle);
        if (typeGroups) typeGroups.addEventListener('change', toggle);
        if (typeAll) typeAll.addEventListener('change', toggle);
        submitBtn.addEventListener('click', doSyncData);
    }

    async function doSyncData() {
        const targetType = document.querySelector('input[name="syncTargetType"]:checked');
        const type = targetType ? targetType.value : 'users';
        const body = { target_type: type };
        if (type === 'users') {
            const sel = document.getElementById('syncUserIds');
            body.user_ids = Array.from(sel.selectedOptions).map(function (o) { return parseInt(o.value, 10); });
            if (body.user_ids.length === 0) {
                document.getElementById('syncResult').textContent = '请至少选择一名用户';
                return;
            }
        } else if (type === 'groups') {
            const sel = document.getElementById('syncGroupIds');
            body.group_ids = Array.from(sel.selectedOptions).map(function (o) { return parseInt(o.value, 10); });
            if (body.group_ids.length === 0) {
                document.getElementById('syncResult').textContent = '请至少选择一个用户组';
                return;
            }
        }
        try {
            const savedPeriod = localStorage.getItem('cost_forecast_prediction_period') || '1';
            body.prediction_period = parseInt(savedPeriod, 10) || 1;
        } catch (e) {
            body.prediction_period = 1;
        }
        document.getElementById('syncResult').textContent = '正在同步...';
        try {
            const r = await fetch('/api/data-management/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const j = await r.json();
            const el = document.getElementById('syncResult');
            if (j.success) {
                el.textContent = j.message || '同步成功';
                el.className = 'mt-2 small text-success';
                setTimeout(function () {
                    bootstrap.Modal.getInstance(document.getElementById('syncDataModal')).hide();
                }, 1500);
            } else {
                el.textContent = j.message || '同步失败';
                el.className = 'mt-2 small text-danger';
            }
        } catch (e) {
            document.getElementById('syncResult').textContent = '请求失败: ' + e.message;
            document.getElementById('syncResult').className = 'mt-2 small text-danger';
        }
    }

    function initSyncDataFeature() {
        const syncDataBtn = document.getElementById('syncDataBtn');
        if (syncDataBtn) {
            syncDataBtn.addEventListener('click', openSyncDataModal);
        }
        if (document.getElementById('syncDataModal')) {
            initSyncModalListeners();
        }
    }

    window.initSyncDataFeature = initSyncDataFeature;
})();
