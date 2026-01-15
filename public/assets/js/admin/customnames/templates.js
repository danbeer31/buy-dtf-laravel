/* admin/customnames/templates.js */
/* global $, jQuery, window, document */
(function ($) {
    // endpoints (match your PHP routes)
    var LIST_URL = '/admin/customnames/template/get?slug=__list__';
    var RELOAD_URL = '/admin/customnames/templates/reload';

    // DOM hooks expected in templates.tpl
    var $rows = $('#tpl-rows');
    var $alert = $('#tpl-alert');

    function showAlert(kind, msg) {
        // kind: success | danger | warning
        if (!$alert.length) return;
        $alert.removeClass('d-none alert-success alert-danger alert-warning')
            .addClass('alert-' + kind)
            .text(msg || '')
            .removeClass('d-none');
        setTimeout(function () {
            $alert.addClass('d-none');
        }, 3000);
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
        });
    }

    // Be tolerant of various API shapes
    function pickTemplates(res) {
        if (!res) return [];
        if (res.templates && res.templates.length) return res.templates;
        if (res.items && res.items.length) return res.items;
        if (res.list && res.list.length) return res.list;
        if (res.rows && res.rows.length) return res.rows;
        if (res.data && res.data.templates && res.data.templates.length) return res.data.templates;
        return [];
    }

    // Normalize so each row has BOTH id and slug, and a display title
    function normalizeRows(arr) {
        var out = [];
        for (var i = 0; i < (arr || []).length; i++) {
            var it = arr[i] || {};
            var slug = it.slug || it.id || '';
            if (!slug) continue;
            out.push({
                id: it.id || slug,
                slug: slug,
                title: it.title || slug,
                updated: it.updated || it.updatedAt || '',
                widthIn: it.widthIn || it.width || null,
                heightIn: it.heightIn || it.height || null,
                dpi: it.dpi || null
            });
        }
        return out;
    }

    function renderLoading() {
        if (!$rows.length) return;
        $rows.html('<tr class="text-muted"><td colspan="4">Loading…</td></tr>');
    }

    function renderEmpty() {
        if (!$rows.length) return;
        $rows.html('<tr class="text-muted"><td colspan="4">No templates</td></tr>');
    }

    function renderRows(rows) {
        if (!$rows.length) return;
        if (!rows || !rows.length) {
            renderEmpty();
            return;
        }

        var html = '';
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i];
            var updated = r.updated ? String(r.updated).replace('T', ' ').replace('Z', '') : '';
            var editUrl = '/admin/customnames/templatebuilder?slug=' + encodeURIComponent(r.slug);
            html += ''
                + '<tr data-slug="' + escapeHtml(r.slug) + '">'
                + '<td><code>' + escapeHtml(r.slug) + '</code></td>'
                + '<td>' + escapeHtml(r.title || '') + '</td>'
                + '<td>' + escapeHtml(updated) + '</td>'
                + '<td style="width:120px">'
                + '<a class="btn btn-sm btn-outline-primary" href="' + editUrl + '">Edit</a>'
                + '</td>'
                + '</tr>';
        }
        $rows.html(html);
    }

    function loadList() {
        renderLoading();
        $.getJSON(LIST_URL, function (res) {
            if (!res || res.success === false) {
                showAlert('danger', (res && res.message) ? res.message : 'Failed to load templates');
                renderEmpty();
                return;
            }
            var raw = pickTemplates(res);
            var rows = normalizeRows(raw);
            renderRows(rows);
        }).fail(function (xhr) {
            showAlert('danger', 'Error: ' + (xhr.responseText || xhr.status));
            renderEmpty();
        });
    }

    function wireActions() {
        // optional "Reload on Node" button
        $('#btn-reload').on('click', function (e) {
            e.preventDefault();
            $.ajax({
                url: RELOAD_URL,
                type: 'POST',
                dataType: 'json',
                headers: {
                    'X-CSRF-TOKEN': $('meta[name="csrf-token"]').attr('content')
                }
            }).done(function (res) {
                if (!res || res.success === false) {
                    showAlert('danger', (res && res.message) ? res.message : 'Reload failed');
                    return;
                }
                showAlert('success', 'Templates reloaded');
                loadList();
            }).fail(function (xhr) {
                showAlert('danger', 'Reload error: ' + (xhr.responseText || xhr.status));
            });
        });
    }

    $(document).ready(function () {
        wireActions();
        loadList();
    });
})(jQuery);

