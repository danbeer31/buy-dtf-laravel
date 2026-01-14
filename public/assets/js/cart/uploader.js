// public/assets/js/uploader/uploader.js
(function () {
    /* =========================
       Config + helpers
       ========================= */
    function getCfg() {
        const g = (typeof window !== 'undefined' && window.UP_CFG) ? window.UP_CFG : {};
        const cart = (typeof window !== 'undefined' && window.CART_CFG) ? window.CART_CFG : {};
        return {
            preflight_url:   g.preflight_url   || cart.preflight_url   || '/cart/preflight',
            put_url:         g.put_url         || cart.put_url         || '/cart/put',
            status_url:      g.status_url      || cart.status_url      || '/cart/status',
            csrf_token:      g.csrf_token      || cart.csrf_token      || '',
            csrf_token_name: g.csrf_token_name || cart.csrf_token_name || '_token',
            accept:          Array.isArray(g.accept) ? g.accept : (Array.isArray(cart.accept) ? cart.accept : ['image/png','image/svg+xml','application/pdf']),
            max_size_mb:     g.max_size_mb || cart.max_size_mb || 50,
            source_order_id: g.source_order_id || cart.source_order_id || '',
            dupe_check_url:  g.dupe_check_url  || cart.dupe_check_url  || '/cart/dupe_check',
            dupe_check_hash_url: g.dupe_check_hash_url || cart.dupe_check_hash_url || '/cart/dupe_check_hash',
            use_existing_url: g.use_existing_url || cart.use_existing_url || '/cart/use_existing'
        };
    }
    window.addEventListener('cart:changed', () => {
        if (typeof window.refreshCartIndicator === 'function') {
            window.refreshCartIndicator();
        }
    });
    function readCookie(name) {
        if (!name) return null;
        const escaped = name.replace(/([.*+?^${}()|[\]\\])/g, '\\$1');
        const m = document.cookie.match(new RegExp('(?:^|; )' + escaped + '=([^;]*)'));
        return m ? decodeURIComponent(m[1]) : null;
    }

    function getLiveCsrf() {
        // First try the meta tag which is standard in Laravel
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) return { name: '_token', token: meta.content };

        const cartCfg = getCartCfg();
        const cfg  = getCfg();
        const name = cartCfg.csrf_token_name || cfg.csrf_token_name || '_token';
        let tok = cartCfg.csrf_token || cfg.csrf_token;
        if (!tok) {
            tok = readCookie('XSRF-TOKEN') || readCookie(name) || '';
        }
        return { name, token: tok };
    }

    function getCartCfg() {
        return (typeof window !== 'undefined' && window.CART_CFG) ? window.CART_CFG : {};
    }

    // Compute SHA-256 of the original file bytes
    async function sha256Hex(file) {
        if (!('crypto' in window) || !window.crypto.subtle) return null;
        const buf = await file.arrayBuffer();
        const hash = await crypto.subtle.digest('SHA-256', buf);
        const bytes = new Uint8Array(hash);
        return Array.from(bytes).map(b => b.toString(16).padStart(2,'0')).join('');
    }

    function getSourceOrderId() {
        const inp = document.querySelector('[name="source_order_id"]');
        if (inp && inp.value) return String(inp.value);
        const cfg = getCfg();
        return cfg.source_order_id ? String(cfg.source_order_id) : '';
    }

    (function sanityLog() {
        const c = getCfg();
        if (!c.preflight_url || !c.put_url || !c.status_url) {
            console.warn('[uploader] Missing endpoints in UP_CFG; using defaults.', c);
        }
    })();

    function postJSON(url, data) {
        const fd = new FormData();
        Object.keys(data || {}).forEach(k => fd.append(k, data[k]));
        const live = getLiveCsrf();
        if (live.token) {
            if (!fd.has('_token'))          fd.append('_token', live.token);
            if (!fd.has('fuel_csrf_token')) fd.append('fuel_csrf_token', live.token);
            if (!fd.has('fuelcsrf'))        fd.append('fuelcsrf', live.token);
        }
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-CSRF-TOKEN': live.token || '',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: fd
        }).then(async (res) => {
            let j=null; try { j = await res.json(); } catch {}
            if (!res.ok || !j || j.success === false) {
                throw new Error((j && j.message) || ('HTTP ' + res.status));
            }
            return j;
        });
    }

    function bytesStr(n) {
        if (!Number.isFinite(n)) return '';
        if (n < 1024) return n + ' B';
        if (n < 1024*1024) return (n/1024).toFixed(1) + ' KB';
        return (n/(1024*1024)).toFixed(1) + ' MB';
    }

    /* =========================
       PROGRESS DOCK (floating)
       ========================= */
    let dock, dockBarInner, dockTitle, dockLine, dockClose, dockView;
    let batchTotal = 0, batchCompleted = 0, batchSucceeded = 0, batchActive = false;
    let resetTimer = null;

    function injectDockStyles() {
        if (document.getElementById('upload-dock-style')) return;
        const css = document.createElement('style');
        css.id = 'upload-dock-style';
        css.textContent = `
#upload-dock{position:fixed;right:16px;bottom:16px;z-index:2147483647;width:320px;max-width:86vw;background:#fff;border:1px solid rgba(0,0,0,.1);box-shadow:0 6px 24px rgba(0,0,0,.18);border-radius:12px;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
#upload-dock .ud-h{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-bottom:1px solid rgba(0,0,0,.05)}
#upload-dock .ud-h .ud-title{font-weight:600;font-size:14px}
#upload-dock .ud-h .ud-actions{display:flex;gap:8px}
#upload-dock .ud-h button, #upload-dock .ud-h a{appearance:none;border:0;background:transparent;padding:4px 6px;border-radius:6px;cursor:pointer;font-size:12px;color:#0d6efd;text-decoration:none}
#upload-dock .ud-h button:hover, #upload-dock .ud-h a:hover{background:rgba(13,110,253,.08)}
#upload-dock .ud-body{padding:10px 12px}
#upload-dock .ud-line{font-size:12px;color:#555;margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#upload-dock .ud-bar{width:100%;height:8px;background:#e9ecef;border-radius:999px;overflow:hidden}
#upload-dock .ud-bar .ud-bar-inner{height:100%;width:0%;background:#0d6efd;transition:width .2s ease;border-radius:999px}
@media (max-width:480px){#upload-dock{right:8px;left:8px;bottom:8px;width:auto}}
/* Dupe modal */
#dupe-overlay{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:2147483646;display:none}
#dupe-modal{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:min(720px,92vw);max-height:80vh;overflow:auto;background:#fff;border-radius:12px;box-shadow:0 16px 40px rgba(0,0,0,.28);z-index:2147483647}
#dupe-modal .dm-h{display:flex;justify-content:space-between;align-items:center;padding:12px 14px;border-bottom:1px solid rgba(0,0,0,.08);font-weight:600}
#dupe-modal .dm-b{padding:12px 14px}
#dupe-modal .dm-f{display:flex;justify-content:flex-end;gap:8px;padding:10px 14px;border-top:1px solid rgba(0,0,0,.08)}
#dupe-modal .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px}
#dupe-modal .card{border:1px solid rgba(0,0,0,.08);border-radius:10px;overflow:hidden;background:#fff}
#dupe-modal .ratio{position:relative;width:100%;padding-top:100%;background:#f6f7f9}
#dupe-modal .ratio > img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}
#dupe-modal .c-body{padding:10px}
#dupe-modal .btn{appearance:none;border:1px solid rgba(0,0,0,.2);background:#f8f9fa;border-radius:8px;padding:6px 10px;cursor:pointer}
#dupe-modal .btn.primary{background:#0d6efd;color:#fff;border-color:#0d6efd}
.badge-note{display:inline-block;margin-left:6px;padding:2px 6px;border-radius:6px;background:#e7f1ff;color:#0d6efd;font-size:11px}
        `;
        document.head.appendChild(css);
    }

    function ensureDock() {
        if (dock) return dock;
        injectDockStyles();
        dock = document.createElement('div');
        dock.id = 'upload-dock';
        dock.setAttribute('role', 'status');
        dock.setAttribute('aria-live', 'polite');
        dock.innerHTML = `
            <div class="ud-h">
                <div class="ud-title">Uploading files</div>
                <div class="ud-actions">
                    <a href="#" class="ud-view" title="View uploads">View</a>
                    <button type="button" class="ud-close" title="Hide">Hide</button>
                </div>
            </div>
            <div class="ud-body">
                <div class="ud-line">Starting…</div>
                <div class="ud-bar"><div class="ud-bar-inner"></div></div>
            </div>
        `;
        document.body.appendChild(dock);
        dockTitle     = dock.querySelector('.ud-title');
        dockLine      = dock.querySelector('.ud-line');
        dockBarInner  = dock.querySelector('.ud-bar-inner');
        dockClose     = dock.querySelector('.ud-close');
        dockView      = dock.querySelector('.ud-view');

        dockClose.addEventListener('click', (e) => {
            e.preventDefault();
            dock.style.display = 'none';
        });
        dockView.addEventListener('click', (e) => {
            e.preventDefault();
            const anchor = document.getElementById('upload-card')
                || document.getElementById('drop-area')
                || document.getElementById('queue')
                || document.body;
            anchor?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
        });
        return dock;
    }

    // Reset all UI/counters after a completed batch
    function resetForNextRun() {
        const queue = document.getElementById('queue');
        const input = document.getElementById('file-input');

        if (queue) queue.innerHTML = '';
        if (input) input.value = '';

        if (dock) {
            dock.style.display = 'none';
            dockTitle.textContent = 'Uploading files';
            dockLine.textContent = '0 / 0';
            dockBarInner.style.width = '0%';
        }

        batchTotal = 0;
        batchCompleted = 0;
        batchSucceeded = 0;
        batchActive = false;
        resetTimer = null;

        window.dispatchEvent(new CustomEvent('uploader:reset'));
    }

    // Serialize batches so new picks merge into the active run
    let uploadChain = Promise.resolve();

    // Cumulative dock (do not reset while a batch is active)
    function showDock(additional) {
        ensureDock();

        if (!batchActive) {
            batchTotal = 0;
            batchCompleted = 0;
            batchSucceeded = 0;
            batchActive = true;
            dockTitle.textContent = 'Uploading files';
            dockBarInner.style.width = '0%';
            dock.style.display = 'block';
        }

        batchTotal += (additional || 0);
        dockLine.textContent = `${batchCompleted} / ${batchTotal} • Queued`;
    }

    function updateDockForFile(fileName, perFilePct, phase) {
        if (!dock || !batchActive || batchTotal <= 0) return;
        const overall = Math.max(0, Math.min(100, ((batchCompleted + (perFilePct/100)) / batchTotal) * 100));
        dockBarInner.style.width = overall.toFixed(1) + '%';
        const shortName = (fileName || '').toString();
        dockLine.textContent = `${batchCompleted} / ${batchTotal} • ${phase}${shortName ? ' — ' + shortName : ''}`;
    }

    function markFileDone() {
        if (!dock) return;
        batchCompleted++;
        const overall = Math.max(0, Math.min(100, (batchCompleted / Math.max(1,batchTotal)) * 100));
        dockBarInner.style.width = overall.toFixed(1) + '%';
        dockLine.textContent = `${batchCompleted} / ${batchTotal} • Completed`;

        if (batchCompleted >= batchTotal && batchActive) {
            batchActive = false;
            if (resetTimer) clearTimeout(resetTimer);
            resetTimer = setTimeout(resetForNextRun, 1000);
        }
    }

    /* =========================
       Reload behavior (disabled)
       ========================= */
    const RELOAD_AFTER_ALL_DONE = false;
    const RELOAD_DELAY_MS = 300;
    function triggerReload() {
        if (!RELOAD_AFTER_ALL_DONE) return;
        dockTitle.textContent = 'Uploads complete';
        dockLine.textContent = `Reloading…`;
        dockBarInner.style.width = '100%';
        setTimeout(() => { window.location.reload(); }, RELOAD_DELAY_MS);
    }

    /* =========================
       DOM refs + small utils
       ========================= */
    const drop  = document.getElementById('drop-area');
    const pick  = document.getElementById('pick-btn');
    const input = document.getElementById('file-input');
    const queue = document.getElementById('queue');

    function el(tag, cls){ const n=document.createElement(tag); if(cls) n.className=cls; return n; }
    function human(n){ if(n>=1048576) return (n/1048576).toFixed(1)+' MB'; if(n>=1024) return (n/1024).toFixed(1)+' KB'; return n+' B'; }

    function isAccepted(file) {
        const mime = (file.type || '').toLowerCase();
        const name = (file.name || '').toLowerCase();
        if (mime === 'image/png' || mime === 'image/x-png' || name.endsWith('.png')) return true;
        if (mime === 'image/svg+xml' || name.endsWith('.svg')) return true;
        if (mime === 'application/pdf' || name.endsWith('.pdf')) return true;
        return false;
    }

    // Create a card (TOP-DOWN: append instead of prepend)
    function makeCard(file, uploadId){
        const card = el('div', 'card mb-3');
        const body = el('div', 'card-body');

        const head = el('div', 'd-flex align-items-center justify-content-between');
        const left = el('div');
        left.innerHTML = `<strong>${file.name}</strong><div class="text-muted small">${file.type || 'unknown'} • ${human(file.size)}</div>`;
        const right = el('div', 'badge bg-secondary');
        right.textContent = 'Queued';
        head.append(left, right);

        const barWrap = el('div', 'progress mt-3');
        const bar = el('div', 'progress-bar');
        bar.style.width='0%';
        bar.setAttribute('aria-valuenow','0');
        barWrap.append(bar);

        const meta = el('div', 'mt-2 small text-muted');

        body.append(head, barWrap, meta);
        card.append(body);
        card.dataset.id = uploadId;

        queue && queue.prepend(card);

        return { card, right, bar, meta };
    }

    function setPhase(els, phase, pct, txt){
        els.right.className = 'badge bg-secondary';
        if (phase === 'uploading')  els.right.className = 'badge bg-info text-dark';
        if (phase === 'processing') els.right.className = 'badge bg-warning text-dark';
        if (phase === 'ready')      els.right.className = 'badge bg-success';
        if (phase === 'error')      els.right.className = 'badge bg-danger';
        els.right.textContent = txt || phase;

        if (typeof pct === 'number') {
            const v = Math.max(0, Math.min(100, pct));
            els.bar.style.width = v + '%';
            els.bar.setAttribute('aria-valuenow', String(v));
        }
    }

    function appendCsrf(fd) {
        const { token } = getLiveCsrf();
        if (token) {
            if (!fd.has('_token'))          fd.append('_token', token);
            if (!fd.has('fuel_csrf_token')) fd.append('fuel_csrf_token', token);
            if (!fd.has('fuelcsrf'))        fd.append('fuelcsrf', token);
        }
    }

    /* =========================
       Dupe modal (pure JS; no Bootstrap JS required)
       ========================= */
    let dupeOverlay = null, dupeModal = null, activeListHandler = null;

    function ensureDupeModal() {
        injectDockStyles();
        if (!dupeOverlay) {
            dupeOverlay = document.createElement('div');
            dupeOverlay.id = 'dupe-overlay';
            document.body.appendChild(dupeOverlay);
        }
        if (!dupeModal) {
            dupeModal = document.createElement('div');
            dupeModal.id = 'dupe-modal';
            dupeModal.innerHTML = `
                <div class="dm-h">
                    <div>We found matching uploads<span class="badge-note js-note" style="display:none"></span></div>
                    <button type="button" class="btn js-close">Close</button>
                </div>
                <div class="dm-b">
                    <div class="text-muted" style="margin-bottom:8px">
                        It looks like you’ve uploaded <code class="js-fname"></code> (<span class="js-fsize"></span>) before. Use one of these instead?
                    </div>
                    <div class="grid js-list"></div>
                </div>
                <div class="dm-f">
                    <button type="button" class="btn js-new">Upload new anyway</button>
                </div>
            `;
            document.body.appendChild(dupeModal);
            dupeModal.querySelector('.js-close').addEventListener('click', hideDupeModal);
            dupeModal.querySelector('.js-new').addEventListener('click', () => { resolveDupe && resolveDupe({ decision: 'upload_new' }); hideDupeModal(); });
        }
    }

    function showDupeModal() {
        ensureDupeModal();
        dupeOverlay.style.display = 'block';
        dupeModal.style.display = 'block';
    }

    function hideDupeModal() {
        if (dupeOverlay) dupeOverlay.style.display = 'none';
        if (dupeModal) dupeModal.style.display = 'none';
        // Clean up old listener if any
        const list = dupeModal && dupeModal.querySelector('.js-list');
        if (list && activeListHandler) {
            list.removeEventListener('click', activeListHandler);
            activeListHandler = null;
        }
    }

    // Build+show the modal, return Promise with user's decision
    function showDupePickerModal(matches, file, opts = {}) {
        ensureDupeModal();
        const list = dupeModal.querySelector('.js-list');
        const note = dupeModal.querySelector('.js-note');
        dupeModal.querySelector('.js-fname').textContent  = file.name;
        dupeModal.querySelector('.js-fsize').textContent  = bytesStr(file.size);
        if (opts.exact) { note.style.display = 'inline-block'; note.textContent = 'Exact file match'; }
        else { note.style.display = 'none'; note.textContent = ''; }
        list.innerHTML = '';

        // Dedupe matches on frontend as a safety measure
        const uniqueMatches = dedupeMatches(matches);

        uniqueMatches.forEach(m => {
            const card = document.createElement('div');
            card.className = 'card';
            card.innerHTML = `
                <div class="ratio"><img src="${m.thumb || m.path}" alt=""></div>
                <div class="c-body">
                    <div class="small text-muted">${m.native_filename || ''}</div>
                    <div class="fw-semibold" style="font-weight:600">${m.image_name || ''}</div>
                    <div class="text-muted small">${bytesStr(m.file_size || 0)} · ${m.uploaded || ''}</div>
                    <button type="button" class="btn primary w-100 js-use" data-id="${m.id}">Use this</button>
                </div>
            `;
            list.appendChild(card);
        });

        return new Promise((resolve) => {
            resolveDupe = (r) => resolve(r);
            activeListHandler = async (e) => {
                const btn = e.target.closest('.js-use');
                if (!btn) return;
                btn.disabled = true;
                try {
                    const cfg = getCfg();
                    const url = cfg.use_existing_url || '/cart/use_existing';
                    const r = await postJSON(url, {
                        dtfimage_id: btn.getAttribute('data-id')
                    });
                    hideDupeModal();
                    // 🔔 cart changed
                    window.dispatchEvent(new Event('cart:changed'));
                    if (typeof window.refreshCartIndicator === 'function') {
                        window.refreshCartIndicator();
                    } else {
                        // fallback to finding the badge if global helper isn't there
                        const badge = document.getElementById('cart-badge');
                        if (badge) {
                            const current = parseInt(badge.textContent) || 0;
                            badge.textContent = current + 1;
                            badge.classList.remove('d-none');
                        }
                    }
                    resolve({ decision: 'use_existing', id: r.id, order_id: r.order_id });
                } catch (er) {
                    console.error(er);
                    btn.disabled = false;
                }
            };
            list.addEventListener('click', activeListHandler);
            showDupeModal();
        });
    }
    let resolveDupe = null;

    function dedupeMatches(list) {
        const seen = new Map();
        for (const m of (list || [])) {
            // Primarily dedupe by the image file path itself
            const key = String(m.path || m.thumb || m.id).toLowerCase();
            if (!seen.has(key)) {
                seen.set(key, m);
            } else {
                // If we have multiple, maybe keep the one with a name if the seen one doesn't?
                // Or just stick with the first one found (usually newest due to orderBy id desc)
            }
        }
        return Array.from(seen.values());
    }
    // Hash-first dupe check; fallback to filename+size. Returns {decision, id?, order_id?, sha256?}
    async function checkDupesAndMaybeUseExisting(file) {
            try {
                let matches = [];
                let exact = false;
                const cfg = getCfg();
                let sha = null;

            try {
                sha = await sha256Hex(file);
                const url = cfg.dupe_check_hash_url || '/cart/dupe_check_hash';
                const r1 = await postJSON(url, { sha256: sha });
                if (r1 && r1.success && Array.isArray(r1.matches) && r1.matches.length) {
                    matches = r1.matches;
                    exact = true;
                }
            } catch (err3) {
                console.warn('[uploader] hash check failed', err3);
            }

            if (!matches.length) {
                const url = cfg.dupe_check_url || '/cart/dupe_check';
                const r2 = await postJSON(url, { filename: file.name, size: file.size });
                if (r2 && r2.success && Array.isArray(r2.matches)) matches = r2.matches;
            }

            if (matches.length > 0) {
                // Use the managed helper (no extra listeners)
                const result = await showDupePickerModal(matches, file, { exact });
                return { ...result, sha256: sha };
            }
            return { decision: 'upload_new', sha256: sha };
        } catch (e) {
            console.warn('[uploader] dupe_check failed; proceeding with upload', e);
            return { decision: 'upload_new' };
        }
    }

    /* =========================
       Network calls for upload
       ========================= */
    async function preflight(file){
        const cfg = getCfg();
        const form = new FormData();
        form.append('name', file.name);
        form.append('size', String(file.size));
        form.append('mime', file.type || '');
        const sid = getSourceOrderId();
        if (sid) form.append('source_order_id', sid);
        appendCsrf(form);

        const live = getLiveCsrf();
        const res = await fetch(cfg.preflight_url, {
            method: 'POST',
            body: form,
            credentials: 'same-origin',
            headers: {
                'X-CSRF-TOKEN': live.token || '',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        let j=null; try { j = await res.json(); } catch {}
        if (!j || !j.success || !j.upload_id) {
            throw new Error((j && j.message) || `Preflight failed (${res.status})`);
        }
        return j.upload_id;
    }

    // Map upload progress (0–100) to visual 0–50; on upload-finished show Processing at 50%; Ready = 100%
    async function putFile(file, uploadId, els, extras){
        const cfg = getCfg();
        if (!uploadId) throw new Error('Missing upload id');
        const url = `${cfg.put_url}/${encodeURIComponent(uploadId)}`;

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', url, true);
            xhr.responseType = 'json';

            const live = getLiveCsrf();
            xhr.setRequestHeader('X-CSRF-TOKEN', live.token || '');
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

            const fd = new FormData();
            fd.append('file', file);
            // stateless hints
            fd.append('name', file.name);
            fd.append('size', String(file.size));
            fd.append('mime', file.type || '');
            const sid = getSourceOrderId();
            if (sid) fd.append('source_order_id', sid);
            if (extras && extras.sha256) fd.append('sha256', extras.sha256); // optional/debug
            appendCsrf(fd);

            // Upload progress → 0..100%
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const pctUpload = Math.round((e.loaded / e.total) * 100); // 0..100
                    setPhase(els, 'uploading', pctUpload, `Uploading ${Math.max(1, pctUpload)}%`);
                    updateDockForFile(file.name, pctUpload, 'Uploading');
                }
            };

            // Upload finished sending body, waiting on server → 100% "Processing…"
            xhr.upload.onload = () => {
                setPhase(els, 'processing', 100, 'Processing…');
                updateDockForFile(file.name, 100, 'Processing');
            };

            // Response received
            xhr.onload = () => {
                const j = xhr.response || {};
                if (xhr.status >= 200 && xhr.status < 300 && (j.success || j.status === 'uploaded')) {
                    setPhase(els, 'ready', 100, 'Ready');
                    updateDockForFile(file.name, 100, 'Ready');
                    if (j.meta) {
                        const m = j.meta;
                        els.meta.textContent =
                            `Saved • ${m.width_px}×${m.height_px}px @ 300 DPI • ${m.width_in}" × ${m.height_in}" • Order #${j.order_id}`;
                    } else if (j.dtfimage_id) {
                         els.meta.textContent = `Saved to Order #${j.order_id}`;
                    }
                    const dtfimageId = j.dtfimage_id;
                    const orderId    = j.order_id;
                    if (window.Cart && typeof window.Cart.addDtfImageCard === 'function' && dtfimageId && orderId) {
                        try { window.Cart.addDtfImageCard(dtfimageId, orderId); } catch (e) {}
                    }
                    window.dispatchEvent(new Event('cart:changed'));
                    if (typeof window.refreshCartIndicator === 'function') {
                        window.refreshCartIndicator();
                    } else {
                        // fallback to finding the badge if global helper isn't there
                        const badge = document.getElementById('cart-badge');
                        if (badge) {
                            const current = parseInt(badge.textContent) || 0;
                            badge.textContent = current + 1;
                            badge.classList.remove('d-none');
                        }
                    }
                    resolve(true);
                } else {
                    setPhase(els, 'error', 100, 'Error');
                    updateDockForFile(file.name, 100, 'Error');
                    els.meta.textContent = (j && j.message) || `Upload failed (${xhr.status})`;
                    reject(new Error(els.meta.textContent));
                }
            };

            xhr.onerror = () => {
                setPhase(els, 'error', 100, 'Network error');
                updateDockForFile(file.name, 100, 'Network error');
                reject(new Error('Network error'));
            };

            xhr.send(fd);
        });
    }

    // Process a batch (runs after any previous batches via uploadChain)
    async function processQueue(queueItems) {
        for (const it of queueItems) {
            try {
                await putFile(it.file, it.uploadId, it.els, { sha256: it.sha256 || null });
                batchSucceeded++;
            } catch (e) {
                // error state already shown
            } finally {
                markFileDone();
            }
        }

        if (!batchActive && batchCompleted >= batchTotal) {
            triggerReload();
        }
    }

    /* =========================
       Flow: show all cards immediately; dupe check; then upload if needed
       ========================= */
    async function handleFiles(files){
        // 1) Build items & show ALL cards immediately (top-down order via append)
        const items = [];
        for (const file of files) {
            if (!isAccepted(file)) {
                alert(`"${file.name}" is not an accepted type (${file.type || 'unknown'}). Only PNG, SVG, PDF.`);
                continue;
            }
            if (/\.(jpe?g)$/i.test(file.name)) {
                alert(`"${file.name}" is a JPG. Please upload PNG, SVG, or PDF.`);
                continue;
            }

            const tempId = 'pending-'+Math.random().toString(36).slice(2);
            const els = makeCard(file, tempId);
            setPhase(els, 'queued', 0, 'Queued');
            items.push({ file, els, uploadId: null, error: null, sha256: null });
        }
        if (!items.length) return;

        // 2) Show/extend the dock for ALL accepted items (some may be reused)
        showDock(items.length);

        // 3) For each item: run dupe check first. If user reuses, skip upload.
        const toUpload = [];
        for (const it of items) {
            try {
                const choice = await checkDupesAndMaybeUseExisting(it.file);
                // keep the computed sha256 (if any) for sending with upload
                if (choice && choice.sha256) it.sha256 = choice.sha256;

                if (choice && choice.decision === 'use_existing') {
                    setPhase(it.els, 'ready', 100, 'Reused');
                    it.els.meta.textContent = 'Reused existing image';
                    if (window.Cart && typeof window.Cart.addDtfImageCard === 'function' && choice.id && choice.order_id) {
                        try { window.Cart.addDtfImageCard(choice.id, choice.order_id); } catch (err2) {}
                    }
                    markFileDone();
                    continue;
                }
            } catch (err1) {
                // Dupe check failed → proceed with normal upload
            }

            // 4) Preflight (only for those still needing upload)
            try {
                const id = await preflight(it.file);
                it.uploadId = id;
                if (it.els && it.els.card) it.els.card.dataset.id = id;
                setPhase(it.els, 'queued', 0, 'Queued');
                toUpload.push(it);
            } catch (err) {
                it.error = err;
                setPhase(it.els, 'error', 100, 'Preflight error');
                it.els.meta.textContent = err.message || 'Preflight failed';
                markFileDone();
            }
        }

        // 5) Upload the remaining items (after current chain)
        if (toUpload.length > 0) {
            uploadChain = uploadChain.then(() => processQueue(toUpload));
        }
    }

    /* =========================
       UI wiring
       ========================= */
    if (pick)  pick.addEventListener('click', () => input && input.click());
    if (input) input.addEventListener('change', (e) => {
        const files = Array.from(e.target.files || []);
        if (files.length) handleFiles(files);
        input.value = '';
    });

    if (drop) {
        let dragDepth = 0;

        ['dragenter','dragover'].forEach((evt) => {
            drop.addEventListener(evt, (e) => {
                e.preventDefault(); e.stopPropagation();
                if (evt === 'dragenter') dragDepth++;
                drop.classList.add('bg-light');
            });
        });

        drop.addEventListener('dragleave', (e) => {
            e.preventDefault(); e.stopPropagation();
            dragDepth = Math.max(0, dragDepth - 1);
            if (dragDepth === 0) drop.classList.remove('bg-light');
        });

        drop.addEventListener('drop', (e) => {
            e.preventDefault(); e.stopPropagation();
            dragDepth = 0;
            drop.classList.remove('bg-light');
            const files = Array.from(e.dataTransfer?.files || []);
            if (files.length) handleFiles(files);
        });
    }

    // Clipboard paste (PNG only)
    document.addEventListener('paste', (e) => {
        const items = e.clipboardData && e.clipboardData.items ? Array.from(e.clipboardData.items) : [];
        const imgs = items.filter(it => it.kind === 'file' && it.type === 'image/png');
        if (!imgs.length) return;
        const files = imgs.map(it => it.getAsFile());
        handleFiles(files);
    });
})();

