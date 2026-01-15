// public/assets/js/teamcustomization/index.js
(function () {
    const cfg = (window.__TCFG || {});
    const urls = cfg.urls || {};
    const ORDER_QTY_KEY = '__order_quantity__';
    const els = {
        // Top controls
        tpl: document.getElementById('tc-template'),
        addRow: document.getElementById('tc-add-row'),
        preview: document.getElementById('tc-preview'),
        run: document.getElementById('tc-run'),
        gridEmpty: document.getElementById('tc-grid-empty'),
        grid: document.getElementById('tc-grid'),
        head: document.getElementById('tc-grid-head'),
        body: document.getElementById('tc-grid-body'),
        bar: document.getElementById('tc-progress'),
        log: document.getElementById('tc-log'),

        // Per-block controls table (3 columns: Block | Mode | Colors/Controls)
        blockRows: document.getElementById('tc-block-rows'),

        // Fonts (per textual block)
        fontRows: document.getElementById('tc-font-rows'),

        // CSV offcanvas + controls
        csvBtn: document.getElementById('tc-import-csv'),
        csvFile: document.getElementById('csv-file'),
        csvSample: document.getElementById('csv-sample'),
        csvAddSelected: document.getElementById('csv-add-selected'),
        csvTable: document.getElementById('csv-preview-table'),
        csvOffcanvas: document.getElementById('offcanvas-csv'),

        // Mapping area (above CSV preview)
        csvMapWrap: document.getElementById('csv-map-wrap'),
        csvMapBody: document.getElementById('csv-map-body'),

        // Color offcanvas mount (right side)
        colorOffcanvasMount: document.getElementById('nl-cc-offcanvas-container'),


    };
    const delBtn = document.getElementById('tc-delete-all');
    const addBtn = document.getElementById('tc-add-row-inline');
    if (addBtn && !addBtn.dataset.bound) {
        addBtn.addEventListener('click', () => addRow());
        addBtn.dataset.bound = '1';
    }
    if (delBtn && !delBtn.dataset.bound) {
        delBtn.addEventListener('click', clearAllRows);
        delBtn.dataset.bound = '1';
    }
    // ---------- State ----------
    const TCState = {
        fonts: [],
        palette: [],              // [{id,name,hex,is_global}]
        baseTemplate: null,
        activeTemplate: null,
        quick: {
            // Per-block overrides:
            // blocks[slot] = { mode, colors:{fill,outline,outline2,ring}, strokeWidth, ringWidth, ringGap }
            blocks: {},
            fontsBySlot: {}
        },
        placeholders: [],         // textual slots only
        rows: [],
        selectedRow: -1,
    };

    // CSV working state
    const CSV_STATE = {headers: [], rows: []};

    // ---------- Helpers ----------
    const clone = (o) => JSON.parse(JSON.stringify(o));

    // Treat these as textual blocks (font/color editable)
    const TEXTUAL_TYPES = new Set([
        'text', 'svg_text', 'arc', 'label', 'arc_text', 'curved_text', 'text_label'
    ]);
    const isTextualBlock = (b) => TEXTUAL_TYPES.has(String(b.type || '').toLowerCase());
    const isSvgNonTextBlock = (b) => {
        const t = (b.type || '').toLowerCase();
        return t.startsWith('svg') && t !== 'svg_text';
    };

    function setBar(done, total) {
        const pct = total ? Math.round((done / total) * 100) : 0;
        if (els.bar) {
            els.bar.style.width = pct + '%';
            els.bar.textContent = pct + '%';
        }
    }

    function findSlotName(tpl, wanted) {
        const w = String(wanted).toLowerCase();
        const hit = (tpl.blocks || []).find(b => b.slot && String(b.slot).toLowerCase() === w);
        return hit ? hit.slot : null;
    }

    // Build a style object for HN from a per-block quick config
    function styleFromQuick(q) {
        const s = {};
        if (!q) return s;

        if (q.mode === 'fill') {
            s.fill = q.colors.fill;
            s.stroke = '#000000';
            s.strokeWidth = 0;
            s.outline2 = {widthPx: 0};
            s.separatedOutline = {outerWidthPx: 0, gapPx: 0};
        }
        if (q.mode === 'outline') {
            s.fill = q.colors.fill;
            s.stroke = q.colors.outline;
            s.strokeWidth = q.strokeWidth || 30;
            s.outline2 = {widthPx: 0};
            s.separatedOutline = {outerWidthPx: 0, gapPx: 0};
        }
        if (q.mode === 'outline2') {
            s.fill = q.colors.fill;
            s.stroke = q.colors.outline;
            s.strokeWidth = q.strokeWidth || 30;
            s.outline2 = {color: q.colors.outline2, widthPx: 45};
            s.separatedOutline = {outerWidthPx: 0, gapPx: 0};
        }
        if (q.mode === 'ring') {
            s.fill = q.colors.fill;
            s.stroke = 0;
            s.strokeWidth = 0;
            s.outline2 = {widthPx: 0};
            s.separatedOutline = {
                outerColor: q.colors.ring,
                outerWidthPx: q.ringWidth || 80,
                gapPx: q.ringGap || 20
            };
        }
        return s;
    }

    // Extract NAME/NUMBER values from a row (fallbacks if slots aren't literally NAME/NUMBER)
    function extractNameNumber(row) {
        const keys = Object.keys(row || {});
        // exact hits first
        let name = row?.NAME ?? row?.Name ?? row?.name;
        let number = row?.NUMBER ?? row?.Number ?? row?.number;
        // fuzzy fallback
        if (name == null) {
            const k = keys.find(k => /name/i.test(k));
            if (k) name = row[k];
        }
        if (number == null) {
            const k = keys.find(k => /num(ber)?/i.test(k));
            if (k) number = row[k];
        }
        return {name: String(name ?? ''), number: String(number ?? '')};
    }
    function clearAllRows() {
        if (!TCState.rows.length) return;
        const ok = confirm(`Delete all ${TCState.rows.length} row(s)?`);
        if (!ok) return;

        TCState.rows = [];
        TCState.selectedRow = -1;

        if (els.body) els.body.innerHTML = '';
        updateButtons();
    }
    function extractImageUrl(respJson) {
        if (!respJson) return null;
        const obj = respJson.image || respJson.preview || respJson;
        return (obj && (obj.url || (obj.preview && obj.preview.url))) || null;
    }

    // Build the EXACT payload your controller expects for Helpers_NameNumber::render_template_remote
    function buildHNPayload(row) {
        const tpl = TCState.activeTemplate || TCState.baseTemplate;

        // find which slots are NAME / NUMBER (case-insensitive)
        const nameSlot = findSlotName(tpl, 'NAME');
        const numberSlot = findSlotName(tpl, 'NUMBER');

        // map per-block quick config to name/number styles if we have those slots
        const nameQuick = nameSlot ? TCState.quick.blocks[nameSlot] : null;
        const numberQuick = numberSlot ? TCState.quick.blocks[numberSlot] : null;

        const name_style = styleFromQuick(nameQuick);
        const number_style = styleFromQuick(numberQuick);

        const {name, number} = extractNameNumber(row);

        return {
            name, number,
            name_style, number_style,
            opts: {
                template_inline: tpl,
                dpi: 300,
                format: 'png',
                preserveCase: true,
                data: row
            }
        };
    }

    function logRow(i, text, cls) {
        if (!els.log) return {
            querySelector: () => ({}), appendChild: () => {
            }
        };
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.dataset.rowIndex = i;
        li.innerHTML = `<span>${text}</span><span class="badge ${cls ? 'bg-' + cls : 'bg-secondary'}">${i + 1}</span>`;
        els.log.appendChild(li);
        return li;
    }

    async function pollProgress(batchId, rowIndex, li) {
        let stage = 'queued', preview = null;
        while (stage !== 'done' && stage !== 'error') {
            const r = await fetch(`${urls.progress}?batch=${encodeURIComponent(batchId)}&row=${rowIndex}`).then(r => r.json());
            stage = r.stage;
            preview = r.preview_url || null;
            const label = ({
                queued: `Queued ${rowIndex + 1}`, building: `Building image ${rowIndex + 1}`,
                saving: `Saving image ${rowIndex + 1}`, inserting: `Inserting ${rowIndex + 1}`,
                done: `Done ${rowIndex + 1}`, error: `Error ${rowIndex + 1}: ${r.error || ''}`
            })[stage] || `Row ${rowIndex + 1}`;
            li.querySelector('span').textContent = label;
            if (stage === 'done' && preview && !li.querySelector('img')) {
                const a = document.createElement('a');
                a.href = preview;
                a.target = '_blank';
                a.textContent = ' preview ';
                const img = document.createElement('img');
                img.src = preview;
                img.alt = 'preview';
                img.style.maxHeight = '40px';
                img.className = 'ms-2';
                li.appendChild(a);
                li.appendChild(img);
            }
            await new Promise(r => setTimeout(r, 1000));
        }
    }

    // ---------- Template + Quick ----------
    function collectPlaceholders(tpl) {
        const slots = [];
        (tpl.blocks || []).forEach(b => {
            if (isTextualBlock(b) && b.slot && !slots.includes(b.slot)) slots.push(b.slot);
        });
        return slots;
    }

    function ensureBlockQuick(slot) {
        if (!TCState.quick.blocks[slot]) {
            TCState.quick.blocks[slot] = {
                mode: 'fill',
                colors: {fill: '#000000', outline: '#FFFFFF', outline2: '#000000', ring: '#000000'},
                strokeWidth: 30,   // outline / outline2 default
                ringWidth: 80,     // ring default
                ringGap: 20        // ring default
            };
        }
        return TCState.quick.blocks[slot];
    }

    function applyQuickToTemplate(base, quick) {
        const t = clone(base);
        (t.blocks || []).forEach(b => {
            if (!b.slot) return;

            // font override (textual only)
            const f = quick.fontsBySlot[b.slot];
            if (f && isTextualBlock(b)) b.font = f;

            // static SVGs: no color edits
            if (!isTextualBlock(b)) return;

            const q = quick.blocks[b.slot];
            if (!q) return;

            if (q.mode === 'fill') {
                if (q.colors.fill) b.fill = q.colors.fill;
                b.stroke = 0;
                b.strokeWidth = 0;
                if (b.outline2) b.outline2.widthPx = 0;
                if (b.separatedOutline) {
                    b.separatedOutline.outerWidthPx = 0;
                    b.separatedOutline.gapPx = 0;
                }
            }
            if (q.mode === 'outline') {
                if (q.colors.fill) b.fill = q.colors.fill;
                if (q.colors.outline) b.stroke = q.colors.outline;
                b.strokeWidth = q.strokeWidth || 20;
                if (b.outline2) b.outline2.widthPx = 0;
                if (b.separatedOutline) {
                    b.separatedOutline.outerWidthPx = 0;
                    b.separatedOutline.gapPx = 0;
                }
            }
            if (q.mode === 'outline2') {
                if (q.colors.fill) b.fill = q.colors.fill;
                if (q.colors.outline) b.stroke = q.colors.outline;
                b.strokeWidth = q.strokeWidth || 20;
                if (!b.outline2) b.outline2 = {color: '#000000', widthPx: 0};
                if (q.colors.outline2) b.outline2.color = q.colors.outline2;
                b.outline2.widthPx = b.outline2.widthPx || 45;
                if (b.separatedOutline) {
                    b.separatedOutline.outerWidthPx = 0;
                    b.separatedOutline.gapPx = 0;
                }
            }
            if (q.mode === 'ring') {
                if (q.colors.fill) b.fill = q.colors.fill;
                b.stroke = 0;
                b.strokeWidth = 0;
                if (b.outline2) b.outline2.widthPx = 0;
                if (!b.separatedOutline) b.separatedOutline = {outerColor: '#000000', outerWidthPx: 0, gapPx: 0};
                if (q.colors.ring) b.separatedOutline.outerColor = q.colors.ring;
                b.separatedOutline.outerWidthPx = q.ringWidth || 80;
                b.separatedOutline.gapPx = q.ringGap || 20;
            }
        });
        return t;
    }

    function buildPrunedOverrides(base, active) {
        const out = {blocks: {}};
        const baseBySlot = {};
        (base.blocks || []).forEach(b => {
            if (b.slot) baseBySlot[b.slot] = b;
        });

        (active.blocks || []).forEach(b => {
            if (!b.slot || !baseBySlot[b.slot]) return;
            const dif = {};
            const a = b, d = baseBySlot[b.slot];

            if (a.font && a.font !== d.font) dif.font = a.font;
            if (a.fill && a.fill !== d.fill) dif.fill = a.fill;

            if ((a.stroke || 0) !== (d.stroke || 0)) dif.stroke = a.stroke || 0;
            if ((a.strokeWidth || 0) !== (d.strokeWidth || 0)) dif.strokeWidth = a.strokeWidth || 0;

            const ao2 = (a.outline2 || {}), do2 = (d.outline2 || {});
            if ((ao2.color || '') !== (do2.color || '')) {
                dif.outline2 = dif.outline2 || {};
                dif.outline2.color = ao2.color || '';
            }
            if ((ao2.widthPx || 0) !== (do2.widthPx || 0)) {
                dif.outline2 = dif.outline2 || {};
                dif.outline2.widthPx = ao2.widthPx || 0;
            }

            const ar = (a.separatedOutline || {}), dr = (d.separatedOutline || {});
            if ((ar.outerColor || '') !== (dr.outerColor || '')) {
                dif.separatedOutline = dif.separatedOutline || {};
                dif.separatedOutline.outerColor = ar.outerColor || '';
            }
            if ((ar.outerWidthPx || 0) !== (dr.outerWidthPx || 0)) {
                dif.separatedOutline = dif.separatedOutline || {};
                dif.separatedOutline.outerWidthPx = ar.outerWidthPx || 0;
            }
            if ((ar.gapPx || 0) !== (dr.gapPx || 0)) {
                dif.separatedOutline = dif.separatedOutline || {};
                dif.separatedOutline.gapPx = ar.gapPx || 0;
            }

            if (Object.keys(dif).length) out.blocks[b.slot] = dif;
        });
        return out;
    }

    // ---------- Color Offcanvas ----------
    function colorNameForHex(hex) {
        const h = (hex || '').toLowerCase();
        const hit = TCState.palette.find(c => (c.hex || '').toLowerCase() === h);
        return hit ? hit.name : null;
    }

    function renderPaletteGrid(mountEl, initialHex, onPick) {
        if (!mountEl) return;
        mountEl.innerHTML = '';
        const wrap = document.createElement('div');
        wrap.className = 'd-grid';
        wrap.style.gridTemplateColumns = 'repeat(5, 1fr)';
        wrap.style.gap = '10px';

        (TCState.palette || []).forEach(c => {
            const tile = document.createElement('button');
            tile.type = 'button';
            tile.className = 'btn btn-light text-start';
            tile.style.border = '1px solid #e5e7eb';
            tile.style.borderRadius = '10px';
            tile.style.padding = '10px 8px';
            tile.style.height = '72px';

            const sw = document.createElement('div');
            sw.style.width = '100%';
            sw.style.height = '28px';
            sw.style.border = '1px solid #d1d5db';
            sw.style.borderRadius = '6px';
            sw.style.background = c.hex;

            const cap = document.createElement('div');
            cap.className = 'small mt-2 text-truncate';
            cap.title = `${c.name} ${c.hex}`;
            cap.textContent = c.name;

            tile.appendChild(sw);
            tile.appendChild(cap);
            tile.addEventListener('click', () => onPick(c.hex, c.name));
            wrap.appendChild(tile);
        });

        const free = document.createElement('div');
        free.className = 'mt-3 d-flex align-items-center gap-2';
        free.innerHTML = `
      <input type="color" class="form-control form-control-color" id="nl-free-color" value="${initialHex || '#000000'}">
      <input type="text" class="form-control form-control-sm" id="nl-free-hex" placeholder="#RRGGBB" value="${initialHex || ''}">
      <button class="btn btn-secondary btn-sm" id="nl-free-apply" type="button">Apply</button>
    `;
        free.querySelector('#nl-free-apply').addEventListener('click', () => {
            const val = free.querySelector('#nl-free-hex').value.trim() || free.querySelector('#nl-free-color').value;
            onPick(val, val);
        });
        free.querySelector('#nl-free-color').addEventListener('input', (e) => {
            free.querySelector('#nl-free-hex').value = e.target.value;
        });

        mountEl.appendChild(wrap);
        mountEl.appendChild(free);
    }

    function attachColorButton(containerEl, initialHex, onChange) {
        containerEl.innerHTML = '';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-outline-secondary btn-sm';
        btn.setAttribute('data-bs-toggle', 'offcanvas');
        btn.setAttribute('data-bs-target', '#offcanvas-colors');
        btn.setAttribute('aria-controls', 'offcanvas-colors');

        const sw = document.createElement('span');
        sw.className = 'tc-color-swatch';
        sw.style.display = 'inline-block';
        sw.style.width = '16px';
        sw.style.height = '16px';
        sw.style.border = '1px solid #d1d5db';
        sw.style.borderRadius = '4px';
        sw.style.marginRight = '8px';
        sw.style.background = initialHex || '#000000';

        const label = document.createElement('span');
        label.className = 'tc-color-label text-truncate';
        label.textContent = colorNameForHex(initialHex) || (initialHex || '#000000');

        btn.appendChild(sw);
        btn.appendChild(label);
        containerEl.appendChild(btn);

        btn.addEventListener('click', () => {
            const mount = els.colorOffcanvasMount;
            if (!mount) return;
            const slot = btn.closest('tr')?.dataset.slot || 'unknown';
            const role = containerEl.closest('[data-role]')?.dataset.role || 'unknown';
            const offcanvasTitle = document.getElementById('offcanvasColorsLabel');
            if (offcanvasTitle) {
                offcanvasTitle.textContent = `Choose Color: ${slot} (${role})`;
            }

            renderPaletteGrid(mount, initialHex || '#000000', (hex, name) => {
                sw.style.background = hex;
                label.textContent = name || hex;
                onChange(hex);
                try {
                    const ocEl = document.getElementById('offcanvas-colors');
                    if (window.bootstrap && bootstrap.Offcanvas) {
                        bootstrap.Offcanvas.getOrCreateInstance(ocEl).hide();
                    }
                } catch (e) {
                }
            });
        });
    }

    // ---------- Per-Block UI ----------
    function makeNumberInput(labelText, initial, onChange, min = 0, step = 1, width = '100px') {
        const wrap = document.createElement('div');
        wrap.className = 'd-inline-flex align-items-center me-3 mb-2';
        const lab = document.createElement('span');
        lab.className = 'me-2 small text-muted';
        lab.textContent = labelText;
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.className = 'form-control form-control-sm';
        inp.style.width = width;
        inp.min = String(min);
        inp.step = String(step);
        inp.value = (initial ?? '');
        inp.addEventListener('input', () => {
            const v = Number(inp.value);
            if (!Number.isFinite(v)) return;
            onChange(v);
        });
        wrap.appendChild(lab);
        wrap.appendChild(inp);
        return {wrap, inp};
    }

    function createSvgPreviewCell(block) {
        const cell = document.createElement('div');
        cell.className = 'text-muted small d-flex align-items-center gap-2';
        let src = null;
        if (block.url) src = block.url;
        else if (block.src) src = block.src;
        else if (typeof block.svg === 'string') src = 'data:image/svg+xml;utf8,' + encodeURIComponent(block.svg);

        const badge = document.createElement('span');
        badge.className = 'badge bg-secondary';
        badge.textContent = 'SVG';
        cell.appendChild(badge);

        if (src) {
            const img = document.createElement('img');
            img.src = src;
            img.alt = 'svg preview';
            img.style.maxHeight = '40px';
            img.style.maxWidth = '120px';
            img.style.border = '1px solid #e5e7eb';
            img.style.borderRadius = '6px';
            img.loading = 'lazy';
            cell.appendChild(img);
        } else {
            const txt = document.createElement('span');
            txt.textContent = 'Static block';
            cell.appendChild(txt);
        }
        return cell;
    }

    function renderBlockRows(template) {
        const tbody = els.blockRows;
        if (!tbody) return;
        tbody.innerHTML = '';
        tbody.classList.add('fs-4');
        (template.blocks || []).forEach(b => {
            if (!b.slot) return;

            // SVG (non-text) -> static row with preview; no controls
            if (isSvgNonTextBlock(b)) {
                const tr = document.createElement('tr');
                const tdBlock = document.createElement('td');
                tdBlock.textContent = b.slot;
                tr.appendChild(tdBlock);
                const tdMode = document.createElement('td');
                tdMode.innerHTML = '<span class="text-muted small">n/a</span>';
                tr.appendChild(tdMode);
                const tdColors = document.createElement('td');
                tdColors.appendChild(createSvgPreviewCell(b));
                tr.appendChild(tdColors);
                tbody.appendChild(tr);
                return;
            }

            // text / arc / label / svg_text blocks
            const q = ensureBlockQuick(b.slot);
            const tr = document.createElement('tr');
            tr.dataset.slot = b.slot;

            // Block name
            const tdBlock = document.createElement('td');
            tdBlock.textContent = b.slot;
            tr.appendChild(tdBlock);

            // Mode radios
            const tdMode = document.createElement('td');
            const group = document.createElement('div');
            group.className = 'btn-group';
            ['fill', 'outline', 'outline2', 'ring'].forEach(mode => {
                const safeSlot = String(b.slot).replace(/[^a-z0-9_-]/gi, '_');
                const id = `mode-${safeSlot}-${mode}`;
                const inp = document.createElement('input');
                inp.type = 'radio';
                inp.className = 'btn-check';
                inp.name = `mode-${safeSlot}`;
                inp.id = id;
                inp.value = mode;
                if (q.mode === mode) inp.checked = true;
                const lbl = document.createElement('label');
                lbl.className = 'btn btn-outline-danger btn-sm';
                lbl.setAttribute('for', id);
                lbl.textContent = mode;
                inp.addEventListener('change', () => {
                    if (!inp.checked) return;
                    q.mode = mode;
                    renderVisibility();
                    TCState.activeTemplate = applyQuickToTemplate(TCState.baseTemplate, TCState.quick);
                });
                group.appendChild(inp);
                group.appendChild(lbl);
            });
            tdMode.appendChild(group);
            tr.appendChild(tdMode);

            // Colors + numeric controls
            const tdColors = document.createElement('td');

            const containersByKey = {}; // color roles
            const slidersByKey = {}; // numeric inputs

            function setVisible(el, vis) {
                if (!el) return;
                el.classList.toggle('d-none', !vis);
                el.style.display = vis ? '' : 'none';
                el.setAttribute('aria-hidden', String(!vis));
            }

            function renderVisibility() {
                const m = q.mode;
                setVisible(containersByKey.fill, true);
                setVisible(containersByKey.outline, (m === 'outline' || m === 'outline2'));
                setVisible(containersByKey.outline2, (m === 'outline2'));
                setVisible(containersByKey.ring, (m === 'ring'));
                setVisible(slidersByKey.strokeWidth, (m === 'outline' || m === 'outline2'));
                setVisible(slidersByKey.ringWidth, (m === 'ring'));
                setVisible(slidersByKey.ringGap, (m === 'ring'));
            }

            function makeRole(roleKey, labelText, initialHex) {
                const wrap = document.createElement('div');
                wrap.className = 'd-inline-flex align-items-center me-3 mb-2';
                wrap.dataset.role = labelText;
                const lab = document.createElement('span');
                lab.className = 'me-2 small text-black-50';
                lab.textContent = labelText;
                const btnWrap = document.createElement('span');
                btnWrap.className = 'nl-cc-cell';
                wrap.appendChild(lab);
                wrap.appendChild(btnWrap);
                tdColors.appendChild(wrap);
                containersByKey[roleKey] = wrap;
                attachColorButton(btnWrap, initialHex, (hex) => {
                    q.colors[roleKey] = hex;
                    TCState.activeTemplate = applyQuickToTemplate(TCState.baseTemplate, TCState.quick);
                });
            }

            makeRole('fill', 'Fill', q.colors.fill);
            makeRole('outline', 'Outline', q.colors.outline);
            makeRole('outline2', 'Outline 2', q.colors.outline2);
            makeRole('ring', 'Ring', q.colors.ring);

            const strokeCtl = makeNumberInput('Stroke', q.strokeWidth, v => {
                q.strokeWidth = v;
                TCState.activeTemplate = applyQuickToTemplate(TCState.baseTemplate, TCState.quick);
            });
            const ringWctl = makeNumberInput('Ring W', q.ringWidth, v => {
                q.ringWidth = v;
                TCState.activeTemplate = applyQuickToTemplate(TCState.baseTemplate, TCState.quick);
            });
            const ringGctl = makeNumberInput('Ring Gap', q.ringGap, v => {
                q.ringGap = v;
                TCState.activeTemplate = applyQuickToTemplate(TCState.baseTemplate, TCState.quick);
            });

            slidersByKey.strokeWidth = strokeCtl.wrap;
            slidersByKey.ringWidth = ringWctl.wrap;
            slidersByKey.ringGap = ringGctl.wrap;

            tdColors.appendChild(strokeCtl.wrap);
            tdColors.appendChild(ringWctl.wrap);
            tdColors.appendChild(ringGctl.wrap);

            tr.appendChild(tdColors);
            tbody.appendChild(tr);

            // initial visibility for this row
            renderVisibility();
        });
    }


    // ---------- When a template is loaded ----------
    window.TC_onTemplateLoaded = async function (templateJson) {
        if (!templateJson) return;
        TCState.baseTemplate = clone(templateJson);
        TCState.activeTemplate = clone(templateJson);
        TCState.placeholders = collectPlaceholders(templateJson); // textual slots only
        TCState.rows = [];
        TCState.selectedRow = -1;

        // Load palette once
        if (!TCState.palette.length && urls.colors) {
            try {
                const res = await fetch(urls.colors).then(r => r.json());
                if (res && res.success) TCState.palette = res.colors || [];
            } catch (e) {
                console.error('TC: palette load error', e);
            }
        }

        // Load fonts once
        if (!TCState.fonts.length && urls.fonts) {
            try {
                const res = await fetch(urls.fonts).then(r => r.json());
                console.log('TC: fetched fonts', res);
                if (res && res.success === false) {
                    console.error('TC: font fetch failed', res.message);
                    TCState.fonts = [];
                } else {
                    // Controller now returns plain array of {id, name}
                    TCState.fonts = Array.isArray(res) ? res : (res.fonts || []);
                }
            } catch (e) {
                console.error('TC: font fetch error', e);
                TCState.fonts = [];
            }
        }

        // Initialize per-block quick defaults for textual blocks only
        (templateJson.blocks || []).forEach(b => {
            if (isTextualBlock(b) && b.slot) ensureBlockQuick(b.slot);
        });

        // Render per-block UI
        renderBlockRows(templateJson);

        // Fonts for textual blocks
        renderFontsSync(templateJson);

        // Grid headers for textual placeholders
        renderGridHeaders(TCState.placeholders);

        // If CSV already parsed, refresh mapping with the new placeholders
        if (CSV_STATE.headers.length) renderCsvMapping(TCState.placeholders, CSV_STATE.headers);

        updateButtons();
    };

    function renderFontsSync(baseTemplate) {
        if (!els.fontRows) return;
        const fonts = Array.isArray(TCState.fonts) ? TCState.fonts : [];
        const tbody = els.fontRows;
        tbody.innerHTML = '';
        tbody.classList.add('fs-4');
        (baseTemplate.blocks || []).forEach(b => {
            if (!isTextualBlock(b) || !b.slot) return; // exclude static SVG blocks
            const tr = document.createElement('tr');
            const td1 = document.createElement('td');
            td1.textContent = b.slot;
            const td2 = document.createElement('td');
            const sel = document.createElement('select');
            sel.className = 'form-select form-select-sm';
            const opt0 = document.createElement('option');
            opt0.value = '';
            opt0.textContent = `(Default) ${b.font || ''}`;
            sel.appendChild(opt0);
            fonts.forEach(f => {
                const o = document.createElement('option');
                o.value = f.id;
                o.textContent = f.name || f.id;
                if (TCState.quick.fontsBySlot[b.slot] === f.id) o.selected = true;
                sel.appendChild(o);
            });
            sel.addEventListener('change', () => {
                if (sel.value) TCState.quick.fontsBySlot[b.slot] = sel.value; else delete TCState.quick.fontsBySlot[b.slot];
                TCState.activeTemplate = applyQuickToTemplate(TCState.baseTemplate, TCState.quick);
            });
            td2.appendChild(sel);
            tr.appendChild(td1);
            tr.appendChild(td2);
            tbody.appendChild(tr);
        });
    }

    // ---------- Build payload for Helpers_NameNumber::render_template_remote ----------
    function pickNameNumberKeys(placeholders) {
        const arr = (placeholders || []).map(s => String(s));
        const lower = arr.map(s => ({raw: s, low: s.toLowerCase()}));
        let nameKey = lower.find(x => x.low === 'name')?.raw
            || lower.find(x => x.low.includes('name'))?.raw
            || arr[0] || null;
        let numberKey = lower.find(x => x.low === 'number')?.raw
            || lower.find(x => x.low.includes('number'))?.raw
            || arr[1] || null;
        if (nameKey === numberKey && arr.length > 1) numberKey = arr[1];
        return {nameKey, numberKey};
    }

    function styleForSlot(slot) {
        const q = (TCState.quick.blocks && TCState.quick.blocks[slot]) || {
            mode: 'fill',
            colors: {fill: '#000000', outline: '#FFFFFF', outline2: '#000000', ring: '#000000'},
            strokeWidth: 30, ringWidth: 80, ringGap: 20
        };
        const fontId = TCState.quick.fontsBySlot ? TCState.quick.fontsBySlot[slot] : null;

        // Use camelCase keys that your PHP snippet and typical renderers accept.
        const s = {
            mode: q.mode,
            font: fontId || null,

            fill: q.colors.fill || null,

            stroke: (q.mode === 'outline' || q.mode === 'outline2') ? (q.colors.outline || null) : null,
            strokeWidth: (q.mode === 'outline' || q.mode === 'outline2') ? (q.strokeWidth || 30) : 0,

            outline2: {
                color: (q.mode === 'outline2') ? (q.colors.outline2 || null) : null,
                widthPx: (q.mode === 'outline2') ? 45 : 0
            },

            separatedOutline: {
                outerColor: (q.mode === 'ring') ? (q.colors.ring || null) : null,
                outerWidthPx: (q.mode === 'ring') ? (q.ringWidth || 80) : 0,
                gapPx: (q.mode === 'ring') ? (q.ringGap || 20) : 0
            }
        };
        return s;
    }

    const DEFAULT_DPI = 300;

    function buildHNRemotePayload(row) {
        const base = TCState.baseTemplate || {};
        const active = TCState.activeTemplate || TCState.baseTemplate || {};
        const {nameKey, numberKey} = pickNameNumberKeys(TCState.placeholders || []);

        const name = (row && nameKey && row[nameKey] != null) ? String(row[nameKey]) : '';
        const number = (row && numberKey && row[numberKey] != null) ? String(row[numberKey]) : '';

        const nameStyle = nameKey ? styleForSlot(nameKey) : {};
        const numberStyle = numberKey ? styleForSlot(numberKey) : {};

        // Keep full template & overrides for your backend if it needs them
        const pruned = buildPrunedOverrides(TCState.baseTemplate, active);

        // Slots-to-data map (what your PHP calls $dataFromSlots)
        const dataFromSlots = {};
        (TCState.placeholders || []).forEach(ph => {
            dataFromSlots[ph] = (row && row[ph] != null) ? row[ph] : '';
        });

        return {
            // for Helpers_NameNumber::render_template_remote(null, name, number, nameStyle, numberStyle, opts)
            name, number,
            name_style: nameStyle,
            number_style: numberStyle,
            opts: {
                template_inline: active,    // <<< IMPORTANT
                dpi: DEFAULT_DPI,
                format: 'png',
                preserveCase: true,
                allowEmptyTopLevel: true,
                data: dataFromSlots         // <<< IMPORTANT: slots → data
            },

            // Additional fields some backends still reference (harmless if unused)
            template_inline: active,
            data: dataFromSlots,
            overrides: pruned,
            format: 'png',
            preserve_case: true,
            embed_fonts: true,
            debug: false
        };
    }

    // ---------- Grid ----------
    function renderGridHeaders(placeholders){
        if (!els.head || !els.body || !els.grid || !els.gridEmpty) return;
        els.head.innerHTML=''; els.body.innerHTML='';

        if (!placeholders || !placeholders.length){
            els.grid.style.display='none';
            els.gridEmpty.style.display='';
            if (els.addRow) els.addRow.disabled = true;
            return;
        }

        els.gridEmpty.style.display='none';
        els.grid.style.display='';
        if (els.addRow) els.addRow.disabled = false;

        const tr = document.createElement('tr');

        // select column
        const selTh = document.createElement('th');
        selTh.style.width='36px';
        tr.appendChild(selTh);

        // placeholder columns
        placeholders.forEach(ph=>{
            const th=document.createElement('th');
            th.textContent=ph;
            tr.appendChild(th);
        });
        const th=document.createElement('th');
        th.textContent='Quantity';
        th.style.width='60px';
        tr.appendChild(th);
        // actions header with inline buttons
        const thActs=document.createElement('th');
        thActs.className='text-end';
        thActs.style.whiteSpace='nowrap';
        addBtn.disabled = false;
        tr.appendChild(thActs);
        delBtn.disabled = false;
        els.head.appendChild(tr);
    }


    function renderRow(i, row) {
        if (!els.body) return;
        const tr = document.createElement('tr');
        tr.dataset.rowIndex = i;
        const tdSel = document.createElement('td');
        tdSel.classList.add('fs-4');
        const rb = document.createElement('input');
        rb.type = 'radio';
        rb.name = 'tc-row-sel';
        rb.className = 'form-check-input';
        rb.addEventListener('change', () => {
            TCState.selectedRow = i;
            updateButtons();
            highlightSelection();
        });
        tdSel.appendChild(rb);
        tr.appendChild(tdSel);

        TCState.placeholders.forEach(ph => {
            const td = document.createElement('td');
            const inp = document.createElement('input');
            inp.type = 'text';
            inp.className = 'form-control font-blinker fw-semibold fs-4 text-muted';
            inp.value = row[ph] || '';
            inp.addEventListener('input', () => {
                row[ph] = inp.value;
            });
            td.appendChild(inp);
            tr.appendChild(td);
        });

        // Qty input cell
        // Qty input cell
        const tdQty = document.createElement('td');
        const qInp = document.createElement('input');
        qInp.type = 'number';
        qInp.min = '1';
        qInp.step = '1';
        qInp.className = 'form-control font-blinker fw-semibold fs-4 text-muted';
        qInp.style.width = '60px';
        qInp.style.textAlign = 'center';
        qInp.value = row[ORDER_QTY_KEY] ?? 1;
        qInp.addEventListener('input', () => {
            const n = parseInt(qInp.value, 10);
            row[ORDER_QTY_KEY] = (Number.isFinite(n) && n > 0) ? n : 1;
        });
        tdQty.appendChild(qInp);
        tr.appendChild(tdQty);

        const tdAct = document.createElement('td');
        const btnDel = document.createElement('button');
        btnDel.className = 'btn btn-sm btn-outline-danger';
        btnDel.textContent = '✕';
        btnDel.addEventListener('click', () => {
            const idx = parseInt(tr.dataset.rowIndex, 10);
            TCState.rows.splice(idx, 1);
            tr.remove();
            Array.from(els.body.querySelectorAll('tr')).forEach((r, ii) => r.dataset.rowIndex = ii);
            if (TCState.selectedRow === idx) TCState.selectedRow = -1;
            updateButtons();
            highlightSelection();
        });
        tdAct.appendChild(btnDel);
        tr.appendChild(tdAct);
        els.body.appendChild(tr);
    }

    function addRow(initial) {
        const row = {};
        TCState.placeholders.forEach(ph => row[ph] = (initial && initial[ph]) || '');
        row[ORDER_QTY_KEY] = (initial && initial[ORDER_QTY_KEY]) ? parseInt(initial[ORDER_QTY_KEY], 10) || 1 : 1;
        TCState.rows.push(row);
        renderRow(TCState.rows.length - 1, row);
        updateButtons();
    }

    function highlightSelection() {
        if (!els.body) return;
        Array.from(els.body.querySelectorAll('tr')).forEach((tr, ii) => {
            tr.classList.toggle('table-active', ii === TCState.selectedRow);
            const rb = tr.querySelector('input[type=radio]');
            if (rb) rb.checked = (ii === TCState.selectedRow);
        });
    }

    function updateButtons() {
        const hasTpl = !!TCState.baseTemplate, hasRows = (TCState.rows.length > 0), hasSel = (TCState.selectedRow >= 0);
        if (els.preview) els.preview.disabled = !(hasTpl && hasSel);
        if (els.run) els.run.disabled = !(hasTpl && hasRows);
        if (els.csvBtn) els.csvBtn.disabled = !hasTpl;
    }

    // ---------- Template dropdown ----------
    async function loadTemplates() {
        if (!urls.templates || !els.tpl) return;
        try {
            const data = await fetch(urls.templates).then(r => r.json());
            const list = (data && data.templates) || [];
            els.tpl.innerHTML = `<option value="">Select a template…</option>` + list.map(t => `<option value="${t.id}">${t.title}</option>`).join('');
    if (els.tpl) {
        els.tpl.addEventListener('change', async function () {
            const id = parseInt(this.value, 10);
            if (!id) {
                TCState.baseTemplate = null;
                TCState.rows = [];
                TCState.selectedRow = -1;
                renderGridHeaders([]);
                updateButtons();
                return;
            }
            // Avoid reloading if it's already the active template (e.g. from templatecards.js)
            if (TCState.baseTemplate && Number(TCState.baseTemplate.id) === id) {
                return;
            }
            const dj = await fetch(`${urls.template}?id=${id}`).then(r => r.json());
            if (!dj || !dj.success) {
                alert(dj && dj.message ? dj.message : 'Failed to load template');
                return;
            }
            window.TC_onTemplateLoaded(dj.template);
        });
    }
        } catch (e) {
            console.error('templates load failed', e);
        }
    }

    // ---------- CSV (auto-delimiter, mapping above, select-all) ----------
    const tblHead = els.csvTable ? els.csvTable.querySelector('thead') : null;
    const tblBody = els.csvTable ? els.csvTable.querySelector('tbody') : null;
    let headerSelectAll = null;

    // Delegate: when any row checkbox toggles, refresh select-all state
    if (tblBody) {
        tblBody.addEventListener('change', (e) => {
            if (e.target && e.target.classList && e.target.classList.contains('csv-row-select')) {
                updateSelectAllState();
            }
        });
    }

    function wireSelectAll() {
        headerSelectAll = document.getElementById('csv-select-all');
        if (!headerSelectAll) return;
        headerSelectAll.onchange = () => {
            const all = !!headerSelectAll.checked;
            if (!tblBody) return;
            tblBody.querySelectorAll('.csv-row-select').forEach(cb => {
                cb.checked = all;
            });
            updateSelectAllState();
        };
    }

    function updateSelectAllState() {
        if (!headerSelectAll || !tblBody) return;
        const checks = Array.from(tblBody.querySelectorAll('.csv-row-select'));
        const total = checks.length;
        const checked = checks.filter(c => c.checked).length;

        if (!total) {
            headerSelectAll.checked = false;
            headerSelectAll.indeterminate = false;
            headerSelectAll.disabled = true;
            return;
        }
        headerSelectAll.disabled = false;
        headerSelectAll.checked = (checked === total);
        headerSelectAll.indeterminate = (checked > 0 && checked < total);
    }

    function ensureCsvMappingVisible() {
        if (!els.csvMapWrap || !els.csvMapBody) return;
        els.csvMapWrap.style.display = '';
    }

    // qty-guess helper
    function guessQtyIdx(headers) {
        const hay = headers.map(h => (h || '').toLowerCase().trim());
        const exact = ['qty', 'quantity'];
        for (let i = 0; i < hay.length; i++) {
            if (exact.includes(hay[i])) return i;
        }
        for (let i = 0; i < hay.length; i++) {
            const h = hay[i];
            if (/\bqty\b/.test(h) || /\bquantity\b/.test(h) || h === '#' || /count/.test(h)) return i;
        }
        return -1;
    }

    function renderCsvMapping(placeholders, headers) {
        if (!els.csvMapWrap || !els.csvMapBody) return;
        ensureCsvMappingVisible();
        els.csvMapBody.innerHTML = '';
        placeholders.forEach(ph => {
            const tr = document.createElement('tr');
            const td1 = document.createElement('td');
            td1.textContent = ph;
            tr.appendChild(td1);
            const td2 = document.createElement('td');
            const sel = document.createElement('select');
            sel.className = 'form-select form-select-sm';
            sel.dataset.placeholder = ph;

            const opt0 = document.createElement('option');
            opt0.value = '';
            opt0.textContent = '(ignore)';
            sel.appendChild(opt0);
            headers.forEach((h, idx) => {
                const o = document.createElement('option');
                o.value = String(idx);
                o.textContent = h;
                if ((h || '').toLowerCase() === (ph || '').toLowerCase()) o.selected = true;
                sel.appendChild(o);
            });

            td2.appendChild(sel);
            tr.appendChild(td2);
            els.csvMapBody.appendChild(tr);
        });

        // Extra row: Order Quantity
        const trQ = document.createElement('tr');
        const tdQ1 = document.createElement('td');
        tdQ1.textContent = 'Order Quantity';
        const tdQ2 = document.createElement('td');
        const selQ = document.createElement('select');
        selQ.className = 'form-select form-select-sm';
        selQ.dataset.placeholder = ORDER_QTY_KEY;
        const optQ0 = document.createElement('option');
        optQ0.value = '';
        optQ0.textContent = '(ignore → defaults to 1)';
        selQ.appendChild(optQ0);
        headers.forEach((h, idx) => {
            const o = document.createElement('option');
            o.value = String(idx);
            o.textContent = h;
            selQ.appendChild(o);
        });
        const g = guessQtyIdx(headers);
        if (g >= 0) selQ.value = String(g);
        tdQ2.appendChild(selQ);
        trQ.appendChild(tdQ1);
        trQ.appendChild(tdQ2);
        els.csvMapBody.appendChild(trQ);
    }

    function currentCsvMapping() {
        const map = {};
        if (!els.csvMapBody) return map;
        Array.from(els.csvMapBody.querySelectorAll('select')).forEach(sel => {
            map[sel.dataset.placeholder] = sel.value === '' ? -1 : parseInt(sel.value, 10);
        });
        return map;
    }

    const SAMPLE = `NAME,NUMBER,COLOR
Jordan,23,#000000
Pat,7,#E9592D
Taylor,12,#FFFFFF`;

    function parseCSV(text) {
        if (!text) return {headers: [], rows: []};

        // strip BOM and normalise newlines
        let raw = String(text);
        if (raw.charCodeAt(0) === 0xFEFF) raw = raw.slice(1);
        const lines = raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n').filter(l => l.trim().length > 0);
        if (!lines.length) return {headers: [], rows: []};

        // detect delimiter
        const first = lines[0];
        const counts = {
            ',': (first.match(/,/g) || []).length,
            ';': (first.match(/;/g) || []).length,
            '\t': (first.match(/\t/g) || []).length
        };
        let delim = ',';
        let max = -1;
        for (const k of [',', ';', '\t']) {
            if (counts[k] > max) {
                max = counts[k];
                delim = k;
            }
        }

        function splitLine(line) {
            const out = [];
            let cur = '';
            let inQ = false;
            for (let i = 0; i < line.length; i++) {
                const ch = line[i];
                if (ch === '"') {
                    if (inQ && line[i + 1] === '"') {
                        cur += '"';
                        i++;
                    } else {
                        inQ = !inQ;
                    }
                } else if (ch === delim && !inQ) {
                    out.push(cur);
                    cur = '';
                } else {
                    cur += ch;
                }
            }
            out.push(cur);
            return out.map(v => v.trim());
        }

        const headers = splitLine(lines[0]);
        const rows = [];
        for (let i = 1; i < lines.length; i++) {
            const cols = splitLine(lines[i]);
            if (cols.every(v => v === '')) continue;
            const obj = {};
            for (let c = 0; c < headers.length; c++) {
                obj[headers[c]] = (cols[c] ?? '');
            }
            rows.push(obj);
        }
        return {headers, rows};
    }

    function renderCSVTable(headers, rows) {
        if (!tblHead || !tblBody) return;
        tblHead.innerHTML = '';
        tblBody.innerHTML = '';

        // header with select-all checkbox
        const trh = document.createElement('tr');
        trh.innerHTML =
            `<th style="width:46px;" class="text-center">
         <input class="form-check-input" type="checkbox" id="csv-select-all">
       </th>` +
            headers.map(h => `<th>${h}</th>`).join('');
        tblHead.appendChild(trh);

        // rows
        rows.forEach((r, i) => {
            const tr = document.createElement('tr');
            const cells = headers.map(h => `<td>${(r[h] ?? '')}</td>`).join('');
            tr.innerHTML = `<td class="text-center"><input class="form-check-input csv-row-select" type="checkbox" data-row="${i}"></td>${cells}`;
            tblBody.appendChild(tr);
        });

        // wire & sync header checkbox
        wireSelectAll();
        updateSelectAllState();

        // show mapping if we have both sides
        if (TCState.placeholders.length && headers.length) {
            renderCsvMapping(TCState.placeholders, headers);
        }
    }

    function getSelectedCSVRows(headers, rows) {
        const checks = Array.from(tblBody ? tblBody.querySelectorAll('.csv-row-select') : []);
        const selected = checks.filter(c => c.checked).map(c => rows[Number(c.dataset.row)]);
        return selected.map(r => ({...r}));
    }

    // File upload
    if (els.csvFile) {
        els.csvFile.addEventListener('change', () => {
            const f = els.csvFile.files && els.csvFile.files[0];
            if (!f) return;
            const reader = new FileReader();
            reader.onload = () => {
                const raw = String(reader.result || '');
                const {headers, rows} = parseCSV(raw);
                CSV_STATE.headers = headers;
                CSV_STATE.rows = rows;
                renderCSVTable(headers, rows);
            };
            reader.readAsText(f);
        });
    }

    // Sample
    if (els.csvSample) {
        els.csvSample.addEventListener('click', (e) => {
            e.preventDefault();
            const {headers, rows} = parseCSV(SAMPLE);
            CSV_STATE.headers = headers;
            CSV_STATE.rows = rows;
            renderCSVTable(headers, rows);
        });
    }

    // Add selected rows -> batch grid (uses mapping)
    window.CSV_IMPORT = window.CSV_IMPORT || {};
    if (!window.CSV_IMPORT.onAdd) {
        window.CSV_IMPORT.onAdd = function (rows) {
            const map = currentCsvMapping(); // {placeholder: idx|-1}
            const qtyIdx = (map && Object.prototype.hasOwnProperty.call(map, ORDER_QTY_KEY)) ? map[ORDER_QTY_KEY] : -1;

            rows.forEach(r => {
                const obj = {};
                // placeholders → values
                TCState.placeholders.forEach(ph => {
                    const idx = (map && Object.prototype.hasOwnProperty.call(map, ph)) ? map[ph] : -1;
                    if (idx >= 0 && CSV_STATE.headers[idx] != null) {
                        const header = CSV_STATE.headers[idx];
                        obj[ph] = r[header] ?? '';
                    } else {
                        // best-effort header name match
                        const keys = Object.keys(r);
                        const hit = keys.find(k => (k || '').toLowerCase() === (ph || '').toLowerCase());
                        obj[ph] = hit ? r[hit] : '';
                    }
                });

                // synthetic order quantity (default 1)
                let q = 1;
                if (qtyIdx >= 0 && CSV_STATE.headers[qtyIdx] != null) {
                    const header = CSV_STATE.headers[qtyIdx];
                    const raw = (r[header] ?? '').toString().trim();
                    const n = parseInt(raw, 10);
                    if (Number.isFinite(n) && n > 0) q = n;
                }
                obj[ORDER_QTY_KEY] = q;

                addRow(obj);
            });
            TCState.selectedRow = (TCState.rows.length ? 0 : -1);
            highlightSelection();
            updateButtons();
        };
    }
    if (els.csvAddSelected) {
        els.csvAddSelected.addEventListener('click', () => {
            if (!CSV_STATE.headers.length || !CSV_STATE.rows.length) {
                alert('Nothing to add. Load a CSV or use Sample first.');
                return;
            }
            const rows = getSelectedCSVRows(CSV_STATE.headers, CSV_STATE.rows);
            if (!rows.length) {
                alert('Select at least one row.');
                return;
            }
            try {
                window.CSV_IMPORT.onAdd(rows);
                if (els.csvOffcanvas && window.bootstrap && bootstrap.Offcanvas) {
                    bootstrap.Offcanvas.getOrCreateInstance(els.csvOffcanvas).hide();
                }
            } catch (err) {
                alert('Failed to add rows: ' + (err && err.message ? err.message : err));
            }
        });
    }

    // Open CSV offcanvas from top button
    if (els.csvBtn && els.csvOffcanvas && window.bootstrap && bootstrap.Offcanvas) {
        els.csvBtn.addEventListener('click', () => {
            if (!TCState.baseTemplate) {
                alert('Choose a template first.');
                return;
            }
            bootstrap.Offcanvas.getOrCreateInstance(els.csvOffcanvas).show();
        });
    }

    // ---------- Buttons ----------
    if (els.addRow) els.addRow.addEventListener('click', () => addRow());

    async function fetchWithCsrf(url, options = {}) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            ...options.headers
        };
        if (csrfToken) {
            headers['X-CSRF-TOKEN'] = csrfToken;
        }
        return fetch(url, {...options, headers});
    }

    // PREVIEW → Helpers_NameNumber::render_template_remote(null, name, number, nameStyle, numberStyle, opts)
    if (els.preview) els.preview.addEventListener('click', async () => {
        if (TCState.selectedRow < 0) return;
        const row = TCState.rows[TCState.selectedRow];
        const payload = buildHNRemotePayload(row);
        try {
            const res = await fetchWithCsrf(urls.preview, {
                method: 'POST', body: JSON.stringify(payload)
            });
            const json = await res.json();
            if (!json.success) throw new Error(json.message || `Preview failed (${res.status})`);
            const li = logRow(TCState.selectedRow, 'Preview ready', 'info');
            const url = json.preview && (json.preview.url || json.preview);
            if (url) {
                const a = document.createElement('a');
                a.href = url;
                a.target = '_blank';
                a.textContent = ' preview ';
                const img = document.createElement('img');
                img.src = url;
                img.style.maxHeight = '40px';
                img.className = 'ms-2';
                li.appendChild(a);
                li.appendChild(img);
            }
        } catch (e) {
            alert(e.message || 'Preview error');
        }
    });

    // RUN BATCH → same payload per row (+ order_quantity)
    if (els.run) els.run.addEventListener('click', async () => {
        if (!TCState.rows.length) return;

        // Disable buttons while running
        const disable = (v) => {
            els.run.disabled = v;
            if (els.preview) els.preview.disabled = v || !(TCState.baseTemplate && TCState.selectedRow >= 0);
            if (els.addRow) els.addRow.disabled = v;
        };
        disable(true);

        const batchId = Math.random().toString(36).slice(2, 10);
        els.log.innerHTML = '';
        setBar(0, TCState.rows.length);

        for (let i = 0; i < TCState.rows.length; i++) {
            const li = logRow(i, `Rendering ${i + 1}…`, 'secondary');

            // Build the same payload used by Preview (HN style)
            const payload = buildHNPayload(TCState.rows[i]);
            payload.batch_id = batchId;
            payload.row_index = i;
            payload.image_name = 'customnames';

            // include order quantity
            const qty = parseInt(TCState.rows[i][ORDER_QTY_KEY], 10);
            const finalQty = (Number.isFinite(qty) && qty > 0) ? qty : 1;
            payload.opts = payload.opts || {};
            payload.opts.order_quantity = finalQty;

            // Pass order info if present (so server can attach to order)
            if (cfg.order_id) payload.order_id = cfg.order_id;
            if (cfg.order_item_id) payload.order_item_id = cfg.order_item_id;

            try {
                const resp = await fetchWithCsrf(urls.runOne, {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });

                // Try to parse JSON either way to surface server message
                let j = {};
                try {
                    j = await resp.json();
                } catch (_) {
                }

                if (!resp.ok || !j.success) {
                    const msg = (j && j.message) ? j.message : `HTTP ${resp.status}`;
                    li.querySelector('span').textContent = `Error ${i + 1}: ${msg}`;
                    console.error('run_one error', {status: resp.status, json: j});
                } else {
                    // Success – show preview link/thumb immediately
                    const url = extractImageUrl(j);
                    li.querySelector('span').textContent = `Done ${i + 1}`;
                    if (url && !li.querySelector('img')) {
                        const a = document.createElement('a');
                        a.href = url;
                        a.target = '_blank';
                        a.textContent = ' preview ';
                        const img = document.createElement('img');
                        img.src = url;
                        img.alt = 'preview';
                        img.style.maxHeight = '40px';
                        img.className = 'ms-2';
                        li.appendChild(a);
                        li.appendChild(img);
                    }
                }
            } catch (e) {
                li.querySelector('span').textContent = `Error ${i + 1}: ${e.message || e}`;
                console.error('run_one fetch failed', e);
            }

            // Advance progress bar
            setBar(i + 1, TCState.rows.length);
        }

        disable(false);
    });


    // Init
    document.addEventListener('DOMContentLoaded', () => {
        loadTemplates();
        // If templatecards.js already pre-selected a template and stored it in __TC_SELECTED_TEMPLATE
        if (window.__TC_SELECTED_TEMPLATE && typeof window.TC_onTemplateLoaded === 'function') {
            window.TC_onTemplateLoaded(window.__TC_SELECTED_TEMPLATE);
        }
    });
})();
