// assets/js/admin/customnames/local.js
(() => {
    // -------- helpers --------
    const $id = (id) => document.getElementById(id);
    const parseJSON = (s, fb) => { try { return JSON.parse(s); } catch { return fb; } };
    const setStatus = (el, t, cls) => {
        if (!el) return;
        el.textContent = t;
        el.className = 'badge status-pill ' + (cls || 'bg-secondary');
    };
    const num = (v, fb) => {
        const n = Number(v);
        return Number.isFinite(n) ? n : (fb ?? 0);
    };

    // Prefer b.text for labels; fall back to legacy fields
    function getBlockText(b) {
        return String((b && (b.text ?? b.value ?? b.label)) || '');
    }
    async function withBusy(btn, workingText, task, doneText = 'Done ✓', restoreDelayMs = 900) {
        if (!btn || typeof task !== 'function') return;
        const original = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML =
            `<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>${workingText}`;
        try {
            const out = await task();
            btn.innerHTML = doneText;
            return out;
        } catch (e) {
            btn.innerHTML = 'Error';
            throw e;
        } finally {
            setTimeout(() => { btn.disabled = false; btn.innerHTML = original; }, restoreDelayMs);
        }
    }
    // --- NEW: arc angle normalization (canonical = startAngleDeg/endAngleDeg) ---
    function normalizeArcAngles(b) {
        if (!b || (String(b.type || '').toLowerCase() !== 'arc')) return b;

        const s = num((b.startAngleDeg ?? b.start), 0);
        const e = num((b.endAngleDeg   ?? b.end),   0);

        b.startAngleDeg = s;
        b.endAngleDeg   = e;

        // Keep legacy mirrors for safety with any older readers
        b.start = s;
        b.end   = e;

        return b;
    }

    // --- NEW: normalize blocks to the new schema (idempotent) ---
    function normalizeBlockToNewSchema(b) {
        if (!b || typeof b !== 'object') return b;

        // 1) Mode: prefer squeezeMode, else lift from legacy autoFixMode
        if (!b.squeezeMode && b.autoFixMode) b.squeezeMode = String(b.autoFixMode).toLowerCase();

        // 2) Windows: prefer fitWidthPx/fitBox; lift from legacy if missing
        const toN = (v) => (Number.isFinite(Number(v)) ? Number(v) : undefined);

        if ((b.fitWidthPx == null || Number.isNaN(Number(b.fitWidthPx))) && b.autoFixWidthPx != null) {
            const n = Number(b.autoFixWidthPx);
            if (Number.isFinite(n) && n > 0) b.fitWidthPx = n;
        }
        if (!b.fitBox && b.autoFixBox) {
            const bx = b.autoFixBox;
            b.fitBox = {
                leftPx:   toN(bx.leftPx)   ?? 0,
                rightPx:  toN(bx.rightPx)  ?? 0,
                topPx:    toN(bx.topPx)    ?? 0,
                bottomPx: toN(bx.bottomPx) ?? 0,
            };
        }

        // 3) Remove legacy fields so we only serialize the new schema
        delete b.autoFixMode;
        delete b.autoFixWidthPx;
        delete b.autoFixBox;

        // 4) Canonicalize squeezeMode tokens
        if (b.squeezeMode) {
            const s = String(b.squeezeMode).toLowerCase();
            b.squeezeMode = (s === 'box') ? 'box' : (s === 'height' ? 'height' : 'width');
        }

        // 5) If fitBox is meaningless, remove it
        if (b.fitBox && typeof b.fitBox === 'object') {
            const wOk = Number(b.fitBox.rightPx) > Number(b.fitBox.leftPx);
            const hOk = Number(b.fitBox.bottomPx) > Number(b.fitBox.topPx);
            if (!wOk && !hOk) delete b.fitBox;
            else {
                if (!wOk) { delete b.fitBox.leftPx; delete b.fitBox.rightPx; }
                if (!hOk) { delete b.fitBox.topPx;  delete b.fitBox.bottomPx; }
            }
        }

        // 6) Arc angle canonicalization
        normalizeArcAngles(b);

        return b;
    }
    // Elements & small utilities

    const fieldsWrap    = document.getElementById('fields-container');
    const btnFormat     = document.getElementById('format-json');
    const btnRescan     = document.getElementById('scan-fields');
    const btnPushRemote = document.getElementById('push-remote');


    function setStatusPill(text, klass) {
        if (!statusPill) return;
        statusPill.textContent = text;
        statusPill.className = 'badge ' + (klass || 'bg-secondary');
    }

    function safeParseJson(txt) {
        try { return JSON.parse(txt); } catch { return null; }
    }

    function normalizeTemplateBlocks(tpl) {
        if (!tpl || !Array.isArray(tpl.blocks)) return false;
        let changed = false;
        tpl.blocks.forEach((b) => {
            const before = JSON.stringify(b);
            normalizeBlockToNewSchema(b);
            if (before !== JSON.stringify(b)) changed = true;
        });
        return changed;
    }

    // -------- config from view --------
    const CFG  = window.TPL_LOCAL || {};
    const URLS = (CFG && CFG.urls) || {};

    // -------- cache DOM --------
    const elName = $id('tpl-name');
    const elSlug = $id('tpl-slug');
    const elJson = $id('tpl-json');
    const elData = $id('tpl-data');
    const fieldsC = $id('fields-container');
    const previewC = $id('preview-container');
    const statusPill = $id('status-pill');
    const fieldsBadge = $id('fields-badge');

    const fldWidth = $id('fld-width');
    const fldHeight = $id('fld-height');
    const fldDpi = $id('fld-dpi');
    const scName = $id('scale-name');
    const scNum = $id('scale-number');
    const scStroke = $id('scale-stroke');

    const blocksTbody = $id('blocks-tbody');

    const btnFormatJson = $id('format-json');
    const btnScanFields = $id('scan-fields');
    const btnPreview = $id('preview');
    const btnSave = $id('save');
    const btnPush = $id('push-remote');
    const btnAddField = $id('add-field');
    const inputNewKey = $id('new-field-key');
    const btnSyncFTD = $id('sync-fields-to-data');
    const btnSyncDTF = $id('sync-data-to-fields');
    const btnFormatData = $id('format-data');
    const btnAddBlock = $id('add-block');

    // -------- Modal refs --------
    const bem = {
        modalEl: $id('block-editor-modal'),
        title: $id('bem-title'),
        idx: $id('bem-index'),
        slot: $id('bem-slot'),
        type: $id('bem-type'),
        value: $id('bem-value'),
        x: $id('bem-x'),
        y: $id('bem-y'),
        fontSizePx: $id('bem-fontSizePx'),
        rotationDeg: $id('bem-rotationDeg'),
        align: $id('bem-align'),
        vAlign: $id('bem-vAlign'),
        autoFix: $id('bem-autoFix'),
        autoFixMode: $id('bem-autoFixMode'),         // UI select; maps to squeezeMode
        autoFixWidthPx: $id('bem-autoFixWidthPx'),   // UI number; maps to fitWidthPx
        letterSpacing: $id('bem-letterSpacing'),
        manualScaleX: $id('bem-manualScaleX'),
        manualScaleY: $id('bem-manualScaleY'),
        fill: $id('bem-fill'),
        stroke: $id('bem-stroke'),
        strokeWidth: $id('bem-strokeWidth'),
        boxLeft: $id('bem-box-left'),
        boxRight: $id('bem-box-right'),
        boxTop: $id('bem-box-top'),
        boxBottom: $id('bem-box-bottom'),
        saveBtn: $id('bem-save'),

        // Fonts (dropdown)
        fontSelect: $id('bem-font'),
        fontRefresh: $id('bem-font-refresh'),

        // SVG controls
        svgGroup: $id('bem-svg-group'),
        svgSource: $id('bem-svg-source'),
        svgInline: $id('bem-svg-inline'),
        svgUrl: $id('bem-svg-url'),
        svgInlineWrap: $id('bem-svg-inline-wrap'),
        svgUrlWrap: $id('bem-svg-url-wrap'),
        svgWidthPx: $id('bem-svg-widthPx'),
        svgHeightPx: $id('bem-svg-heightPx'),

        // Text/Arc extras
        dyPx: $id('bem-dyPx'),
        ringColor: $id('bem-ring-color'),        // separatedOutline.outerColor
        ringWidthPx: $id('bem-ring-widthPx'),    // separatedOutline.outerWidthPx
        ringGapPx: $id('bem-ring-gapPx'),        // separatedOutline.gapPx
        outline2Color: $id('bem-outline2-color'),// outline2.color
        outline2WidthPx: $id('bem-outline2-widthPx'), // outline2.widthPx

        // Arc geometry
        cx: $id('bem-cx'),
        cy: $id('bem-cy'),
        radiusPx: $id('bem-radiusPx'),
        startDeg: $id('bem-startDeg'), // UI fields; bind to startAngleDeg/endAngleDeg
        endDeg: $id('bem-endDeg'),
    };

    let blockModal = null;
    if (bem.modalEl && window.bootstrap && bootstrap.Modal) {
        blockModal = new bootstrap.Modal(bem.modalEl, { backdrop: 'static' });
    }

    // -------- initial JSON from inline <script> (only if textarea empty) --------
    (() => {
        const tplNode = $id('tpl-initial-json');
        const dataNode = $id('tpl-initial-data');

        if (tplNode) {
            const current = (elJson?.value || '').trim();
            if (!current) {
                const j = (() => { try { return JSON.parse(tplNode.textContent || '{}'); } catch { return {}; } })();
                elJson.value = JSON.stringify(j, null, 2);
            }
        }
        if (dataNode) {
            const currentData = (elData?.value || '').trim();
            if (!currentData) {
                const d = (() => { try { return JSON.parse(dataNode.textContent || '{}'); } catch { return {}; } })();
                elData.value = JSON.stringify(d, null, 2);
            }
        }
    })();

    // -------- JSON accessors --------
    const getTpl = () => parseJSON(elJson?.value || '{}', null);
    const setTpl = (obj) => { if (elJson) elJson.value = JSON.stringify(obj || {}, null, 2); };
    const getDataObj = () => parseJSON(elData?.value || '{}', {});
    const setDataObj = (o) => { if (elData) elData.value = JSON.stringify(o || {}, null, 2); };

    // Find the nearest column-like wrapper for a control
    function _wrap(el) {
        if (!el) return null;
        const sels = [
            '.col-12','.col-md-12','.col-md-11','.col-md-10','.col-md-9',
            '.col-md-8','.col-md-7','.col-md-6','.col-md-5','.col-md-4',
            '.col-md-3','.col-md-2','.col-md-1'
        ];
        for (const s of sels) { const p = el.closest(s); if (p) return p; }
        return el.parentElement || el;
    }

    // Show/hide all modal controls except a whitelist of IDs
    function hideAllBut(formEl, idsToShow) {
        const keep = new Set(idsToShow);
        formEl.querySelectorAll('[id^="bem-"]').forEach(el => {
            if (el.tagName === 'INPUT' && el.type === 'hidden') return;
            const grp = _wrap(el);
            if (!grp) return;
            const show = keep.has(el.id) || keep.has(grp.id);
            grp.classList.toggle('d-none', !show);
        });
    }

    function toggleTypeSections() {
        const t = (bem.type?.value || '').toLowerCase();
        const isSvg = t === 'svg';
        const isArc = t === 'arc';

        const form = document.getElementById('block-editor-form');
        if (!form) return;

        if (isSvg) {
            // keep only: Slot, Type, Rotation, SVG group
            hideAllBut(form, ['bem-slot',
                'bem-type',
                'bem-rotationDeg',
                'bem-x',          // << show X
                'bem-y',
                'bem-svg-group',
                'bem-index']);
        } else {
            // show everything, then selectively hide groups
            form.querySelectorAll('[id^="bem-"]').forEach(el => {
                if (el.tagName === 'INPUT' && el.type === 'hidden') return;
                const grp = _wrap(el);
                if (grp) grp.classList.remove('d-none');
            });

            // hide SVG group unless svg
            if (bem.svgGroup) bem.svgGroup.classList.add('d-none');

            // show/hide ARC geometry only for arc
            const arcGroup = document.getElementById('bem-arc-group');
            if (arcGroup) arcGroup.classList.toggle('d-none', !isArc);

            // nice-to-have: update value label when switching to label/text
            const lab = document.querySelector('label[for="bem-value"]');
            if (lab) lab.textContent = (t === 'label') ? 'Label Text' : 'Value (the text to render)';
            if (bem.value) bem.value.placeholder = '{{PLACEHOLDER}}';
        }
    }
    if (bem.type) bem.type.addEventListener('change', toggleTypeSections);

    // -------- field detection --------
    const extractPlaceholderKeys = (str) => {
        if (typeof str !== 'string') return [];
        const out = new Set();
        const re2 = /\{\{([A-Za-z_][\w.-]*)\}\}/g; // {{KEY}}
        const re1 = /\{([A-Za-z_][\w.-]*)\}/g;     // {KEY}  (legacy)
        let m, found = false;
        while ((m = re2.exec(str))) { out.add(m[1]); found = true; }
        if (!found) { while ((m = re1.exec(str))) out.add(m[1]); }
        return Array.from(out);
    };
    const normalizeKey = (s) => String(s || '').trim().replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '');
    const keyFromSlotOrType = (b, i) =>
        (b && b.slot) ? normalizeKey(b.slot) : ((b && b.type ? b.type : 'field') + '_' + (i + 1)).toLowerCase();

    const collectFieldKeysFromTemplate = (tpl) => {
        const keys = [], seen = new Set();
        if (!tpl || !Array.isArray(tpl.blocks)) return [];
        tpl.blocks.forEach((b, i) => {
            const type = (b && (b.type || '')).toLowerCase();
            if (type === 'text' || type === 'label' || type === 'arc') {
                const bucket = [];
                ['field', 'dataField', 'data_key'].forEach(p => {
                    if (typeof b[p] === 'string' && b[p].trim()) bucket.push(b[p].trim());
                });
                ['value', 'label', 'text', 'name'].forEach(p => {
                    if (typeof b[p] === 'string') extractPlaceholderKeys(b[p]).forEach(k => bucket.push(k));
                });
                if (!bucket.length) bucket.push(keyFromSlotOrType(b, i));
                bucket.forEach(k => {
                    const n = normalizeKey(k);
                    if (n && !seen.has(n)) { seen.add(n); keys.push(n); }
                });
            }
        });
        return keys;
    };

    // -------- fonts loader --------
    let _fontsLoaded = false;

    function _slugifyFont(s) {
        return String(s || '').trim().toLowerCase().replace(/[\s_]+/g, '-');
    }

    function _normalizeFontRecord(f) {
        if (typeof f === 'string') {
            const name = f;
            const slug = _slugifyFont(name);
            return { slug, label: name };
        }
        const slug = String(
            f.id || f.family || f.slug || _slugifyFont(f.name || '')
        );
        const label = String(f.name || f.family || slug || '');
        return { slug, label };
    }

    function _setFontSelection(target) {
        if (!bem.fontSelect) return;
        const want = (target || '').trim();
        if (!want) { bem.fontSelect.value = ''; return; }

        const opts = [...bem.fontSelect.options];

        if (opts.some(o => o.value === want)) { bem.fontSelect.value = want; return; }
        const m1 = opts.find(o => (o.dataset.slug || '') === want);
        if (m1) { bem.fontSelect.value = m1.value; return; }
        const m2 = opts.find(o => _slugifyFont(o.textContent) === want);
        if (m2) { bem.fontSelect.value = m2.value; return; }
        const m3 = opts.find(o => o.textContent.includes(`(${want})`));
        if (m3) { bem.fontSelect.value = m3.value; return; }
    }

    async function fetchFontsOnce(force = false) {
        if (_fontsLoaded && !force) return;

        const url = (window.__TB_URLS && window.__TB_URLS.fonts) || '/admin/customnames/local/fonts';
        try {
            const resp = await fetch(url, { headers: { 'Accept': 'application/json' } });
            const json = await resp.json();
            const list = Array.isArray(json) ? json : (Array.isArray(json.fonts) ? json.fonts : []);

            if (bem.fontSelect) {
                const current = bem.fontSelect.value;
                for (let i = bem.fontSelect.options.length - 1; i >= 1; i--) {
                    bem.fontSelect.remove(i);
                }
                list.forEach(f => {
                    const { slug, label } = _normalizeFontRecord(f);
                    if (!slug) return;
                    const opt = document.createElement('option');
                    opt.value = slug;
                    opt.dataset.slug = slug;
                    opt.textContent = (label && slug && label !== slug)
                        ? `${label} (${slug})`
                        : (label || slug);
                    bem.fontSelect.appendChild(opt);
                });
                if (current && [...bem.fontSelect.options].some(o => o.value === current)) {
                    bem.fontSelect.value = current;
                }
            }

            _fontsLoaded = true;
        } catch (e) {
            console.warn('Failed to load fonts', e);
        }
    }
    if (bem.fontRefresh) bem.fontRefresh.addEventListener('click', () => fetchFontsOnce(true));

    // -------- SVG panel visibility --------
    function toggleSvgEditorVisibility() {
        const isSvg = (bem.type?.value || '').toLowerCase() === 'svg';
        if (!bem.svgGroup) return;
        bem.svgGroup.classList.toggle('d-none', !isSvg);
    }
    if (bem.type) bem.type.addEventListener('change', toggleSvgEditorVisibility);
    if (bem.svgSource) {
        bem.svgSource.addEventListener('change', () => {
            const v = bem.svgSource.value;
            if (bem.svgInlineWrap) bem.svgInlineWrap.classList.toggle('d-none', v !== 'inline');
            if (bem.svgUrlWrap) bem.svgUrlWrap.classList.toggle('d-none', v !== 'url');
        });
    }

    // -------- UI: fields list --------
    function updateFieldsBadge(n) {
        if (!fieldsBadge) return;
        fieldsBadge.textContent = `Detected ${n} field${n === 1 ? '' : 's'}`;
        fieldsBadge.classList.remove('d-none');
    }

    function renderFields(keys, values) {
        if (!fieldsC) return;
        fieldsC.innerHTML = '';
        if (!keys || !keys.length) {
            fieldsC.innerHTML = '<em class="text-muted">No fields detected yet.</em>';
            return;
        }
        keys.forEach(k => {
            const v = (values && Object.prototype.hasOwnProperty.call(values, k)) ? values[k] : '';
            const row = document.createElement('div');
            row.className = 'field-row input-group';
            row.innerHTML = `
        <span class="input-group-text" style="min-width:120px">${k}</span>
        <input data-key="${k}" type="text" class="form-control" placeholder="{{${k}}}" value="${String(v).replace(/"/g, '&quot;')}">
        <button type="button" class="btn btn-outline-danger remove-field" data-key="${k}">
          <i class="fa fa-times"></i>
        </button>`;
            fieldsC.appendChild(row);

            row.querySelector('input[data-key]').addEventListener('input', (inpEvt) => {
                const inp = inpEvt.currentTarget;
                const data = getDataObj();
                data[inp.dataset.key] = inp.value;
                setDataObj(data);
            });

            row.querySelector('.remove-field').addEventListener('click', (btnEvt) => {
                const k2 = btnEvt.currentTarget.dataset.key;
                const data = getDataObj();
                delete data[k2];
                setDataObj(data);
                renderFields(Object.keys(data), data);
            });
        });
    }

    // -------- UI: blocks table --------
    function renderBlocksTable(blocks) {
        if (!blocksTbody) return;
        if (!blocks || !blocks.length) {
            blocksTbody.innerHTML = '<tr><td colspan="7" class="text-muted text-center py-3">No blocks yet.</td></tr>';
            return;
        }
        blocksTbody.innerHTML = '';
        blocks.forEach((b, idx) => {
            const type = (b.type || 'text').toLowerCase();
            const pos = `x:${b.x ?? 0}, y:${b.y ?? 0}`;
            const size = (type === 'svg')
                ? `${b.widthPx || '-'}×${b.heightPx || '-'}`
                : ((b.fontSizePx != null) ? `fsz:${b.fontSizePx}` : '-');

            const more = (type === 'svg')
                ? (b.url || b.svg ? 'svg: set' : 'svg: —')
                : [
                b.align ? `a:${b.align}` : null,
                b.autoFix ? `fit:${(b.squeezeMode || 'width')}` : null,
                (Number(b.fitWidthPx) > 0 ? `w:${b.fitWidthPx}` : null),
                (b.fitBox && Number(b.fitBox.leftPx) < Number(b.fitBox.rightPx)
                    ? `box:${b.fitBox.leftPx}-${b.fitBox.rightPx}`
                    : null)
            ].filter(Boolean).join(' ') || '-';

            const tr = document.createElement('tr');
            tr.innerHTML = `
        <td><input class="form-control slot" value="${(b.slot || '').replace(/"/g, '&quot;')}" /></td>
        <td>
          <select class="form-select type">
            <option value="text"${type === 'text' ? ' selected' : ''}>text</option>
            <option value="label"${type === 'label' ? ' selected' : ''}>label</option>
            <option value="arc"${type === 'arc' ? ' selected' : ''}>arc</option>
            <option value="svg"${type === 'svg' ? ' selected' : ''}>svg</option>
          </select>
        </td>
        <td><input class="form-control val" placeholder="${type === 'label' ? '{{PLACEHOLDER}}' : 'value'}" value="${getBlockText(b).replace(/"/g, '&quot;')}" /></td>
        <td><span class="pos-pill">${pos}</span></td>
        <td><span class="size-pill">${size}</span></td>
        <td><span class="more-pill">${more}</span></td>
        <td class="text-end">
          <button class="btn btn-sm btn-outline-secondary edit-adv"><i class="fa fa-sliders-h"></i> Edit</button>
          <button class="btn btn-sm btn-outline-danger ms-1 remove"><i class="fa fa-times"></i></button>
        </td>`;
            blocksTbody.appendChild(tr);

            tr.querySelector('.slot').addEventListener('change', (e) => {
                patchTpl(tpl => { tpl.blocks[idx].slot = e.target.value; });
                setStatus(statusPill, 'Block updated', 'bg-secondary');
                resyncDetectedFields();
            });

            tr.querySelector('.type').addEventListener('change', (e) => {
                const newType = e.target.value.toLowerCase();
                patchTpl(tpl => {
                    const blk = tpl.blocks[idx];
                    blk.type = newType;
                    if (newType === 'label') {
                        blk.text = blk.text || blk.value || blk.label || '';
                        delete blk.value;
                        delete blk.label;
                    } else if (newType === 'text' || newType === 'arc') {
                        blk.value = blk.value || blk.text || blk.label || '';
                        delete blk.text;
                        delete blk.label;
                    }
                    normalizeBlockToNewSchema(blk);
                });
                setStatus(statusPill, 'Block type changed', 'bg-secondary');
                renderBlocksTable(getTpl().blocks || []);
                resyncDetectedFields();
            });

            tr.querySelector('.val').addEventListener('input', (e) => {
                patchTpl(tpl => {
                    const blk = tpl.blocks[idx];
                    const t = (blk.type || 'text').toLowerCase();
                    if (t === 'label') { blk.text = e.target.value; delete blk.label; }
                    else if (t === 'text' || t === 'arc') { blk.value = e.target.value; }
                });
                setStatus(statusPill, 'Block value changed', 'bg-secondary');
            });

            tr.querySelector('.edit-adv').addEventListener('click', async () => {
                await fetchFontsOnce();
                openBlockEditor(idx);
            });

            tr.querySelector('.remove').addEventListener('click', () => {
                if (!confirm('Remove this block?')) return;
                patchTpl(tpl => { tpl.blocks.splice(idx, 1); });
                renderBlocksTable(getTpl().blocks || []);
                resyncDetectedFields();
            });
        });
    }

    // -------- patch & canvas binding --------
    function patchTpl(mutator) {
        const tpl = getTpl();
        if (!tpl) return false;
        mutator(tpl);
        setTpl(tpl);
        return true;
    }

    const onCanvasChange = () => {
        patchTpl(tpl => {
            tpl.widthIn = parseFloat(fldWidth?.value) || 0;
            tpl.heightIn = parseFloat(fldHeight?.value) || 0;
            tpl.dpi = parseInt(fldDpi?.value, 10) || 300;
            tpl.scaling = tpl.scaling || {};
            tpl.scaling.name = parseFloat(scName?.value) || 1;
            tpl.scaling.number = parseFloat(scNum?.value) || 1;
            tpl.scaling.scaleStroke = !!(scStroke && scStroke.checked);
        });
        setStatus(statusPill, 'Canvas updated', 'bg-secondary');
    };
    [fldWidth, fldHeight, fldDpi, scName, scNum].forEach(el => el && el.addEventListener('change', onCanvasChange));
    if (scStroke) scStroke.addEventListener('change', onCanvasChange);

    // -------- Block editor modal --------
    function openBlockEditor(index) {
        const creating = (index == null || index < 0);
        const tpl = getTpl();
        if (!tpl) return;

        const defaultBlock = {
            slot: '', type: 'text',
            x: 600, y: 300,
            fontSizePx: 240, align: 'center', vAlign: 'baseline',
            rotationDeg: 0, value: '',
            letterSpacing: 0, manualScaleX: 1, manualScaleY: 1,
            autoFix: false,
            squeezeMode: 'width',        // NEW canonical
            fitWidthPx: 0,               // NEW canonical
            fitBox: { leftPx: 0, rightPx: 0, topPx: 0, bottomPx: 0 }, // NEW canonical
            fill: '#000000', stroke: '#ffffff', strokeWidth: 0, font: '',
            dyPx: 0,
            // outlines
            separatedOutline: { outerColor: '', outerWidthPx: 0, gapPx: 0 },
            outline2: { color: '', widthPx: 0 },
            // arc defaults
            cx: 0, cy: 0, radiusPx: 0, startAngleDeg: 0, endAngleDeg: 0, start: 0, end: 0
        };

        const blk = creating ? defaultBlock : (tpl.blocks || [])[index];
        if (!blk) return;

        // Normalize the block we are about to edit (lifts legacy ➜ new; removes legacy keys; fixes arc angles)
        normalizeBlockToNewSchema(blk);

        if (!bem.type) {
            console.warn('Block editor: type select missing (id="bem-type")');
            return;
        }

        // Header
        bem.idx.value = creating ? -1 : index;
        bem.title.textContent = creating ? 'Add Block' : `Edit Block ${index + 1}: ${blk.slot || blk.type || ''}`;

        // Base fields
        bem.slot && (bem.slot.value = blk.slot || '');
        bem.type.value = (blk.type || 'text').toLowerCase();
        toggleTypeSections();

        // Fonts dropdown (async)
        fetchFontsOnce().then(() => {
            _setFontSelection(blk.font || '');
        });
        const isLabel = (bem.type.value === 'label');
        const isArc   = (bem.type.value === 'arc');
        const lblValueEl = document.querySelector('label[for="bem-value"]');

        // Value field
        if (bem.value) {
            if (lblValueEl) lblValueEl.textContent = isLabel ? 'Label Text' : 'Value (the text to render)';
            bem.value.placeholder = isLabel ? 'Label Text' : 'If set, this overrides slot data';
            bem.value.value = isLabel ? (blk.text ?? blk.label ?? '') : (blk.value ?? '');
        }

        // Geometry, typography, transform
        if (bem.x) bem.x.value = blk.x ?? 0;
        if (bem.y) bem.y.value = blk.y ?? 0;
        if (bem.fontSizePx) bem.fontSizePx.value = blk.fontSizePx ?? 0;
        if (bem.rotationDeg) bem.rotationDeg.value = blk.rotationDeg ?? 0;
        if (bem.align) bem.align.value = blk.align || 'left';
        if (bem.vAlign) bem.vAlign.value = blk.vAlign || 'baseline';
        if (bem.letterSpacing) bem.letterSpacing.value = blk.letterSpacing ?? 0;
        if (bem.manualScaleX) bem.manualScaleX.value = blk.manualScaleX ?? 1;
        if (bem.manualScaleY) bem.manualScaleY.value = blk.manualScaleY ?? 1;
        if (bem.dyPx) bem.dyPx.value = blk.dyPx ?? 0;

        // Autofit / fit (new schema mapped onto existing UI controls)
        if (bem.autoFix) bem.autoFix.checked = !!blk.autoFix;
        if (bem.autoFixMode) bem.autoFixMode.value = (blk.squeezeMode || '').toLowerCase();      // maps to squeezeMode
        if (bem.autoFixWidthPx) bem.autoFixWidthPx.value = Number(blk.fitWidthPx || 0);          // maps to fitWidthPx
        const box = blk.fitBox || {};
        if (bem.boxLeft)   bem.boxLeft.value   = box.leftPx   ?? 0;
        if (bem.boxRight)  bem.boxRight.value  = box.rightPx  ?? 0;
        if (bem.boxTop)    bem.boxTop.value    = box.topPx    ?? 0;
        if (bem.boxBottom) bem.boxBottom.value = box.bottomPx ?? 0;

        // Paint / outlines
        if (bem.fill) bem.fill.value = blk.fill || '';
        if (bem.stroke) bem.stroke.value = blk.stroke || '';
        if (bem.strokeWidth) bem.strokeWidth.value = blk.strokeWidth ?? 0;

        const sep = blk.separatedOutline || {};
        if (bem.ringColor) bem.ringColor.value = sep.outerColor || '';
        if (bem.ringWidthPx) bem.ringWidthPx.value = sep.outerWidthPx ?? 0;
        if (bem.ringGapPx) bem.ringGapPx.value = sep.gapPx ?? 0;

        const o2 = blk.outline2 || {};
        if (bem.outline2Color) bem.outline2Color.value = o2.color || '';
        if (bem.outline2WidthPx) bem.outline2WidthPx.value = o2.widthPx ?? 0;

        // Arc-only geometry (bind UI to canonical startAngleDeg/endAngleDeg)
        if (isArc) {
            if (bem.cx) bem.cx.value = blk.cx ?? 0;
            if (bem.cy) bem.cy.value = blk.cy ?? 0;
            if (bem.radiusPx) bem.radiusPx.value = blk.radiusPx ?? 0;
            if (bem.startDeg) bem.startDeg.value = blk.startAngleDeg ?? blk.start ?? 0;
            if (bem.endDeg) bem.endDeg.value = blk.endAngleDeg ?? blk.end ?? 0;
        } else {
            // ensure arc props don’t linger on other types
            delete blk.cx; delete blk.cy; delete blk.radiusPx;
            delete blk.startAngleDeg; delete blk.endAngleDeg;
            delete blk.start; delete blk.end;
        }

        // SVG editor visibility (local supports inline/url + width/height)
        toggleSvgEditorVisibility();
        if (bem.svgSource) {
            const hasInline = !!(blk.svg || blk.svgInline || blk.svgMarkup);
            bem.svgSource.value = hasInline ? 'inline' : 'url';
            if (bem.svgInlineWrap) bem.svgInlineWrap.classList.toggle('d-none', !hasInline);
            if (bem.svgUrlWrap) bem.svgUrlWrap.classList.toggle('d-none', hasInline);
        }
        if (bem.svgInline) bem.svgInline.value = blk.svg || blk.svgInline || blk.svgMarkup || '';
        if (bem.svgUrl) bem.svgUrl.value = blk.url || blk.svgUrl || '';
        if (bem.svgWidthPx) bem.svgWidthPx.value = blk.widthPx ?? '';
        if (bem.svgHeightPx) bem.svgHeightPx.value = blk.heightPx ?? '';

        if (blockModal) blockModal.show();
        else if (bem.modalEl) bem.modalEl.style.display = 'block';
        (async () => {
            await fetchPaletteOnce(); // warm cache

            const pickFill   = makeColorButton(bem.fill, 'Fill');
            const pickStroke = makeColorButton(bem.stroke, 'Outline');
            const pickO2     = makeColorButton(bem.outline2Color, 'Outline 2');
            const pickRing   = makeColorButton(bem.ringColor, 'Ring');

            wireRingExclusivity(bem.ringColor, bem.stroke, bem.outline2Color);
        })();
    }

    function saveBlockFromModal() {
        const idx = parseInt(bem.idx.value, 10);
        const creating = (idx < 0);
        const type = (bem.type?.value || 'text').toLowerCase();

        const patch = {
            slot: (bem.slot?.value || '').trim(),
            type,
            x: parseInt(bem.x?.value || '0', 10),
            y: parseInt(bem.y?.value || '0', 10),
            fontSizePx: parseInt(bem.fontSizePx?.value || '0', 10),
            rotationDeg: parseInt(bem.rotationDeg?.value || '0', 10),
            align: bem.align?.value || 'left',
            vAlign: bem.vAlign?.value || 'baseline',
            letterSpacing: parseInt(bem.letterSpacing?.value || '0', 10),
            manualScaleX: parseFloat(bem.manualScaleX?.value || '1') || 1,
            manualScaleY: parseFloat(bem.manualScaleY?.value || '1') || 1,
            autoFix: !!bem.autoFix?.checked,

            // write new canonical fields
            squeezeMode: (bem.autoFixMode?.value || '').toLowerCase(),  // 'width' | 'box' | 'height'
            fitWidthPx: parseInt(bem.autoFixWidthPx?.value || '0', 10) || 0,
            fitBox: {
                leftPx: parseInt(bem.boxLeft?.value   || '0', 10) || 0,
                rightPx: parseInt(bem.boxRight?.value || '0', 10) || 0,
                topPx: parseInt(bem.boxTop?.value     || '0', 10) || 0,
                bottomPx: parseInt(bem.boxBottom?.value || '0', 10) || 0,
            },

            fill: (bem.fill?.value || '').trim(),
            stroke: (bem.stroke?.value || '').trim(),
            strokeWidth: parseInt(bem.strokeWidth?.value || '0', 10),
            font: (bem.fontSelect && bem.fontSelect.value) ? bem.fontSelect.value : '',
            dyPx: parseInt(bem.dyPx?.value || '0', 10) || 0,
        };

        // Label/text value
        const v = bem.value?.value || '';
        if (type === 'label') {
            patch.text = v;
            patch.value = undefined;
            patch.label = undefined;
        } else if (type === 'text' || type === 'arc') {
            patch.value = v;
            patch.text = undefined;
            patch.label = undefined;
        }

        // Arc geometry (canonical: startAngleDeg/endAngleDeg, with legacy mirrors)
        if (type === 'arc') {
            patch.cx = parseInt(bem.cx?.value || '0', 10) || 0;
            patch.cy = parseInt(bem.cy?.value || '0', 10) || 0;
            patch.radiusPx = parseInt(bem.radiusPx?.value || '0', 10) || 0;

            const s = num(bem.startDeg?.value, 0);
            const e = num(bem.endDeg?.value, 0);

            patch.startAngleDeg = s;
            patch.endAngleDeg   = e;

            // keep mirrors for older consumers
            patch.start = s;
            patch.end   = e;
        } else {
            delete patch.cx; delete patch.cy; delete patch.radiusPx;
            delete patch.startAngleDeg; delete patch.endAngleDeg;
            delete patch.start; delete patch.end;
        }

        // Separated outline (Ring) & Outline2
        const so = {
            outerColor: (bem.ringColor?.value || '').trim(),
            outerWidthPx: parseInt(bem.ringWidthPx?.value || '0', 10) || 0,
            gapPx: parseInt(bem.ringGapPx?.value || '0', 10) || 0,
        };
        const o2 = {
            color: (bem.outline2Color?.value || '').trim(),
            widthPx: parseInt(bem.outline2WidthPx?.value || '0', 10) || 0,
        };
        patch.separatedOutline = (so.outerColor || so.outerWidthPx || so.gapPx) ? so : { outerColor: '', outerWidthPx: 0, gapPx: 0 };
        patch.outline2 = (o2.color || o2.widthPx) ? o2 : { color: '', widthPx: 0 };

        // SVG
        if (type === 'svg') {
            const src = bem.svgSource ? bem.svgSource.value : 'inline';
            const w = parseInt(bem.svgWidthPx?.value || '0', 10);
            const h = parseInt(bem.svgHeightPx?.value || '0', 10);
            if (src === 'inline') {
                patch.svg = bem.svgInline?.value || '';
                patch.svgInline = patch.svg;
                patch.url = patch.svgUrl = undefined;
            } else {
                patch.url = bem.svgUrl?.value || '';
                patch.svgUrl = patch.url;
                patch.svg = patch.svgInline = undefined;
            }
            if (!Number.isNaN(w) && w > 0) patch.widthPx = w; else delete patch.widthPx;
            if (!Number.isNaN(h) && h > 0) patch.heightPx = h; else delete patch.heightPx;
        } else {
            delete patch.svg; delete patch.svgInline; delete patch.url; delete patch.svgUrl;
            delete patch.widthPx; delete patch.heightPx;
        }

        // Post-process patch: canonicalize and remove legacy keys; tidy fitBox; fix arc angles
        normalizeBlockToNewSchema(patch);

        patchTpl(tpl => {
            tpl.blocks = Array.isArray(tpl.blocks) ? tpl.blocks : [];
            if (creating) tpl.blocks.push(patch);
            else Object.assign(tpl.blocks[idx], patch);
        });

        renderBlocksTable(getTpl().blocks || []);
        resyncDetectedFields();
        setStatus(statusPill, creating ? 'Block added' : 'Block updated', 'bg-info');

        if (blockModal) blockModal.hide();
        else if (bem.modalEl) bem.modalEl.style.display = 'none';
    }

    // -------- scan everything & populate UI --------
    // One-time migration: convert legacy {label:"..."} to {text:"..."} for label blocks
    function migrateLabelToText(tpl) {
        let changed = false;
        (tpl.blocks || []).forEach(b => {
            if ((b.type || '').toLowerCase() === 'label' && b.label != null && b.text == null) {
                b.text = b.label;
                delete b.label;
                changed = true;
            }
        });
        return changed;
    }

    function scanAndPopulate() {
        const tpl = getTpl();
        if (!tpl) {
            setStatus(statusPill, 'Invalid template JSON', 'bg-danger');
            return;
        }

        if (migrateLabelToText(tpl)) setTpl(tpl);

        // NEW: migrate any legacy autofit fields AND arc angles to the new schema on load
        if (normalizeTemplateBlocks(tpl)) setTpl(tpl);

        if (fldWidth) fldWidth.value = tpl.widthIn ?? '';
        if (fldHeight) fldHeight.value = tpl.heightIn ?? '';
        if (fldDpi) fldDpi.value = tpl.dpi ?? '';
        const sc = tpl.scaling || {};
        if (scName) scName.value = sc.name ?? 1;
        if (scNum) scNum.value = sc.number ?? 1;
        if (scStroke) scStroke.checked = !!sc.scaleStroke;

        renderBlocksTable(tpl.blocks || []);
        resyncDetectedFields();

        setStatus(statusPill, 'Ready', 'bg-success');
    }

    function resyncDetectedFields() {
        const tpl = getTpl();
        if (!tpl) return;
        const detected = collectFieldKeysFromTemplate(tpl);
        const data = getDataObj();
        detected.forEach(k => { if (!Object.prototype.hasOwnProperty.call(data, k)) data[k] = ''; });
        const allKeys = Array.from(new Set([...detected, ...Object.keys(data)]));
        setDataObj(data);
        renderFields(allKeys, data);
        updateFieldsBadge(detected.length);
    }

    // -------- NEW: preview payload bridge (TB + legacy) --------
    function buildPreviewRequestBody(tplJson, data, id) {
        const src = (data && typeof data === 'object') ? data : {};
        const outData = { ...src };
        const dpi = (tplJson && Number.isFinite(tplJson.dpi)) ? tplJson.dpi : 300;

        // Ensure angles are canonical before preview (safety)
        if (normalizeTemplateBlocks(tplJson)) {
            // reflect any normalization back into textarea to keep UI in sync
            setTpl(tplJson);
        }

        return {
            template_inline: tplJson,
            data: outData,
            format: 'png',
            preserveCase: true,
            embedFonts: true,
            dpi,
            debug: false,
        };
    }

    // -------- controls --------
    if (btnFormatJson) {
        btnFormatJson.addEventListener('click', async () => {
            await withBusy(btnFormatJson, 'Formatting…', async () => {
                const obj = parseJSON(elJson.value, null);
                if (!obj) { setStatus(statusPill, 'Invalid JSON', 'bg-danger'); throw new Error('Invalid JSON'); }
                elJson.value = JSON.stringify(obj, null, 2);
                setStatus(statusPill, 'JSON formatted', 'bg-success');
            }, 'Formatted ✓');
        });
    }


    if (btnScanFields) {
        btnScanFields.addEventListener('click', async () => {
            await withBusy(btnScanFields, 'Scanning…', async () => {
                const tpl = getTpl();
                if (!tpl) { setStatus(statusPill, 'Invalid template JSON', 'bg-danger'); throw new Error('Invalid template'); }
                // keep blocks as-is; just re-detect and repaint fields
                resyncDetectedFields();
                setStatus(statusPill, 'Fields updated', 'bg-success');
            }, 'Done ✓');
        });
    }

    if (btnAddField) btnAddField.addEventListener('click', () => {
        const k = (inputNewKey?.value || '').trim();
        if (!k) return;
        const n = k.replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '').toLowerCase();
        const data = getDataObj();
        if (!Object.prototype.hasOwnProperty.call(data, n)) data[n] = '';
        setDataObj(data);
        renderFields(Object.keys(data), data);
        if (inputNewKey) inputNewKey.value = '';
    });

    if (btnSyncFTD) btnSyncFTD.addEventListener('click', () => setStatus(statusPill, 'Synced fields ▶ data', 'bg-secondary'));
    if (btnSyncDTF) btnSyncDTF.addEventListener('click', () => {
        const data = getDataObj();
        renderFields(Object.keys(data), data);
        setStatus(statusPill, 'Synced data ▶ fields', 'bg-secondary');
    });

    if (btnFormatData) btnFormatData.addEventListener('click', () => {
        const obj = getDataObj();
        setDataObj(obj);
        setStatus(statusPill, 'Formatted data', 'bg-info');
    });

    // -------- preview --------
    if (btnPreview) btnPreview.addEventListener('click', async () => {
        await withBusy(btnPreview, 'Preparing preview…', async () => {
            setStatus(statusPill, 'Preparing preview…', 'bg-secondary');
            if (previewC) previewC.innerHTML = '<em>Loading…</em>';

            const tpl = getTpl();
            if (!tpl) { alert('Invalid template JSON'); setStatus(statusPill, 'Error', 'bg-danger'); return; }

            const data = getDataObj();
            const body = buildPreviewRequestBody(tpl, data, CFG.id);

            try {
                const resp = await fetch(URLS.preview, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                    body: JSON.stringify(body)
                });

                const out = await resp.json().catch(() => ({}));
                const success = !!(out && out.success);
                const url = (out && out.url) || (out && out.data && out.data.url) || null;

                if (success && url) {
                    const isSvg = /\.svg($|\?)/i.test(url);
                    if (previewC) {
                        previewC.innerHTML = isSvg
                            ? `<object data="${url}" type="image/svg+xml" style="width:100%;min-height:360px;border:1px solid #ddd;border-radius:.5rem;"></object>`
                            : `<img src="${url}" class="img-fluid border rounded" />`;
                    }
                    setStatus(statusPill, 'Preview Ready', 'bg-success');
                } else {
                    const msg = (out && (out.message || out.error)) || `HTTP ${resp.status}`;
                    throw new Error(msg);
                }
            } catch (e) {
                setStatus(statusPill, 'Error', 'bg-danger');
                if (previewC) previewC.innerHTML = '<em>Preview failed.</em>';
                alert('Preview failed: ' + e.message);
            }
        }, 'Ready ✓');
    });

    // -------- save --------
    if (btnSave) btnSave.addEventListener('click', async () => {
        await withBusy(btnSave, 'Saving…', async () => {
            const name = (elName?.value || '').trim();
            const slug = (elSlug?.value || '').trim();
            if (!slug) { alert('Slug is required.'); return; }
            const tpl = getTpl();
            if (!tpl) { alert('Invalid template JSON'); return; }

            // Normalize blocks (includes arc angles) before save
            if (normalizeTemplateBlocks(tpl)) setTpl(tpl);

            setStatus(statusPill, 'Saving…', 'bg-secondary');
            const resp = await fetch(URLS.save, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify({ id: CFG.id ?? null, name, slug, json: tpl })
            });
            const out = await resp.json();

            if (out && out.success) {
                setStatus(statusPill, 'Saved', 'bg-success');
                if ((CFG.id == null) && out.id) {
                    window.location.href = window.location.pathname.replace(/\/add(?:\/)?$/, '/edit/' + out.id);
                }
            } else {
                throw new Error((out && (out.message || out.error)) || 'Unknown error');
            }
        }, 'Saved ✓');
    });

    // -------- push --------
    if (btnPush) btnPush.addEventListener('click', async () => {
        if (CFG.id == null) { alert('Save the template first.'); return; }
        setStatus(statusPill, 'Pushing to Remote…', 'bg-secondary');
        try {
            const resp = await fetch(URLS.push, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify({ id: CFG.id })
            });
            const out = await resp.json();
            if (out && out.success) {
                setStatus(statusPill, 'Pushed', 'bg-success');
                alert('Pushed to remote as slug: ' + (out.slug || '(unknown)'));
            } else {
                throw new Error((out && (out.message || out.error)) || 'Unknown error');
            }
        } catch (e) {
            setStatus(statusPill, 'Error', 'bg-danger');
            alert('Push failed: ' + e.message);
        }
    });

    // Add Block -> open modal (create mode)
    if (btnAddBlock) btnAddBlock.addEventListener('click', async () => {
        await fetchFontsOnce();
        openBlockEditor(-1);
    });

    // Modal Save
    if (bem.saveBtn) bem.saveBtn.addEventListener('click', saveBlockFromModal);

    // -------- robust boot --------
    const boot = () => {
        try {
            scanAndPopulate();
            fetchFontsOnce().catch(() => {});
            btnFormatJson && btnFormatJson.click();
        } catch (e) {
            console.error('Init error:', e);
            const sp = $id('status-pill');
            if (sp) {
                sp.textContent = 'Init error';
                sp.className = 'badge status-pill bg-danger';
            }
        }
    };
    (() => {
        const ocEl = document.getElementById('offcanvas-colors');
        if (!ocEl || !window.bootstrap) return;

        // Make sure offcanvas is in <body> (not inside modal DOM)
        if (ocEl.parentElement !== document.body) document.body.appendChild(ocEl);

        ocEl.addEventListener('shown.bs.offcanvas', () => {
            // Tag the backdrop so our CSS can raise it above the modal
            const b = document.querySelector('.offcanvas-backdrop');
            if (b) b.classList.add('nl-cc');
        });

        ocEl.addEventListener('hidden.bs.offcanvas', () => {
            // Clean up so other offcanvas components are unaffected
            const b = document.querySelector('.offcanvas-backdrop.nl-cc');
            if (b) b.classList.remove('nl-cc');
        });
    })();
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
    else boot();
})();
