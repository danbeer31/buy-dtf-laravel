(function () {
    const CFG = (window.CART_CFG || {});
    const CSRF_COOKIE = (CFG.csrf_cookie_name || 'fuel_csrf_token');
    const LIST_SEL = CFG.list_selector || '#img-grid';

    function readCookie(name) {
        const m = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'));
        return m ? decodeURIComponent(m[1]) : '';
    }
    function getToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) return meta.content;
        return readCookie(CSRF_COOKIE) || (CFG.csrf_token || '');
    }
    function initNewCard(root) {
        window.dispatchEvent(new CustomEvent('dtfimage:card-added', { detail: { el: root } }));
    }

    // Ensure a grid exists; if not, create it just before #upload-card
    function ensureListContainer() {
        let list = document.querySelector(LIST_SEL);
        if (list) return list;

        const uploadCard = document.getElementById('upload-card');
        if (!uploadCard || !uploadCard.parentNode) return null;

        list = document.createElement('div');
        list.id = 'img-grid';
        list.className = 'row g-3';
        uploadCard.parentNode.insertBefore(list, uploadCard);
        return list;
    }

    async function fetchCardHTML(dtfimageId, orderId) {
        const body = new URLSearchParams();
        body.set('dtfimage_id', dtfimageId);
        body.set('order_id', orderId);
        body.set(CFG.csrf_token_name || '_token', getToken());

        const res = await fetch('/cart/render_dtfimage_card', {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-TOKEN': getToken()
            },
            body
        });

        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
    }

    async function addDtfImageCard(dtfimageId, orderId) {
        try {
            const data = await fetchCardHTML(dtfimageId, orderId);
            if (!data || !data.success || !data.html) {
                console.warn('Render failed:', data && data.msg);
                return false;
            }

            const list = ensureListContainer();
            if (!list) {
                console.error('Could not create/find card list container.');
                return false;
            }

            // remove the empty-state alert if present
            const empty = document.getElementById('no-images-alert');
            if (empty) empty.remove();

            // enable the "Place order" button if it was disabled
            const place = document.querySelector('a.btn.btn-success');
            if (place) {
                place.classList.remove('disabled');
                place.removeAttribute('aria-disabled');
                place.removeAttribute('tabindex');
            }

            // insert the new card
            list.insertAdjacentHTML('beforeend', data.html.trim());  // APPEND

            // init the just-inserted node
            const newCard = list.lastElementChild; // we inserted at the end
            if (newCard) {
                initNewCard(newCard);
                // Also initialize proportion lock for the new card specifically
                if (window.DTF && typeof window.DTF.initProportionLock === 'function') {
                    window.DTF.initProportionLock(newCard.querySelector('.image-card') || newCard);
                }
            }

            return true;
        } catch (err) {
            console.error('addDtfImageCard error:', err);
            return false;
        }
    }

    window.Cart = window.Cart || {};
    window.Cart.addDtfImageCard = addDtfImageCard;
})();
// public/assets/js/cart/dtfimage-cards.js
(function () {
    const MIN = 0.25, MAX = 60;
    const round3 = n => Math.round(n * 1e3) / 1e3;
    const toNum  = (v, d=0) => { const x = parseFloat(v); return Number.isFinite(x) ? x : d; };

    function computeRatio(w, h) {
        w = toNum(w); h = toNum(h);
        return h > 0 ? w / h : 1;
    }

    function initCard(card) {
        if (!card || card.dataset.proportionInit === '1') return;

        const wInp  = card.querySelector('.input-width');
        const hInp  = card.querySelector('.input-height');
        const lock  = card.querySelector('.input-lock');
        if (!wInp || !hInp || !lock) return;

        let ratio = parseFloat(card.dataset.ratio);
        if (!Number.isFinite(ratio) || ratio <= 0) ratio = computeRatio(wInp.value, hInp.value) || 1;

        let updating = false;
        const clamp = n => Math.min(MAX, Math.max(MIN, round3(n)));
        const fmt   = n => String(clamp(n)).replace(/\.?0+$/,'');

        function syncFromWidth() {
            if (!lock.checked || updating) return;
            const W = toNum(wInp.value, MIN);
            updating = true;
            hInp.value = fmt(W / (ratio || 1));
            updating = false;
        }
        function syncFromHeight() {
            if (!lock.checked || updating) return;
            const H = toNum(hInp.value, MIN);
            updating = true;
            wInp.value = fmt(H * (ratio || 1));
            updating = false;
        }
        function freezeCurrentRatio() {
            const W = toNum(wInp.value, MIN), H = toNum(hInp.value, MIN);
            if (H > 0) ratio = W / H;
            card.dataset.ratio = String(ratio);
        }

        // Events
        wInp.addEventListener('input',  syncFromWidth);
        hInp.addEventListener('input',  syncFromHeight);
        lock.addEventListener('change', () => {
            if (lock.checked) { freezeCurrentRatio(); syncFromWidth(); }
        });

        // Initial normalize if locked
        if (lock.checked) syncFromWidth();

        card.dataset.proportionInit = '1';
    }

    function initAll() {
        document.querySelectorAll('.image-card').forEach(initCard);
    }

    // Init now / on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }

    // Initialize cards added dynamically (e.g., after upload/duplicate)
    const mo = new MutationObserver(muts => {
        muts.forEach(m => {
            m.addedNodes && m.addedNodes.forEach(n => {
                if (!(n instanceof HTMLElement)) return;
                if (n.classList?.contains('image-card')) initCard(n);
                n.querySelectorAll?.('.image-card').forEach(initCard);
            });
        });
    });
    mo.observe(document.body, { childList: true, subtree: true });

    // Optional manual hook if you render a single card via AJAX
    window.DTF = window.DTF || {};
    window.DTF.initProportionLock = initCard;
})();
