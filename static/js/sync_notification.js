/**
 * 同步数据通知：轮询待确认通知，支持历史同步版本选择与应用
 */
(function () {
    let syncNotificationPollInFlight = false;
    let shownSyncNotificationKey = null;
    let onAcceptCallback = null;
    let listenersBound = false;
    let latestSyncId = null;

    function formatTime(iso) {
        if (!iso) return '-';
        try {
            return new Date(iso).toLocaleString('zh-CN');
        } catch (e) {
            return iso;
        }
    }

    function hideSyncNotificationBar() {
        const bar = document.getElementById('syncNotificationBar');
        if (bar) bar.style.display = 'none';
    }

    function showSyncNotificationBar(fromName, syncedAt, syncId) {
        const bar = document.getElementById('syncNotificationBar');
        const textEl = document.getElementById('syncNotificationText');
        if (!bar || !textEl) return;
        const name = fromName || '其他用户';
        textEl.textContent = name + ' 向您同步了数据，是否立即刷新查看？';
        bar.style.display = 'flex';
        shownSyncNotificationKey = (fromName || '') + '|' + (syncedAt || '');
        latestSyncId = syncId || null;
    }

    async function loadSyncHistoryList() {
        const listEl = document.getElementById('syncHistoryList');
        const resultEl = document.getElementById('syncHistoryResult');
        if (!listEl) return [];
        listEl.innerHTML = '<div class="text-muted small p-2">加载中...</div>';
        if (resultEl) {
            resultEl.textContent = '';
            resultEl.className = 'mt-2 small';
        }
        try {
            const response = await fetch('/api/system/session/sync-history');
            const result = await response.json();
            if (!result.success) {
                listEl.innerHTML = '<div class="text-danger small p-2">' + (result.error || '加载失败') + '</div>';
                return [];
            }
            const items = result.data || [];
            if (items.length === 0) {
                listEl.innerHTML = '<div class="text-muted small p-2">暂无同步历史记录</div>';
                return [];
            }
            const defaultId = latestSyncId || (items[0] && items[0].sync_id) || '';
            listEl.innerHTML = items.map(function (item) {
                const syncId = item.sync_id || '';
                const checked = syncId === defaultId ? ' checked' : '';
                const fromName = item.from_name || '其他用户';
                const countText = item.session_count ? item.session_count + ' 项数据' : '';
                return (
                    '<label class="list-group-item list-group-item-action d-flex justify-content-between align-items-start">' +
                    '<div class="me-2">' +
                    '<input class="form-check-input me-2 sync-history-radio" type="radio" name="syncHistoryItem"' +
                    ' value="' + syncId.replace(/"/g, '&quot;') + '"' + checked + '>' +
                    '<strong>' + fromName + '</strong>' +
                    '<div class="small text-muted">' +
                    formatTime(item.synced_at) +
                    (countText ? ' · ' + countText : '') +
                    '</div></div></label>'
                );
            }).join('');
            return items;
        } catch (e) {
            listEl.innerHTML = '<div class="text-danger small p-2">加载失败: ' + e.message + '</div>';
            return [];
        }
    }

    async function openSyncHistoryModal() {
        const modalEl = document.getElementById('syncHistoryModal');
        if (!modalEl) return;
        await loadSyncHistoryList();
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            new bootstrap.Modal(modalEl).show();
        }
    }

    function getSelectedSyncId() {
        const selected = document.querySelector('input[name="syncHistoryItem"]:checked');
        return selected ? selected.value : null;
    }

    async function applyAndAcceptSync(selectedSyncId) {
        if (selectedSyncId && latestSyncId && selectedSyncId !== latestSyncId) {
            const applyResp = await fetch('/api/system/session/sync-history/apply', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sync_id: selectedSyncId })
            });
            const applyResult = await applyResp.json();
            if (!applyResult.success) {
                throw new Error(applyResult.error || applyResult.message || '应用同步版本失败');
            }
        }
        await fetch('/api/system/session/sync-notification/accept', { method: 'POST' });
        hideSyncNotificationBar();
        shownSyncNotificationKey = null;
        latestSyncId = null;
        if (typeof applySyncedUserUiSettings === 'function') {
            await applySyncedUserUiSettings();
        }
        if (typeof onAcceptCallback === 'function') {
            onAcceptCallback();
        }
    }

    async function pollSyncNotification() {
        if (syncNotificationPollInFlight) return;
        if (!document.getElementById('syncNotificationBar')) return;
        syncNotificationPollInFlight = true;
        try {
            const response = await fetch('/api/system/session/sync-notification');
            const result = await response.json();
            if (!result.success || !result.data || !result.data.pending) {
                return;
            }
            const key = (result.data.from_name || '') + '|' + (result.data.synced_at || '');
            if (key === shownSyncNotificationKey) {
                latestSyncId = result.data.sync_id || latestSyncId;
                return;
            }
            showSyncNotificationBar(
                result.data.from_name,
                result.data.synced_at,
                result.data.sync_id
            );
        } catch (e) {
            console.warn('检查同步通知失败:', e);
        } finally {
            syncNotificationPollInFlight = false;
        }
    }

    function bindSyncNotificationButtons() {
        const acceptBtn = document.getElementById('syncNotificationAccept');
        const chooseBtn = document.getElementById('syncNotificationChoose');
        const dismissBtn = document.getElementById('syncNotificationDismiss');
        const applyBtn = document.getElementById('syncHistoryApplyBtn');
        const modalDismissBtn = document.getElementById('syncHistoryDismissBtn');

        if (acceptBtn && !acceptBtn.dataset.syncBound) {
            acceptBtn.dataset.syncBound = '1';
            acceptBtn.addEventListener('click', async function () {
                acceptBtn.disabled = true;
                try {
                    await applyAndAcceptSync(latestSyncId);
                } catch (e) {
                    console.warn('确认同步通知失败:', e);
                    alert(e.message || '刷新失败，请重试');
                } finally {
                    acceptBtn.disabled = false;
                }
            });
        }

        if (chooseBtn && !chooseBtn.dataset.syncBound) {
            chooseBtn.dataset.syncBound = '1';
            chooseBtn.addEventListener('click', function () {
                openSyncHistoryModal();
            });
        }

        if (dismissBtn && !dismissBtn.dataset.syncBound) {
            dismissBtn.dataset.syncBound = '1';
            dismissBtn.addEventListener('click', async function () {
                dismissBtn.disabled = true;
                try {
                    await fetch('/api/system/session/sync-notification/dismiss', { method: 'POST' });
                    hideSyncNotificationBar();
                    shownSyncNotificationKey = null;
                    latestSyncId = null;
                } catch (e) {
                    console.warn('忽略同步通知失败:', e);
                } finally {
                    dismissBtn.disabled = false;
                }
            });
        }

        if (applyBtn && !applyBtn.dataset.syncBound) {
            applyBtn.dataset.syncBound = '1';
            applyBtn.addEventListener('click', async function () {
                const resultEl = document.getElementById('syncHistoryResult');
                const selectedSyncId = getSelectedSyncId();
                if (!selectedSyncId) {
                    if (resultEl) {
                        resultEl.textContent = '请选择一条同步记录';
                        resultEl.className = 'mt-2 small text-danger';
                    }
                    return;
                }
                applyBtn.disabled = true;
                if (resultEl) {
                    resultEl.textContent = '正在应用...';
                    resultEl.className = 'mt-2 small text-muted';
                }
                try {
                    await applyAndAcceptSync(selectedSyncId);
                    const modalEl = document.getElementById('syncHistoryModal');
                    if (modalEl && typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                        const inst = bootstrap.Modal.getInstance(modalEl);
                        if (inst) inst.hide();
                    }
                } catch (e) {
                    console.warn('应用同步历史失败:', e);
                    if (resultEl) {
                        resultEl.textContent = e.message || '应用失败，请重试';
                        resultEl.className = 'mt-2 small text-danger';
                    }
                } finally {
                    applyBtn.disabled = false;
                }
            });
        }

        if (modalDismissBtn && !modalDismissBtn.dataset.syncBound) {
            modalDismissBtn.dataset.syncBound = '1';
            modalDismissBtn.addEventListener('click', async function () {
                modalDismissBtn.disabled = true;
                try {
                    await fetch('/api/system/session/sync-notification/dismiss', { method: 'POST' });
                    hideSyncNotificationBar();
                    shownSyncNotificationKey = null;
                    latestSyncId = null;
                    const modalEl = document.getElementById('syncHistoryModal');
                    if (modalEl && typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                        const inst = bootstrap.Modal.getInstance(modalEl);
                        if (inst) inst.hide();
                    }
                } catch (e) {
                    console.warn('忽略同步通知失败:', e);
                } finally {
                    modalDismissBtn.disabled = false;
                }
            });
        }
    }

    function initSyncNotification(options) {
        options = options || {};
        onAcceptCallback = options.onAccept || null;
        bindSyncNotificationButtons();
        if (listenersBound) {
            pollSyncNotification();
            return;
        }
        listenersBound = true;
        pollSyncNotification();
        setInterval(function () {
            if (document.visibilityState === 'visible') {
                pollSyncNotification();
            }
        }, 15000);
        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) {
                pollSyncNotification();
            }
        });
        window.addEventListener('focus', function () {
            pollSyncNotification();
        });
    }

    window.pollSyncNotification = pollSyncNotification;
    window.initSyncNotification = initSyncNotification;
    window.openSyncHistoryModal = openSyncHistoryModal;
})();
