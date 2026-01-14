// public/assets/js/cart/quick-add.js
(function () {
    // ---- Endpoints (adjust if needed) ----
    const URLS = {
        quickSearch:  '/cart/quick_search', // GET ?q=
        myImages:     '/cart/my_images',    // GET ?page=&q=
        useExisting:  '/cart/use_existing', // POST dtfimage_id
        // If you later add a dedicated endpoint for saved images:
        // useSaved:  '/cart/use_saved'
    };
    async function postUseSaved(savedId) {
        const fd = new FormData();
        fd.append('saved_id', String(savedId));
        const token = attachCsrf(fd);

        const res = await fetch('/cart/use_saved', {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-Token': token || '',
                'Accept': 'application/json'
            }
        });

        let j = null; try { j = await res.json(); } catch {}
        if (!res.ok || !j || j.success === false) {
            throw new Error((j && (j.message || j.error)) || ('HTTP ' + res.status));
        }
        // Expect { success:true, id:<dtfimage_id>, order_id:<open_order_id> }
        return j;
    }
    // ---- Cookie + CSRF helpers ----
    function readCookie(name) {
        if (!name || !document.cookie) return '';
        const m = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.*+?^${}()|[\]\\])/g,'\\$1') + '=([^;]*)'));
        return m ? decodeURIComponent(m[1]) : '';
    }

    function getCsrf() {
        const cfg  = (window.CART_CFG || window.UP_CFG || {});
        const name = cfg.csrf_token_name || '_token';

        // ✅ Prefer server-injected token; fallback to cookie only if necessary
        let token = cfg.csrf_token || '';
        if (!token) {
            token = readCookie('XSRF-TOKEN') || readCookie(name) || '';
        }

        return { name, token };
    }

    function attachCsrf(fd) {
        const { name, token } = getCsrf();
        if (token) {
            if (!fd.has(name))     fd.append(name, token);   // expected POST field
            if (!fd.has('fuelcsrf')) fd.append('fuelcsrf', token); // common alias
        }
        return token;
    }

    // ---- Cart badge refresh hook ----
    function pingCartChanged() {
        window.dispatchEvent(new Event('cart:changed'));
        if (window.refreshCartIndicator) window.refreshCartIndicator();
    }

    // ---- Network helpers ----
    async function postUseExisting(dtfimageId) {
        const fd = new FormData();
        fd.append('dtfimage_id', String(dtfimageId));
        const token = attachCsrf(fd);

        const res = await fetch(URLS.useExisting, {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-Token': token || '',
                'Accept': 'application/json'
            }
        });

        let j = null; try { j = await res.json(); } catch {}
        if (!res.ok || !j || j.success === false) {
            throw new Error((j && (j.message || j.error)) || ('HTTP ' + res.status));
        }
        return j; // { success:true, id:<dtfimage_id>, order_id:<id>, ... }
    }

    // If you later support saved->cart flow directly:
    // async function postUseSaved(savedId) {
    //   const fd = new FormData();
    //   fd.append('saved_id', String(savedId));
    //   const token = attachCsrf(fd);
    //   const res = await fetch(URLS.useSaved, {
    //     method: 'POST',
    //     body: fd,
    //     credentials: 'same-origin',
    //     headers: {
    //       'X-Requested-With': 'XMLHttpRequest',
    //       'X-CSRF-Token': token || '',
    //       'Accept': 'application/json'
    //     }
    //   });
    //   const j = await res.json();
    //   if (!res.ok || !j || j.success === false) throw new Error((j && j.message) || ('HTTP ' + res.status));
    //   return j; // { success:true, id:<dtfimage_id>, order_id:<id> }
    // }

    function debounce(fn, ms) {
        let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
    }

    // ---- Typeahead search (top-right) ----
    const elSearch  = document.getElementById('qa-search');
    const elSuggest = document.getElementById('qa-suggest');

    function closeSuggest() {
        if (!elSuggest) return;
        elSuggest.classList.remove('show');
        elSuggest.innerHTML = '';
    }
    function fmtBytes(n) {
        const b = Number(n || 0);
        if (!b) return '';
        if (b < 1024) return b + ' B';
        if (b < 1024*1024) return (b/1024).toFixed(1) + ' KB';
        return (b/(1024*1024)).toFixed(1) + ' MB';
    }

    function fmtDateMaybe(item) {
        // Prefer server-sent pretty date
        if (item && item.uploaded_fmt) return String(item.uploaded_fmt);

        // Fallback: only format if we have a positive epoch seconds
        const ts = Number(item && item.date_uploaded);
        if (!Number.isFinite(ts) || ts <= 0) return '';

        const d = new Date(ts * 1000);
        if (isNaN(d.getTime())) return '';
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function renderSuggest(items) {
        if (!elSuggest) return;
        elSuggest.innerHTML = '';
        if (!items || !items.length) { closeSuggest(); return; }

        // Compute a width that fits the viewport and looks nice
        const vw     = document.documentElement.clientWidth || window.innerWidth || 1024;
        const pad    = 24;                       // keep some breathing room from the viewport edge
        const maxW   = Math.min(640, vw - pad);  // clamp to screen
        const inputW = elSearch ? elSearch.offsetWidth : 420;
        const finalW = Math.max(420, Math.min(maxW, Math.max(560, inputW)));

        elSuggest.style.minWidth = finalW + 'px';
        elSuggest.style.maxWidth = maxW + 'px';

        items.slice(0, 8).forEach(it => {
            const name = it.name || it.image_name || it.native_filename || ('#' + it.id);
            const src  = it.thumb || it.image || it.path || '';
            const subL = [];
            const when = fmtDateMaybe(it);
            if (when) subL.push(when);
            if (it.file_size) subL.push(fmtBytes(it.file_size));
            const sub = subL.join(' · ');

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'dropdown-item qa-s-item';
            btn.innerHTML = `
      <img class="qa-thumb" src="${src}" alt="">
      <div class="qa-meta">
        <div class="qa-name text-truncate" title="${name}">${name}</div>
        ${sub ? `<div class="qa-sub">${sub}</div>` : ''}
      </div>
    `;

            btn.addEventListener('click', async () => {
                closeSuggest();
                try {
                    const r = await postUseExisting(it.dtfimage_id || it.id);
                    const useId = r.id || r.dtfimage_id;
                    if (window.Cart && typeof window.Cart.addDtfImageCard === 'function' && useId && r.order_id) {
                        try { await window.Cart.addDtfImageCard(useId, r.order_id); } catch (err1) {}
                    }
                    pingCartChanged();
                } catch (e) {
                    alert(e.message || 'Failed to add.');
                }
            });

            elSuggest.appendChild(btn);
        });

        elSuggest.classList.add('show');
    }

    const doSearch = debounce(async function () {
        const q = (elSearch && elSearch.value || '').trim();
        if (!q) { closeSuggest(); return; }
        try {
            const res = await fetch(`${URLS.quickSearch}?q=${encodeURIComponent(q)}`, {
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            });
            const j = await res.json();
            if (!j || j.success === false) { closeSuggest(); return; }
            renderSuggest(j.items || j.results || []);
        } catch (_) {
            closeSuggest();
        }
    }, 180);

    if (elSearch && elSuggest) {
        elSearch.addEventListener('input', doSearch);
        document.addEventListener('click', (e) => {
            if (!elSuggest.contains(e.target) && e.target !== elSearch) closeSuggest();
        });
    }

    // ---- Saved Images modal (grid + paging) ----
    const elBrowse = document.getElementById('qa-browse');
    const modalEl  = document.getElementById('qa-modal');
    const grid     = document.getElementById('qa-grid');
    const moreWrap = document.getElementById('qa-more');
    const emptyEl  = document.getElementById('qa-empty');
    const qInput   = document.getElementById('qa-modal-search');
    const refresh  = document.getElementById('qa-modal-refresh');

    let page = 1, hasMore = true, loading = false, qStr = '';

    function cardHtml(it) {
        const name     = it.name || it.image_name || it.native_filename || ('#' + it.id);
        const src      = it.thumb || it.image || it.path || '';
        const uploaded = it.uploaded_fmt || ''; // server may send date-only string
        const dtfAttr  = it.dtfimage_id ? ` data-dtfimage-id="${String(it.dtfimage_id)}"` : '';

        return `
      <div class="col-6 col-sm-4 col-md-3 col-lg-2">
        <div class="card h-100"${dtfAttr}>
          <div class="ratio ratio-1x1 bg-light">
            <img src="${src}" alt="" class="img-fluid" style="object-fit:contain;">
          </div>
          <div class="card-body p-2">
            <div class="small text-truncate" title="${name}">${name}</div>
            ${uploaded ? `<div class="text-muted small">${uploaded}</div>` : ``}
            <button class="btn btn-sm btn-primary w-100 qa-add mt-2" data-id="${String(it.id)}">Add</button>
          </div>
        </div>
      </div>
    `;
    }

    async function loadPage(reset=false) {
        if (loading) return;
        loading = true;

        if (reset) {
            page = 1; hasMore = true;
            if (grid) grid.innerHTML = '';
            if (emptyEl) emptyEl.classList.add('d-none');
        }
        if (!hasMore) { loading = false; return; }

        try {
            const res = await fetch(`${URLS.myImages}?page=${page}&q=${encodeURIComponent(qStr)}`, {
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            });
            const j = await res.json();
            const items = (j && (j.items || j.results)) || [];
            const next  = (j && (j.next_page || j.has_more)) || false;

            if (!items.length && page === 1) {
                if (emptyEl) emptyEl.classList.remove('d-none');
            }
            if (grid && items.length) {
                grid.insertAdjacentHTML('beforeend', items.map(cardHtml).join(''));
            }

            hasMore = !!next;
            if (moreWrap) moreWrap.classList.toggle('d-none', !hasMore);

            page += 1;
        } catch (e) {
            console.warn('[quick-add] loadPage failed', e);
        } finally {
            loading = false;
        }
    }

    function wireGridClicks() {
        if (!grid) return;
        grid.addEventListener('click', async (e) => {
            const btn = e.target.closest('.qa-add');
            if (!btn) return;

            const card = btn.closest('.card');
            const savedId = btn.getAttribute('data-id');
            const dtfId   = card && card.getAttribute('data-dtfimage-id'); // if API included it

            btn.disabled = true;
            const prev = btn.textContent;
            btn.textContent = 'Adding…';

            try {
                // Prefer dtfimage_id when available; else assume list already returns dtfimages (id)
                const r = dtfId
                ? await postUseExisting(dtfId)
                    : await postUseSaved(savedId);

                const useId = r.id || r.dtfimage_id;
                if (window.Cart && typeof window.Cart.addDtfImageCard === 'function' && useId && r.order_id) {
                    try { await window.Cart.addDtfImageCard(useId, r.order_id); } catch (err2) {}
                }
                pingCartChanged();

                btn.textContent = 'Added ✓';
                setTimeout(() => { btn.textContent = prev; btn.disabled = false; }, 800);
            } catch (er) {
                btn.disabled = false;
                btn.textContent = prev;
                alert(er.message || 'Failed to add.');
            }
        });
    }

    if (elBrowse && modalEl) {
        elBrowse.addEventListener('click', async () => {
            const m = window.bootstrap ? new bootstrap.Modal(modalEl) : null;
            if (m) m.show();
            await loadPage(true);
        });

        if (moreWrap) {
            moreWrap.addEventListener('click', (e) => {
                const b = e.target.closest('button'); if (!b) return;
                loadPage(false);
            });
        }

        if (qInput) {
            qInput.addEventListener('input', debounce(() => {
                qStr = (qInput.value || '').trim();
                loadPage(true);
            }, 220));
        }

        if (refresh) {
            refresh.addEventListener('click', () => loadPage(true));
        }

        wireGridClicks();
    }
})();
