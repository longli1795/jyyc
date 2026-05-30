/**
 * 用户界面设置（预测期数等）：与服务端 user_ui_settings 同步
 */
(function () {
    const PREDICTION_PERIOD_KEY = 'cost_forecast_prediction_period';
    let __headerPeriodDebounceTimer = null;

    function clampPredictionPeriod(value) {
        let n = parseInt(value, 10);
        if (isNaN(n) || n < 1) n = 1;
        if (n > 120) n = 120;
        return n;
    }

    function applyPredictionPeriodToPage(period) {
        const n = clampPredictionPeriod(period);
        try {
            localStorage.setItem(PREDICTION_PERIOD_KEY, String(n));
        } catch (e) {
            console.warn('保存预测期数到 localStorage 失败:', e);
        }
        const input = document.getElementById('headerPredictionPeriod');
        if (input && String(input.value) !== String(n)) {
            input.value = n;
        }
        return n;
    }

    async function fetchUserUiSettings() {
        const response = await fetch('/api/system/user-ui-settings');
        const result = await response.json();
        if (!result.success) {
            throw new Error(result.error || '获取用户设置失败');
        }
        return result.data || {};
    }

    async function applySyncedUserUiSettings() {
        try {
            const settings = await fetchUserUiSettings();
            if (settings.prediction_period !== undefined && settings.prediction_period !== null) {
                applyPredictionPeriodToPage(settings.prediction_period);
            }
            return settings;
        } catch (e) {
            console.warn('应用同步的用户界面设置失败:', e);
            return null;
        }
    }

    async function savePredictionPeriodToServer(period) {
        const n = clampPredictionPeriod(period);
        try {
            await fetch('/api/system/user-ui-settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prediction_period: n })
            });
        } catch (e) {
            console.warn('保存预测期数到服务端失败:', e);
        }
        return n;
    }

    function initPredictionPeriodInput(options) {
        options = options || {};
        const input = document.getElementById('headerPredictionPeriod');
        if (!input) return;

        try {
            const saved = localStorage.getItem(PREDICTION_PERIOD_KEY);
            const n = parseInt(saved, 10);
            if (!isNaN(n) && n >= 1 && n <= 120) {
                input.value = n;
            } else {
                input.value = 1;
                localStorage.setItem(PREDICTION_PERIOD_KEY, '1');
            }
        } catch (e) {
            console.error('读取预测期数失败:', e);
            input.value = 1;
        }

        input.addEventListener('input', function () {
            const n = parseInt(input.value, 10);
            if (isNaN(n) || n < 1 || n > 120) {
                return;
            }
            try {
                localStorage.setItem(PREDICTION_PERIOD_KEY, String(n));
                if (typeof savePredictionPeriodToServer === 'function') {
                    savePredictionPeriodToServer(n);
                }
            } catch (e) {
                console.error('保存预测期数失败:', e);
            }
        });

        input.addEventListener('change', function () {
            let n = parseInt(input.value, 10);
            if (isNaN(n) || n < 1) n = 1;
            if (n > 120) n = 120;
            input.value = n;

            try {
                localStorage.setItem(PREDICTION_PERIOD_KEY, String(n));
                savePredictionPeriodToServer(n);
            } catch (e) {
                console.error('保存预测期数失败:', e);
            }

            if (__headerPeriodDebounceTimer) {
                clearTimeout(__headerPeriodDebounceTimer);
            }
            __headerPeriodDebounceTimer = setTimeout(function () {
                if (typeof options.onPeriodChange === 'function') {
                    options.onPeriodChange(n);
                }
            }, 300);
        });

        window.addEventListener('storage', function (e) {
            if (e.key === PREDICTION_PERIOD_KEY && e.newValue) {
                const n = parseInt(e.newValue, 10);
                if (!isNaN(n) && n >= 1 && n <= 120 && String(n) !== input.value) {
                    input.value = n;
                }
            }
        });
    }

    window.applySyncedUserUiSettings = applySyncedUserUiSettings;
    window.savePredictionPeriodToServer = savePredictionPeriodToServer;
    window.applyPredictionPeriodToPage = applyPredictionPeriodToPage;
    window.initPredictionPeriodInput = initPredictionPeriodInput;
})();
