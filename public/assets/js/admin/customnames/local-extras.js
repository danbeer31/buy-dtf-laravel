// /public/assets/js/admin/template-local-extras.js
(function () {
    const cfg = (window.TPL_LOCAL && window.TPL_LOCAL.urls) || {};

    // --- CSRF helpers ---
    function readCookie(name) {
        if (!name || !document.cookie) return '';
        const m = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.*+?^${}()|[\]\\])/g,'\\$1') + '=([^;]*)'));
        return m ? decodeURIComponent(m[1]) : '';
    }
    function getCsrf() {
        const cookieName = 'fuel_csrf_token';
        const token = readCookie(cookieName) || (window.CART_CFG && window.CART_CFG.csrf_token) || '';
        return { name: cookieName, token };
    }
    async function postForm(url, data) {
        const fd = new FormData();
        Object.keys(data || {}).forEach(k => fd.append(k, data[k]));
        const { name, token } = getCsrf();
        if (name && token) {
            fd.append(name, token);
            if (name !== 'fuelcsrf') fd.append('fuelcsrf', token);
        }
        const res = await fetch(url, {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        });
        let j = null; try { j = await res.json(); } catch {}
        if (!res.ok || !j || j.success === false) {
            throw new Error((j && (j.message || j.error)) || ('HTTP ' + res.status));
        }
        return j;
    }

    function setBadge(el, text, klass) {
        if (!el) return;
        el.textContent = text;
        el.className = 'badge ' + (klass || 'bg-secondary');
    }

    // --- Save Meta ---
    const metaBtn   = document.getElementById('meta-save');
    const metaForm  = document.getElementById('tpl-meta-form');
    const metaBadge = document.getElementById('meta-status');

    if (metaBtn && metaForm) {
        metaBtn.addEventListener('click', async () => {
            try {
                const id    = (window.TPL_LOCAL && window.TPL_LOCAL.id) || null;
                const name  = document.getElementById('tpl-public-name')?.value || '';
                const desc  = document.getElementById('tpl-description')?.value || '';
                if (!cfg.save_meta) throw new Error('Save meta URL missing');

                metaBtn.disabled = true;
                setBadge(metaBadge, 'Saving…', 'bg-warning text-dark');

                const payload = { id: id, public_name: name, description: desc };
                const j = await postForm(cfg.save_meta, payload);

                setBadge(metaBadge, 'Saved', 'bg-success');
                // If server returns updated thumb URL, refresh small thumb
                if (j.preview_url) {
                    const thumb = document.getElementById('tpl-preview-thumb');
                    if (thumb) thumb.src = j.preview_url + (j.preview_url.includes('?') ? '&' : '?') + 't=' + Date.now();
                }
            } catch (e) {
                setBadge(metaBadge, e.message || 'Error', 'bg-danger');
                alert(e.message || 'Failed to save meta');
            } finally {
                metaBtn.disabled = false;
                setTimeout(() => setBadge(metaBadge, 'Idle', 'bg-secondary'), 1200);
            }
        });
    }

    // --- Save current Preview image as template preview ---
    const savePrevBtn = document.getElementById('save-template-preview');
    if (savePrevBtn) {
        savePrevBtn.addEventListener('click', async () => {
            try {
                const id = (window.TPL_LOCAL && window.TPL_LOCAL.id) || null;
                if (!cfg.save_preview) throw new Error('Save preview URL missing');
                if (!id) throw new Error('Template ID missing');

                savePrevBtn.disabled = true;
                savePrevBtn.textContent = 'Saving…';

                const box = document.getElementById('preview-container');
                if (!box) throw new Error('Preview container not found');

                // Prefer <canvas>, else <img>
                let dataUrl = '';
                const cvs = box.querySelector('canvas');
                const img = box.querySelector('img');

                if (cvs && cvs.toDataURL) {
                    dataUrl = cvs.toDataURL('image/png');
                } else if (img && img.src) {
                    // If already a data URL, use it; else send URL for server to fetch
                    if (img.src.startsWith('data:')) {
                        dataUrl = img.src;
                    } else {
                        // send image_url (server will fetch and store)
                        const j = await postForm(cfg.save_preview, { id: id, image_url: img.src });
                        savePrevBtn.textContent = 'Saved ✓';
                        // Update both big preview and small thumb if server returns URL
                        if (j.preview_url) {
                            if (img) img.src = j.preview_url + (j.preview_url.includes('?') ? '&' : '?') + 't=' + Date.now();
                            const thumb = document.getElementById('tpl-preview-thumb');
                            if (thumb) thumb.src = img.src;
                        }
                        setTimeout(() => (savePrevBtn.textContent = 'Save as Template Preview', savePrevBtn.disabled = false), 900);
                        return;
                    }
                } else {
                    throw new Error('No preview image to save');
                }

                // Post base64 if we have it
                const j = await postForm(cfg.save_preview, { id: id, image_base64: dataUrl });
                savePrevBtn.textContent = 'Saved ✓';

                // If server returns the stored URL, update displays
                if (j.preview_url) {
                    if (img && !img.src.startsWith('data:')) {
                        img.src = j.preview_url + (j.preview_url.includes('?') ? '&' : '?') + 't=' + Date.now();
                    }
                    const thumb = document.getElementById('tpl-preview-thumb');
                    if (thumb) thumb.src = j.preview_url + (j.preview_url.includes('?') ? '&' : '?') + 't=' + Date.now();
                }
            } catch (e) {
                alert(e.message || 'Failed to save preview');
            } finally {
                setTimeout(() => {
                    savePrevBtn.textContent = 'Save as Template Preview';
                    savePrevBtn.disabled = false;
                }, 900);
            }
        });
    }
})();
