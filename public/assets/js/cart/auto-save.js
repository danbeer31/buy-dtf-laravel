// public/assets/js/cart/auto-save.js
(function () {
    const money = v => '$' + Number(v || 0).toFixed(2);

    async function post(url, params){
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Accept':'application/json','X-Requested-With':'XMLHttpRequest' },
            body: new URLSearchParams(params || {})
        });
        if (!res.ok) throw new Error('HTTP '+res.status);
        return res.json();
    }

    function norm(el){
        if (!el) return '';
        if (el.type === 'number' || el.classList.contains('input-width') || el.classList.contains('input-height')) {
            const n = parseFloat(el.value);
            return Number.isFinite(n) ? n.toFixed(3) : '';
        }
        return String(el.value).trim();
    }

    function collect(card){
        const w  = card.querySelector('.input-width');
        const h  = card.querySelector('.input-height');
        const q  = card.querySelector('input[name="quantity"]');
        const nm = card.querySelector('input[name="image_name"]');
        const nt = card.querySelector('textarea[name="image_notes"]');
        const lk = card.querySelector('.input-lock');
        return {
            quantity:   q  ? q.value  : '',
            image_name: nm ? nm.value : '',
            image_notes:nt ? nt.value : '',
            width:      w  ? w.value  : '',
            height:     h  ? h.value  : '',
            lock:       lk && lk.checked ? '1' : '0'
        };
    }

    function ensureIndicator(card){
        let el = card.querySelector('.saving-indicator');
        if (!el){
            el = document.createElement('div');
            el.className = 'saving-indicator';
            el.innerHTML =
                '<div class="si-box"><div class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></div><span>Saving…</span></div>';
            card.appendChild(el);
        }
        return el;
    }
    function showSaving(card){ ensureIndicator(card); card.classList.add('saving'); }
    function doneSaving(card, ok=true, r=null){
        const el = ensureIndicator(card);
        el.innerHTML = ok
            ? '<div class="si-box"><span>Saved</span></div>'
            : '<div class="si-box"><span class="text-danger">Save failed</span></div>';
        setTimeout(()=>{ card.classList.remove('saving'); el.remove(); }, ok ? 500 : 1200);

        if (!ok || !r) return;

        // normalize fields to server values
        const q  = card.querySelector('input[name="quantity"]');
        const w  = card.querySelector('.input-width');
        const h  = card.querySelector('.input-height');
        const nm = card.querySelector('input[name="image_name"]');
        const nt = card.querySelector('textarea[name="image_notes"]');
        if (typeof r.quantity === 'number' && q) q.value = r.quantity;
        if (typeof r.width    === 'number' && w) w.value = (Math.round(r.width*100)/100).toString();
        if (typeof r.height   === 'number' && h) h.value = (Math.round(r.height*100)/100).toString();
        if (typeof r.image_name  === 'string' && nm) nm.value = r.image_name;
        if (typeof r.image_notes === 'string' && nt) nt.value = r.image_notes;

        // prices: use price from payload; compute total if extended absent
        const pe = card.querySelector('[data-price-each]');
        const tt = card.querySelector('[data-price-total],[data-total]');
        const qty = (typeof r.quantity === 'number' ? r.quantity : (q ? parseInt(q.value,10)||1 : 1));
        if (pe && r.price != null) pe.textContent = money(r.price);
        const total = (r.extended != null) ? r.extended : (r.price != null ? r.price * qty : null);
        if (tt && total != null) tt.textContent = money(total);
    }

    async function autosave(card){
        const id = parseInt(card.dataset.id || '0', 10);
        if (!id) return;
        showSaving(card);
        try {
            const r = await post(`/cart/image_update/${id}`, collect(card));
            doneSaving(card, !!(r && r.success === true), r || null);
            if (window.refreshCartIndicator) window.refreshCartIndicator();
        } catch (e) {
            console.error('autosave', e);
            doneSaving(card, false, null);
        }
    }

    // Record starting value on focusin
    document.addEventListener('focusin', (e) => {
        const t = e.target;
        if (!(t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement)) return;
        if (!t.closest('.image-card')) return;
        t.dataset.prev = norm(t);
    }, true);

    // Only save if changed on blur
    document.addEventListener('focusout', (e) => {
        const t = e.target;
        if (!(t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement)) return;
        const card = t.closest('.image-card');
        if (!card) return;

        const prev = t.dataset.prev ?? '';
        const curr = norm(t);
        if (curr === prev) return;

        clearTimeout(card._saveTimer);
        card._saveTimer = setTimeout(() => autosave(card), 50);
    }, true);

    // Save on lock checkbox toggle
    document.addEventListener('change', (e) => {
        const t = e.target;
        if (!(t instanceof HTMLInputElement) || !t.classList.contains('input-lock')) return;
        const card = t.closest('.image-card');
        if (!card) return;
        autosave(card);
    }, true);
})();
