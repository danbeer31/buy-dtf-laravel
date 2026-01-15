//* admin/customnames/fontsmap.js */
/* global $, jQuery, window, document */
(function ($) {
    var URLS = window.__FM_URLS || {};
    var $rows = $('#fm-rows');
    var $alert = $('#fm-alert');

    var _fonts = []; // [{slug,family,format,filename?,trackingMinPx?}]
    var _map = {}; // { slug: "Family" | {family:"Family", pxPerInch:392, trackingMinPx:-8} }

    function esc(v) {
        return (v == null ? '' : String(v)).replace(/[&<>"]/g, function (c) {
            return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
        });
    }

    function showAlert(kind, msg) {
        if (!$alert.length) return;
        $alert
            .removeClass('d-none alert-success alert-danger alert-warning')
            .addClass('alert-' + kind)
            .text(msg || '')
            .removeClass('d-none');
        setTimeout(function () {
            $alert.addClass('d-none');
        }, 2600);
    }

    function parseEntry(entry, fallbackFamily) {
        // Supports legacy string and new object {family, pxPerInch, trackingMinPx}
        if (entry && typeof entry === 'object') {
            return {
                family: entry.family || fallbackFamily || '',
                pxPerInch: (entry.pxPerInch == null ? '' : entry.pxPerInch),
                trackingMinPx: (entry.trackingMinPx == null ? '' : entry.trackingMinPx)
            };
        }
        return {family: entry || fallbackFamily || '', pxPerInch: '', trackingMinPx: ''};
    }

    function apiGet(url) {
        return $.getJSON(url);
    }

    function apiPostJSON(url, obj) {
        return $.ajax({
            url: url,
            method: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify(obj || {}),
            headers: {
                'X-CSRF-TOKEN': $('meta[name="csrf-token"]').attr('content')
            },
            xhrFields: {withCredentials: true}
        });
    }

    function loadAll() {
        $rows.html('<tr class="text-muted"><td colspan="7">Loading…</td></tr>');
        $.when(apiGet(URLS.fonts), apiGet(URLS.getMap))
            .done(function (a, b) {
                var fontsRes = a[0] || {};
                var mapRes = b[0] || {};
                var fonts = (fontsRes.fonts) || (fontsRes.data && fontsRes.data.fonts) || [];
                _fonts = fonts.map(function (f) {
                    var ext = f.format === 'truetype' ? '.ttf' :
                        (f.format === 'opentype' ? '.otf' :
                            (f.format ? '.' + f.format : ''));
                    return {
                        slug: (f.slug || '').toLowerCase(),
                        family: f.family || '',
                        format: f.format || '',
                        filename: (f.slug ? (f.slug + ext) : ''),
                        trackingMinPx: (typeof f.trackingMinPx === 'number' ? f.trackingMinPx : null) // from Node /fonts
                    };
                });
                _map = (mapRes.map) || (mapRes.data && mapRes.data.map) || (mapRes || {});
                render();
            })
            .fail(function (xhr) {
                showAlert('danger', 'Load error: ' + (xhr.responseText || xhr.status));
                $rows.html('<tr class="text-danger"><td colspan="7">Failed to load</td></tr>');
            });
    }

    function render() {
        if (!_fonts.length) {
            $rows.html('<tr><td colspan="7" class="text-muted">No fonts found</td></tr>');
            return;
        }
        var html = '';
        for (var i = 0; i < _fonts.length; i++) {
            var f = _fonts[i];
            var parts = parseEntry(_map[f.slug], f.family);
            var placeholderTrack = (parts.trackingMinPx === '' && f.trackingMinPx != null) ? (' placeholder="' + esc(f.trackingMinPx) + '"') : '';

            html += ''
                + '<tr data-slug="' + esc(f.slug) + '">'
                + '<td><code>' + esc(f.slug) + '</code></td>'
                + '<td><input type="text" class="form-control form-control-sm fm-family" value="' + esc(parts.family) + '" placeholder="Display name"></td>'
                // PPI column (fixed 70px)
                + '<td style="width:70px;max-width:70px;">'
                + '<input type="number" min="0" step="1"'
                + ' class="form-control form-control-sm fm-ppi"'
                + ' style="width:60px;min-width:60px;max-width:60px;text-align:right;"'
                + ' value="' + esc(parts.pxPerInch) + '" placeholder="">'
                + '</td>'
                // Tracking Min column (fixed 70px)
                + '<td style="width:70px;max-width:70px;">'
                + '<input type="number" step="1"'
                + ' class="form-control form-control-sm fm-tracking"'
                + ' style="width:60px;min-width:60px;max-width:60px;text-align:right;"'
                + ' value="' + esc(parts.trackingMinPx) + '"' + placeholderTrack
                + ' title="Minimum letter-spacing (px, can be negative)">'
                + '</td>'
                + '<td>' + esc(f.format || '') + '</td>'
                + '<td class="text-muted">' + esc(f.filename || '') + '</td>'
                + '<td><button class="btn btn-sm btn-outline-primary fm-update">Update</button></td>'
                + '</tr>';
        }
        $rows.html(html);
    }

    function collectMapFromTable() {
        var m = {};
        $('#fm-rows tr[data-slug]').each(function () {
            var slug = String($(this).data('slug') || '');
            var family = String($(this).find('.fm-family').val() || '').trim();
            var ppiStr = String($(this).find('.fm-ppi').val() || '').trim();
            var trkStr = String($(this).find('.fm-tracking').val() || '').trim();

            if (!slug || !family) return; // skip incomplete rows

            var hasPpi = (ppiStr !== '' && !isNaN(ppiStr) && Number(ppiStr) > 0);
            var hasTrk = (trkStr !== '' && !isNaN(trkStr)); // allow negative

            if (hasPpi || hasTrk) {
                var obj = {family: family};
                if (hasPpi) obj.pxPerInch = parseInt(ppiStr, 10);
                if (hasTrk) obj.trackingMinPx = parseInt(trkStr, 10);
                m[slug] = obj;
            } else {
                m[slug] = family; // legacy simple string if no calibration/track override set
            }
        });
        return m;
    }

    // Save ALL rows (full overwrite)
    function saveAll() {
        var map = collectMapFromTable();
        apiPostJSON(URLS.saveMap, {map: map})
            .done(function (res) {
                if (!res || res.success === false) return showAlert('danger', (res && res.message) || 'Save failed');
                showAlert('success', 'Saved.');
                loadAll();
            })
            .fail(function (xhr) {
                showAlert('danger', 'Save error: ' + (xhr.responseText || xhr.status));
            });
    }

    // Update one row — still posts the entire map (keeps behavior consistent)
    function updateSingle($tr) {
        var map = collectMapFromTable();
        apiPostJSON(URLS.saveMap, {map: map})
            .done(function (res) {
                if (!res || res.success === false) return showAlert('danger', (res && res.message) || 'Update failed');
                showAlert('success', 'Updated.');
                loadAll();
            })
            .fail(function (xhr) {
                showAlert('danger', 'Update error: ' + (xhr.responseText || xhr.status));
            });
    }

    function wire() {
        $('#btn-reload').on('click', function () {
            // Reload fonts on Node then refresh list
            apiPostJSON(URLS.reload, {})
                .done(function (res) {
                    if (!res || res.success === false) return showAlert('danger', (res && res.message) || 'Reload failed');
                    showAlert('success', 'Fonts reloaded.');
                    loadAll();
                })
                .fail(function (xhr) {
                    showAlert('danger', 'Reload error: ' + (xhr.responseText || xhr.status));
                });
        });

        $('#btn-save-all').on('click', saveAll);

        $rows.on('click', '.fm-update', function () {
            updateSingle($(this).closest('tr'));
        });
    }

    $(function () {
        wire();
        loadAll();
    });
})(jQuery);
