/**
 * 工作区全量快照：保存/加载复盘数据
 */
(function () {
    const PREDICTION_PERIOD_KEY = 'cost_forecast_prediction_period';

    function formatSize(bytes) {
        if (!bytes || bytes < 1024) return (bytes || 0) + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function formatTime(iso) {
        if (!iso) return '-';
        try {
            return new Date(iso).toLocaleString('zh-CN');
        } catch (e) {
            return iso;
        }
    }

    function setResult(el, text, isError) {
        if (!el) return;
        el.textContent = text;
        el.className = 'mt-2 small ' + (isError ? 'text-danger' : 'text-success');
    }

    async function openSaveModal() {
        const modalEl = document.getElementById('saveSnapshotModal');
        if (!modalEl) return;
        document.getElementById('snapshotSaveFilename').value = '';
        document.getElementById('snapshotSaveToServer').checked = true;
        document.getElementById('snapshotAlsoDownload').checked = false;
        setResult(document.getElementById('snapshotSaveResult'), '', false);
        new bootstrap.Modal(modalEl).show();
    }

    async function doSaveSnapshot() {
        const filename = (document.getElementById('snapshotSaveFilename').value || '').trim();
        if (!filename) {
            setResult(document.getElementById('snapshotSaveResult'), '请输入快照名称', true);
            return;
        }
        const saveToServer = document.getElementById('snapshotSaveToServer').checked;
        const alsoDownload = document.getElementById('snapshotAlsoDownload').checked;
        const resultEl = document.getElementById('snapshotSaveResult');
        setResult(resultEl, '正在保存快照...', false);

        try {
            const r = await fetch('/api/snapshot/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filename: filename,
                    save_to_server: saveToServer,
                    also_download: alsoDownload
                })
            });

            if (alsoDownload || !saveToServer) {
                if (!r.ok) {
                    let msg = '保存失败';
                    try {
                        const j = await r.json();
                        msg = j.message || msg;
                    } catch (e) { /* ignore */ }
                    setResult(resultEl, msg, true);
                    return;
                }
                const blob = await r.blob();
                const disp = r.headers.get('Content-Disposition') || '';
                let dlName = filename.endsWith('.zip') ? filename : filename + '.zip';
                const m = disp.match(/filename[^;=\n]*=(["']?)([^"'\n]*)\1/);
                if (m && m[2]) dlName = decodeURIComponent(m[2]);
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = dlName;
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
                setResult(resultEl, saveToServer ? '已保存到服务器并已下载' : '下载已开始', false);
                setTimeout(function () {
                    bootstrap.Modal.getInstance(document.getElementById('saveSnapshotModal')).hide();
                }, 1200);
                return;
            }

            const j = await r.json();
            if (j.success) {
                setResult(resultEl, j.message || '保存成功', false);
                setTimeout(function () {
                    bootstrap.Modal.getInstance(document.getElementById('saveSnapshotModal')).hide();
                }, 1200);
            } else {
                setResult(resultEl, j.message || '保存失败', true);
            }
        } catch (e) {
            setResult(resultEl, '请求失败: ' + e.message, true);
        }
    }

    function canDeleteSnapshot() {
        return !!document.getElementById('saveSnapshotBtn');
    }

    async function loadServerSnapshotList() {
        const listEl = document.getElementById('snapshotServerList');
        if (!listEl) return;
        listEl.innerHTML = '<div class="text-muted small p-2">加载中...</div>';
        try {
            const r = await fetch('/api/snapshot/list');
            const j = await r.json();
            if (!j.success) {
                listEl.innerHTML = '<div class="text-danger small p-2">' + (j.message || '加载失败') + '</div>';
                return;
            }
            const items = j.data || [];
            if (items.length === 0) {
                listEl.innerHTML = '<div class="text-muted small p-2">暂无已保存的快照</div>';
                return;
            }
            const showDelete = canDeleteSnapshot();
            listEl.innerHTML = items.map(function (item) {
                const safeFilename = item.filename.replace(/"/g, '&quot;');
                const displayName = item.display_name || item.filename;
                const deleteBtn = showDelete ? (
                    '<button type="button" class="btn btn-sm btn-outline-danger snapshot-delete-btn ms-2 flex-shrink-0"' +
                    ' data-filename="' + safeFilename + '"' +
                    ' data-display-name="' + String(displayName).replace(/"/g, '&quot;') + '"' +
                    ' title="删除快照"><i class="fas fa-trash-alt"></i></button>'
                ) : '';
                return (
                    '<div class="list-group-item d-flex justify-content-between align-items-center">' +
                    '<label class="mb-0 flex-grow-1 d-flex align-items-start">' +
                    '<input class="form-check-input me-2 snapshot-server-radio mt-1" type="radio" name="snapshotServerFile" value="' +
                    safeFilename + '">' +
                    '<div>' +
                    '<strong>' + displayName + '</strong>' +
                    '<div class="small text-muted">' +
                    formatTime(item.saved_at || item.modified_at) +
                    ' · ' + formatSize(item.size_bytes) +
                    (item.session_count ? ' · ' + item.session_count + ' 项数据' : '') +
                    '</div></div></label>' +
                    deleteBtn +
                    '</div>'
                );
            }).join('');
        } catch (e) {
            listEl.innerHTML = '<div class="text-danger small p-2">加载失败: ' + e.message + '</div>';
        }
    }

    async function deleteServerSnapshot(filename, displayName) {
        if (!confirm('确定删除快照「' + displayName + '」？此操作不可恢复。')) {
            return;
        }
        const resultEl = document.getElementById('snapshotLoadResult');
        setResult(resultEl, '正在删除快照...', false);
        try {
            const r = await fetch('/api/snapshot/delete/' + encodeURIComponent(filename), {
                method: 'DELETE'
            });
            const j = await r.json();
            if (!r.ok || !j.success) {
                setResult(resultEl, j.message || '删除失败', true);
                return;
            }
            setResult(resultEl, j.message || '快照已删除', false);
            await loadServerSnapshotList();
        } catch (e) {
            setResult(resultEl, '请求失败: ' + e.message, true);
        }
    }

    async function openLoadModal() {
        const modalEl = document.getElementById('loadSnapshotModal');
        if (!modalEl) return;
        document.getElementById('snapshotUploadFile').value = '';
        setResult(document.getElementById('snapshotLoadResult'), '', false);
        document.getElementById('snapshotLoadConfirm').checked = false;
        const serverTab = document.getElementById('snapshot-tab-server');
        if (serverTab) {
            serverTab.click();
            await loadServerSnapshotList();
        }
        new bootstrap.Modal(modalEl).show();
    }

    async function doLoadSnapshot() {
        const resultEl = document.getElementById('snapshotLoadResult');
        const confirmed = document.getElementById('snapshotLoadConfirm');
        if (!confirmed || !confirmed.checked) {
            setResult(resultEl, '请先勾选确认：了解加载将覆盖当前全部数据', true);
            return;
        }

        const activeTab = document.querySelector('#snapshotLoadTabs .nav-link.active');
        const isServer = activeTab && activeTab.id === 'snapshot-tab-server';
        setResult(resultEl, '正在加载快照，请稍候...', false);

        try {
            let r;
            if (isServer) {
                const selected = document.querySelector('input[name="snapshotServerFile"]:checked');
                if (!selected) {
                    setResult(resultEl, '请选择一个服务器快照', true);
                    return;
                }
                r = await fetch('/api/snapshot/load', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source: 'server', filename: selected.value })
                });
            } else {
                const fileInput = document.getElementById('snapshotUploadFile');
                if (!fileInput || !fileInput.files || !fileInput.files[0]) {
                    setResult(resultEl, '请选择本地 zip 快照文件', true);
                    return;
                }
                const fd = new FormData();
                fd.append('source', 'upload');
                fd.append('file', fileInput.files[0]);
                r = await fetch('/api/snapshot/load', { method: 'POST', body: fd });
            }

            const j = await r.json();
            if (!j.success) {
                setResult(resultEl, j.message || '加载失败', true);
                return;
            }

            const pp = j.data && j.data.prediction_period;
            if (pp !== undefined && pp !== null) {
                try {
                    localStorage.setItem(PREDICTION_PERIOD_KEY, String(pp));
                    const input = document.getElementById('headerPredictionPeriod');
                    if (input) input.value = pp;
                } catch (e) { /* ignore */ }
            }

            // 快照会替换全部会话数据，必须失效利润汇总表 sessionStorage 缓存
            try {
                sessionStorage.setItem('profit_summary_needs_reload', 'true');
                localStorage.setItem('profit_summary_needs_reload', Date.now().toString());
            } catch (e) { /* ignore */ }

            setResult(resultEl, j.message || '加载成功，正在刷新页面...', false);
            setTimeout(function () {
                window.location.reload();
            }, 800);
        } catch (e) {
            setResult(resultEl, '请求失败: ' + e.message, true);
        }
    }

    function initSnapshotFeature() {
        const saveBtn = document.getElementById('saveSnapshotBtn');
        const loadBtn = document.getElementById('loadSnapshotBtn');
        const saveSubmit = document.getElementById('snapshotSaveSubmitBtn');
        const loadSubmit = document.getElementById('snapshotLoadSubmitBtn');

        if (saveBtn) saveBtn.addEventListener('click', openSaveModal);
        if (loadBtn) loadBtn.addEventListener('click', openLoadModal);
        if (saveSubmit) saveSubmit.addEventListener('click', doSaveSnapshot);
        if (loadSubmit) loadSubmit.addEventListener('click', doLoadSnapshot);

        const serverTab = document.getElementById('snapshot-tab-server');
        if (serverTab) {
            serverTab.addEventListener('shown.bs.tab', loadServerSnapshotList);
        }

        const listEl = document.getElementById('snapshotServerList');
        if (listEl) {
            listEl.addEventListener('click', function (e) {
                const btn = e.target.closest('.snapshot-delete-btn');
                if (!btn) return;
                e.preventDefault();
                e.stopPropagation();
                const filename = btn.getAttribute('data-filename');
                const displayName = btn.getAttribute('data-display-name') || filename;
                if (filename) {
                    deleteServerSnapshot(filename, displayName);
                }
            });
        }
    }

    window.initSnapshotFeature = initSnapshotFeature;
})();