/* =========================
   (Legacy drawer helper kept as-is in case you still use it)
   ========================= */
(function () {
    const Q         = document.getElementById('queue');
    const drawer    = document.getElementById('upload-drawer');
    const bar       = drawer ? drawer.querySelector('.js-bar') : null;
    const statusEl  = drawer ? drawer.querySelector('.js-status') : null;
    const fileInput = document.getElementById('file-input');

    let total = 0, done = 0, resetTimer = null;

    function showDrawer() {
        if (drawer) drawer.classList.remove('d-none');
    }

    function hideDrawer() {
        if (drawer) drawer.classList.add('d-none');
    }

    function updateDrawer() {
        if (!bar || !statusEl) return;
        const pct = total ? Math.round((done / total) * 100) : 0;
        bar.style.width = pct + '%';
        statusEl.textContent = `${done} / ${total} · ${done >= total && total > 0 ? 'Completed' : 'Uploading'}`;
    }

    function startBatch(n) {
        if (resetTimer) { clearTimeout(resetTimer); resetTimer = null; }
        total = n; done = 0;
        showDrawer();
        updateDrawer();
    }

    function oneDone() {
        done++;
        updateDrawer();

        if (done >= total && total > 0) {
            resetTimer = setTimeout(resetUI, 1000);
        }
    }

    function resetUI() {
        if (window.UploaderPoll && typeof window.UploaderPoll.stop === 'function') {
            try { window.UploaderPoll.stop(); } catch (e) {}
        }

        if (Q) Q.innerHTML = '';
        if (fileInput) fileInput.value = '';
        if (bar) bar.style.width = '0%';
        if (statusEl) statusEl.textContent = '0 / 0';
        hideDrawer();

        total = 0; done = 0; resetTimer = null;

        window.dispatchEvent(new CustomEvent('uploader:reset'));
    }

    window.UploaderBatch = { startBatch, oneDone, resetUI };
})();
