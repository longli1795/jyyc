/**
 * 期初库存状态条文案，以及「固化后若未按该文件计算过则自动重算」的标记。
 */
(function (global) {
    var STAMP_KEY = 'opening_inventory_calc_stamp';

    function formatTime(iso) {
        if (!iso) return '';
        var s = String(iso).replace('T', ' ');
        return s.length >= 16 ? s.slice(0, 16) : s;
    }

    function stamp(meta) {
        if (!meta) return '';
        return meta.uploaded_at || meta.last_loaded_at || '';
    }

    function formatHintHtml(meta) {
        if (!meta) return '';
        var source = meta.source || 'upload';
        var name;
        if (source === 'sap') {
            var period = meta.sap_period || '';
            name = period ? ('SAP ' + period) : (meta.original_filename || 'SAP取数');
        } else {
            name = meta.original_filename || 'opening_inventory';
        }
        var timeStr = formatTime(stamp(meta));
        var timeHtml = timeStr ? (' 更新于 ' + timeStr) : '';
        return '已固化：' + name + timeHtml +
            ' <a href="/api/opening-inventory/download" title="下载固化文件">下载</a>';
    }

    function markCalculated(meta) {
        var value = stamp(meta);
        if (value) {
            try {
                localStorage.setItem(STAMP_KEY, value);
            } catch (e) {}
        }
    }

    function isStale(meta) {
        var value = stamp(meta);
        if (!value) return false;
        try {
            return localStorage.getItem(STAMP_KEY) !== value;
        } catch (e) {
            return true;
        }
    }

    function markCalculatedFromStatus() {
        return fetch('/api/status')
            .then(function (response) { return response.json(); })
            .then(function (statusInfo) {
                markCalculated(statusInfo && statusInfo.opening_inventory_meta);
                return statusInfo;
            })
            .catch(function () { return null; });
    }

    global.OpeningInventoryUI = {
        formatTime: formatTime,
        stamp: stamp,
        formatHintHtml: formatHintHtml,
        markCalculated: markCalculated,
        isStale: isStale,
        markCalculatedFromStatus: markCalculatedFromStatus
    };
})(window);
