// public/assets/js/uploader/editor.js
(function () {
    /* ======================================================
       Small helpers (cookie, CSRF, JSON-post with resilience)
       ====================================================== */
    function readCookie(name) {
        if (!name || !document.cookie) return '';
        const parts = document.cookie.split('; ');
        for (const p of parts) {
            const i = p.indexOf('=');
            const k = i >= 0 ? p.slice(0, i) : p;
            if (k === name) return decodeURIComponent(i >= 0 ? p.slice(i + 1) : '');
        }
        return '';
    }
    function getCsrf() {
        // First try the meta tag which is standard in Laravel
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) return { token: meta.content };

        const cfg = (window.CART_CFG || window.UP_CFG || {});
        const cookieName = cfg.csrf_cookie_name || '_token';
        const token = readCookie('XSRF-TOKEN') || readCookie(cookieName) || cfg.csrf_token || '';
        return { cookieName, token };
    }

    async function postFormJSON(form) {
        const fd = new FormData(form);

        // Inject CSRF (common aliases too)
        const { token } = getCsrf();
        if (token) {
            if (!fd.has('_token'))          fd.append('_token', token);
            if (!fd.has('fuel_csrf_token')) fd.append('fuel_csrf_token', token);
            if (!fd.has('fuelcsrf'))        fd.append('fuelcsrf', token);
        }

        const res = await fetch(form.action, {
            method: 'POST',
            body: fd,
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-TOKEN': token
            },
            credentials: 'same-origin'
        });

        // Try to parse JSON if provided
        let j = null;
        const ct = (res.headers.get('content-type') || '').toLowerCase();
        if (ct.includes('application/json')) {
            try { j = await res.json(); } catch (_) {}
        }

        if (!res.ok) {
            const msg = (j && (j.message || j.error)) || `HTTP ${res.status}`;
            throw new Error(msg);
        }
        if (j && j.success === false) {
            throw new Error(j.message || 'Request failed');
        }
        return j || { success: true };
    }

    // Optional nicer confirm (falls back to native)
    async function askConfirm(message) {
        if (window.bootstrap) {
            let modal = document.getElementById('genericConfirmModal');
            if (!modal) {
                modal = document.createElement('div');
                modal.id = 'genericConfirmModal';
                modal.className = 'modal fade';
                modal.innerHTML = `
<div class="modal-dialog modal-dialog-centered">
  <div class="modal-content">
    <div class="modal-header"><h5 class="modal-title">Please confirm</h5>
      <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
    </div>
    <div class="modal-body"><p class="mb-0"></p></div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
      <button type="button" class="btn btn-primary" id="genericConfirmOkBtn">OK</button>
    </div>
  </div>
</div>`;
                document.body.appendChild(modal);
            }
            modal.querySelector('.modal-body p').textContent = String(message || '');
            return new Promise(resolve => {
                const m = new bootstrap.Modal(modal, { backdrop: 'static' });
                const okBtn = modal.querySelector('#genericConfirmOkBtn');
                const onOk = () => { cleanup(); m.hide(); resolve(true); };
                const onHide = () => { cleanup(); resolve(false); };
                const cleanup = () => {
                    okBtn.removeEventListener('click', onOk);
                    modal.removeEventListener('hidden.bs.modal', onHide);
                };
                okBtn.addEventListener('click', onOk);
                modal.addEventListener('hidden.bs.modal', onHide);
                m.show();
            });
        }
        return Promise.resolve(window.confirm(message));
    }

    /* =========================
       Card binder (ratio lock)
       ========================= */
    function bindCard(card) {
        if (!card) return;
        const ratio = parseFloat(card.getAttribute('data-ratio')) || 1;

        const formU = card.querySelector('.form-update');
        const w     = formU ? formU.querySelector('.input-width')  : null;
        const h     = formU ? formU.querySelector('.input-height') : null;
        const lock  = formU ? formU.querySelector('.input-lock')   : null;

        if (w && h && lock) {
            if (!w.__ratioBound) {
                w.addEventListener('input', () => {
                    const val = parseFloat(w.value);
                    if (lock.checked && val > 0) h.value = (val / ratio).toFixed(2);
                });
                w.__ratioBound = true;
            }
            if (!h.__ratioBound) {
                h.addEventListener('input', () => {
                    const val = parseFloat(h.value);
                    if (lock.checked && val > 0) w.value = (val * ratio).toFixed(2);
                });
                h.__ratioBound = true;
            }
        }
    }

    // Bind existing cards on load
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.image-card').forEach(bindCard);
    });

    // Bind future cards inserted by Cart.addDtfImageCard()
    window.addEventListener('dtfimage:card-added', (ev) => {
        const el = ev && ev.detail && ev.detail.el;
        if (el) bindCard(el);
    });

    /* =========================
       SAVE (delegated, robust)
       ========================= */
    if (!window.__CART_SAVE_DELEGATE_BOUND__) {
        window.__CART_SAVE_DELEGATE_BOUND__ = true;

        document.addEventListener('submit', async (e) => {
            const form = e.target.closest('.form-update');
            if (!form) return;
            e.preventDefault();

            const btn = form.querySelector('.btn-save, button[type="submit"]');
            const w   = form.querySelector('input[name="width"]');
            const h   = form.querySelector('input[name="height"]');
            const prevText = btn ? btn.textContent : '';

            if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

            try {
                const j = await postFormJSON(form);

                if (typeof j.width  !== 'undefined' && w) w.value = Number(j.width).toFixed(2);
                if (typeof j.height !== 'undefined' && h) h.value = Number(j.height).toFixed(2);
                // if (j.price_each || j.total) { /* update price UI here if returned */ }
                if (window.refreshCartIndicator) {
                    window.refreshCartIndicator();
                } else {
                    const badge = document.getElementById('cart-badge');
                    if (badge) {
                        // For saving an existing image, count shouldn't change, but let's refresh anyway
                        // If it's not defined, we can't do much without a fetch
                    }
                }
                if (btn) { btn.textContent = 'Saved ✓'; }
                setTimeout(() => { if (btn) { btn.textContent = prevText; btn.disabled = false; } }, 600);
            } catch (err) {
                if (btn) { btn.textContent = 'Error'; }
                setTimeout(() => { if (btn) { btn.textContent = prevText; btn.disabled = false; } }, 1200);
                alert(err && err.message ? err.message : 'Save failed');
            }
        }, true); // capture to intercept native submits first
    }

    /* =========================
       DELETE (delegated; hardened)
       ========================= */
    if (!window.__CART_DELETE_DELEGATE_BOUND__) {
        window.__CART_DELETE_DELEGATE_BOUND__ = true;

        document.addEventListener('submit', async (e) => {
            const form = e.target.closest('.form-delete');
            if (!form) return;
            e.preventDefault();

            const ok = await askConfirm('Remove this image from your order?');
            if (!ok) return;

            const btn = form.querySelector('button[type="submit"], .btn');
            const prev = btn ? btn.textContent : '';
            if (btn) { btn.disabled = true; btn.textContent = 'Removing…'; }

            try {
                await postFormJSON(form);

                // Remove the whole grid column so layout reflows nicely
                const cardEl = form.closest('.image-card') || form.closest('[data-id]');
                const colEl  = cardEl
                    ? cardEl.closest('.dtf-card-col, .col-12, .col-sm-6, .col-md-6, .col-lg-4')
                    : null;

                if (colEl && colEl.parentNode) {
                    colEl.parentNode.removeChild(colEl);
                } else if (cardEl && cardEl.parentNode) {
                    cardEl.parentNode.removeChild(cardEl);
                }

                // If no more cards remain, show the empty-state and disable "Place order"
                const list = document.getElementById('img-grid') ||
                    document.querySelector('#dtfimages-list, #img-grid');
                const hasCards = !!(list && list.querySelector('.image-card'));

                if (!hasCards) {
                    if (!document.getElementById('no-images-alert')) {
                        const alert = document.createElement('div');
                        alert.id = 'no-images-alert';
                        alert.className = 'alert alert-info';
                        alert.textContent = 'No images found on your open order.';
                        const uploadCard = document.getElementById('upload-card');
                        if (list && list.parentNode) {
                            list.parentNode.insertBefore(alert, list);
                        } else if (uploadCard && uploadCard.parentNode) {
                            uploadCard.parentNode.insertBefore(alert, uploadCard);
                        } else {
                            document.body.prepend(alert);
                        }
                    }
                    const place = document.querySelector('a.btn.btn-success');
                    if (place) {
                        place.classList.add('disabled');
                        place.setAttribute('aria-disabled', 'true');
                        place.setAttribute('tabindex', '-1');
                    }
                }
                if (window.refreshCartIndicator) {
                    window.refreshCartIndicator();
                } else {
                    const badge = document.getElementById('cart-badge');
                    if (badge) {
                        const current = parseInt(badge.textContent) || 0;
                        badge.textContent = Math.max(0, current - 1);
                        if (current <= 1) badge.classList.add('d-none');
                    }
                }
            } catch (err) {
                if (btn) { btn.textContent = prev; btn.disabled = false; }
                alert(err && err.message ? err.message : 'Delete failed');
            }
        }, true);
    }

    /* ==================================
       Duplicate (delegated, no-reload)
       ================================== */
    // Submits .form-duplicate → server returns { success, dtfimage_id, order_id }
    // Then we render the card with Cart.addDtfImageCard and highlight it.
    if (!window.__CART_DUPLICATE_DELEGATE_BOUND__) {
        window.__CART_DUPLICATE_DELEGATE_BOUND__ = true;

        function ensureDupHiStyle() {
            if (document.getElementById('dup-hi-style')) return;
            const s = document.createElement('style');
            s.id = 'dup-hi-style';
            s.textContent = `
.dup-hi { outline: 3px solid rgba(13,110,253,.85); outline-offset: 2px; transition: outline-color .6s ease; }
.dup-hi.fade { outline-color: transparent; }
`;
            document.head.appendChild(s);
        }

        async function addCardAndHighlight(dtfimageId, orderId) {
            if (!window.Cart || typeof window.Cart.addDtfImageCard !== 'function') {
                throw new Error('Cart.addDtfImageCard is not available on this page.');
            }
            const ok = await window.Cart.addDtfImageCard(dtfimageId, orderId);
            if (!ok) throw new Error('Failed to render duplicated card.');

            ensureDupHiStyle();
            const byData = `.image-card[data-id="${dtfimageId}"]`;
            const byId   = `#dtfimage-card-${dtfimageId}`;
            const card   = document.querySelector(byData) || document.querySelector(byId);
            if (card) {
                card.classList.add('dup-hi');
                card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                setTimeout(() => card.classList.add('fade'), 50);
                setTimeout(() => card.classList.remove('dup-hi', 'fade'), 700);
            }
        }

        document.addEventListener('submit', async (e) => {
            const form = e.target.closest('form.form-duplicate');
            if (!form) return;
            e.preventDefault();

            const ok = await askConfirm('Duplicate this image into your cart?');
            if (!ok) return;

            const btn = form.querySelector('button[type=submit]');
            const prev = btn ? btn.textContent : '';
            if (btn) { btn.disabled = true; btn.textContent = 'Duplicating…'; }

            try {
                const j = await postFormJSON(form);
                const newId   = j.dtfimage_id || j.image_id || j.id;
                const orderId = j.order_id    || j.order    || j.dtforder_id;

                if (!newId || !orderId) throw new Error('Duplicate succeeded but no IDs returned.');
                await addCardAndHighlight(newId, orderId);
                if (window.refreshCartIndicator) {
                    window.refreshCartIndicator();
                } else {
                    const badge = document.getElementById('cart-badge');
                    if (badge) {
                        const current = parseInt(badge.textContent) || 0;
                        badge.textContent = current + 1;
                        badge.classList.remove('d-none');
                    }
                }
                if (btn) { btn.textContent = 'Duplicated ✓'; setTimeout(() => { btn.textContent = prev; btn.disabled = false; }, 800); }
            } catch (err) {
                if (btn) { btn.textContent = prev; btn.disabled = false; }
                alert(err && err.message ? err.message : 'Duplicate failed');
            }

        }, true);
    }

    /* ==================================
       "Add to My Images" button (jQuery)
       ================================== */
    $(document).on('click', '.save_image', function (e) {
        e.preventDefault();

        var $btn = $(this);
        var image_id = $btn.data('id');
        if (!image_id) return;

        if (!confirm('Add this image to your saved images?')) return;

        var prev = $btn.text();
        $btn.prop('disabled', true).text('Saving…');

        $.ajax({
            url: '/cart/save/' + image_id,
            type: 'POST',
            dataType: 'json',
            headers: { 'X-CSRF-TOKEN': getCsrf().token },
            data: { dtfimage_id: image_id, _token: getCsrf().token }
        })
            .done(function (res) {
                if (!res || res.success === false) {
                    alert(res && res.message ? res.message : 'Failed to save the image.');
                    $btn.prop('disabled', false).text(prev);
                    return;
                }
                $btn.css('display', 'none');
            })
            .fail(function () {
                alert('Failed to save the image. Please try again.');
                $btn.prop('disabled', false).text(prev);
            });
    });

})();
