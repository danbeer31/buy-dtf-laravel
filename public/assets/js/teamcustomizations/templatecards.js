(function () {
    const grid = document.getElementById('tc-templates-grid');
    const sel = document.getElementById('tc-template');
    if (!grid || !sel) return;

    // Only dispatch a change when the template actually changes
    let lastSelectedId = null;

    // Optional: list of action buttons the legacy code enables/binds
    const ACTION_BUTTON_IDS = [
        'tc-add-row-inline',
        'tc-import-csv',
        'tc-delete-all',
        'tc-preview',
        'tc-run'
    ];

    function enableActionButtons() {
        ACTION_BUTTON_IDS.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.disabled = false;
        });
    }

    async function setSelectedCard(id) {
        const idStr = String(id || '');

        // Visual card selection
        grid.querySelectorAll('.tc-tpl-card').forEach(c => {
            c.classList.toggle('selected', String(c.dataset.id) === idStr);
        });

        // No-op if same selection (prevents double-binding)
        if (lastSelectedId === idStr) return;
        lastSelectedId = idStr;

        // Reflect into the select for legacy code
        sel.value = idStr;

        // Failsafe: enable buttons immediately (legacy will also enable/bind)
        enableActionButtons();

        // Fetch the template (harden the payload for any downstream readers)
        let tpl = {};
        try {
            const res = await fetch(`${window.__TCFG.urls.template}?id=${encodeURIComponent(idStr)}`, {
                headers: {'Accept': 'application/json'},
                credentials: 'same-origin'
            });
            const j = await res.json().catch(() => ({}));
            tpl = (j && (j.template || j)) || {};
        } catch (_) {
            tpl = {};
        }

        // Never leak null/undefined to legacy code that does Object.keys(...)
        if (!Array.isArray(tpl.blocks)) tpl.blocks = [];
        if (!tpl.colors || typeof tpl.colors !== 'object') tpl.colors = {};
        if (!tpl.scaling || typeof tpl.scaling !== 'object') tpl.scaling = {};
        if (!tpl.meta || typeof tpl.meta !== 'object') tpl.meta = {};

        window.__TC_SELECTED_TEMPLATE = tpl;

        // Let the legacy on-change handler run once per actual selection
        try {
            sel.dispatchEvent(new Event('change', {bubbles: true}));
        } catch (e) {
            console.warn('Template change handler threw:', e);
        }
    }

    grid.addEventListener('click', (e) => {
        const card = e.target.closest('.tc-tpl-card');
        if (!card) return;
        setSelectedCard(card.dataset.id);
    });

    grid.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const card = e.target.closest('.tc-tpl-card');
        if (!card) return;
        e.preventDefault();
        setSelectedCard(card.dataset.id);
    });

    // Initialize selection once (if something is preselected)
    window.addEventListener('load', () => {
        if (sel.value) setSelectedCard(sel.value);
    });
})();
