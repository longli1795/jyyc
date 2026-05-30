/**
 * 清除数据：POST /api/clear_data 并清理前端缓存
 */
(function () {
    let featureOptions = {};

    function clearUserDataCaches() {
        try {
            sessionStorage.removeItem('profit_summary_data');
            sessionStorage.removeItem('profit_summary_params');
            sessionStorage.removeItem('profit_summary_needs_reload');
            localStorage.removeItem('profit_summary_needs_reload');

            sessionStorage.removeItem('disassembly_profit_analysis_data');
            sessionStorage.removeItem('disassembly_profit_analysis_params');
            sessionStorage.removeItem('disassembly_profit_analysis_needs_reload');
            localStorage.removeItem('disassembly_profit_analysis_data_updated');

            const keysToRemove = [];
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && (key.includes('_data_') || key.includes('_cache_') ||
                    key.includes('_updated') || key === 'deducted_data_updated' ||
                    key === 'deducted_data_updated_time' || key === 'price_data_updated' ||
                    key === 'period_cost_data_updated')) {
                    if (key !== 'cost_forecast_prediction_period' &&
                        key !== 'coefficient_quality_manager' &&
                        key !== 'coefficient_quality_group' &&
                        key !== 'coefficient_warehouse_group') {
                        keysToRemove.push(key);
                    }
                }
            }
            keysToRemove.forEach(function (key) { localStorage.removeItem(key); });

            const sessionKeysToRemove = [];
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                if (key && (key.includes('_data_') || key.includes('_cache_') ||
                    key.includes('_needs_reload'))) {
                    sessionKeysToRemove.push(key);
                }
            }
            sessionKeysToRemove.forEach(function (key) { sessionStorage.removeItem(key); });
        } catch (e) {
            console.warn('清除缓存失败:', e);
        }
    }

    function handleClearData() {
        if (!confirm('确定要清除所有数据吗？这个操作不可撤销。')) {
            return;
        }

        if (typeof featureOptions.showLoading === 'function') {
            featureOptions.showLoading('正在清除数据...');
        }

        fetch('/api/clear_data', {
            method: 'POST',
            cache: 'no-cache',
            headers: { 'Cache-Control': 'no-cache' }
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (typeof featureOptions.hideLoading === 'function') {
                    featureOptions.hideLoading();
                }
                if (data.success) {
                    if (typeof featureOptions.showAlert === 'function') {
                        featureOptions.showAlert('success', data.message);
                    }
                    clearUserDataCaches();
                    if (typeof featureOptions.onSuccess === 'function') {
                        featureOptions.onSuccess();
                    }
                    location.reload(true);
                } else if (typeof featureOptions.showAlert === 'function') {
                    featureOptions.showAlert('danger', data.message);
                }
            })
            .catch(function (error) {
                if (typeof featureOptions.hideLoading === 'function') {
                    featureOptions.hideLoading();
                }
                if (typeof featureOptions.showAlert === 'function') {
                    featureOptions.showAlert('danger', '清除数据失败: ' + error.message);
                }
            });
    }

    function initClearDataFeature(options) {
        featureOptions = options || {};
        const clearDataBtn = document.getElementById('clearDataBtn');
        if (clearDataBtn) {
            clearDataBtn.addEventListener('click', handleClearData);
        }
    }

    window.clearUserDataCaches = clearUserDataCaches;
    window.handleClearData = handleClearData;
    window.initClearDataFeature = initClearDataFeature;
})();
