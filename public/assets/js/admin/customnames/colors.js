// ---------- PALETTE + offcanvas color picker (TeamCustomization-style) ----------
const URLS = (window.TPL_LOCAL && window.TPL_LOCAL.urls) || {};
let _paletteLoaded = false;
let _PALETTE = []; // [{id, name, hex}]

async function fetchPaletteOnce() {
    if (_paletteLoaded) return;
    const url = (URLS && URLS.colors) || '/teamcustomization/colors';
    try {
        const res = await fetch(url, { headers: { 'Accept': 'application/json' }});
        const j = await res.json();
        const list = (j && j.colors) || [];
        _PALETTE = list.map(p => {
            const hex = String(p.hex || '').toUpperCase();
            return { id: Number(p.id), name: String(p.name || ''), hex: hex.startsWith('#') ? hex : ('#' + hex) };
        });
    } catch(e) {
        // fallback palette so UI remains usable
        _PALETTE = [
            {id:0, name:'Black',  hex:'#000000'},
            {id:1, name:'White',  hex:'#FFFFFF'},
            {id:2, name:'Red',    hex:'#FF0000'},
            {id:3, name:'Blue',   hex:'#0000FF'},
            {id:4, name:'Gold',   hex:'#FFD700'}
        ];
    } finally {
        _paletteLoaded = true;
    }
}
function ensureColorOffcanvasStyles() {
    if (document.getElementById('nl-cc-offcanvas-styles')) return;
    const css = `
  .nl-cc-grid{
    display:grid;
    grid-template-columns:repeat(auto-fill,minmax(190px,1fr));
    gap:12px;
  }
  .nl-cc-chip{
    display:flex; align-items:center; gap:12px;
    width:100%;
    padding:10px 14px;
    border:1px solid #e5e7eb; /* gray-200 */
    border-radius:12px;
    background:#fff;
    box-shadow:0 1px 1px rgba(0,0,0,.03);
    transition:box-shadow .15s ease, transform .05s ease;
  }
  .nl-cc-chip:hover{ box-shadow:0 4px 14px rgba(0,0,0,.07); transform:translateY(-1px); }
  .nl-cc-chip:focus{ outline:2px solid #93c5fd; outline-offset:2px; } /* blue-300 */
  .nl-cc-bar{
    flex:0 0 72px; height:20px;
    border-radius:8px;
    border:1px solid #d1d5db; /* gray-300 */
    background:#fff;
  }
  .nl-cc-label{
    font-size:14px; line-height:1.1;
    color:#111827;  /* gray-900 */
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  }
  /* Optional: compact on very small widths */
  @media (max-width:420px){
    .nl-cc-grid{ grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); }
  }
  `;
    const style = document.createElement('style');
    style.id = 'nl-cc-offcanvas-styles';
    style.textContent = css;
    document.head.appendChild(style);
}
function normHex(h) {
    if (!h) return '';
    let v = String(h).trim().toUpperCase();
    if (!v.startsWith('#')) v = '#'+v;
    return /^#[0-9A-F]{6}$/.test(v) ? v : '';
}

function renderPaletteGrid(mountEl, initialHex, onPick) {
    if (!mountEl) return;
    ensureColorOffcanvasStyles();
    mountEl.innerHTML = '';

    // Grid container
    const grid = document.createElement('div');
    grid.className = 'nl-cc-grid';
    mountEl.appendChild(grid);

    // Build a chip button for each color
    _PALETTE.forEach(c => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'nl-cc-chip';
        btn.setAttribute('aria-label', `${c.name} ${c.hex}`);
        btn.title = `${c.name} (${c.hex})`;

        const bar = document.createElement('div');
        bar.className = 'nl-cc-bar';
        bar.style.background = c.hex;

        const label = document.createElement('div');
        label.className = 'nl-cc-label';
        label.textContent = c.name;

        btn.appendChild(bar);
        btn.appendChild(label);

        btn.addEventListener('click', () => onPick(c.hex));
        grid.appendChild(btn);
    });

    // (Optional) If you want to pre-highlight the current value, add a faint ring:
    if (initialHex) {
        const ih = String(initialHex).toUpperCase();
        const match = Array.from(grid.children).find(b => {
            const hex = (b.title.match(/(#?[0-9A-F]{6})/i) || [])[1] || '';
            return hex.replace('#','') === ih.replace('#','');
        });
        if (match) match.style.boxShadow = '0 0 0 2px #60a5fa'; // blue-400 ring
    }
}

function openColorOffcanvas(initialHex, onPick) {
    const mount = document.getElementById('nl-cc-offcanvas-container');
    if (!mount) return;
    renderPaletteGrid(mount, initialHex, (hex) => {
        onPick(hex);
        try {
            const ocEl = document.getElementById('offcanvas-colors');
            if (window.bootstrap && bootstrap.Offcanvas) {
                bootstrap.Offcanvas.getOrCreateInstance(ocEl).hide();
            }
        } catch {}
    });
    const ocEl = document.getElementById('offcanvas-colors');
    if (window.bootstrap && bootstrap.Offcanvas) {
        bootstrap.Offcanvas.getOrCreateInstance(ocEl).show();
    }
}

function makeColorButton(inputEl, label='Pick color') {
    if (!inputEl || inputEl._nlDecorated) return null;
    inputEl._nlDecorated = true;

    const wrap = document.createElement('div');
    wrap.className = 'input-group nl-cc-cell';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-outline-secondary';
    btn.innerHTML = `<span class="nl-cc-swatch"></span><span class="nl-cc-label">${label}</span>`;

    // sync swatch with input value
    const sync = () => {
        const v = normHex(inputEl.value);
        const sw = btn.querySelector('.nl-cc-swatch');
        if (sw) sw.style.background = v || 'transparent';
    };
    inputEl.addEventListener('input', sync);
    sync();

    btn.addEventListener('click', async () => {
        await fetchPaletteOnce();
        openColorOffcanvas(normHex(inputEl.value) || '#000000', (hex) => {
            inputEl.value = hex;
            inputEl.dispatchEvent(new Event('input', {bubbles:true}));
            inputEl.dispatchEvent(new Event('change', {bubbles:true}));
            sync();
        });
    });

    // assemble
    inputEl.parentNode.insertBefore(wrap, inputEl);
    wrap.appendChild(inputEl);
    wrap.appendChild(btn);
    return {wrap, btn, sync};
}

// Ring exclusivity (disables outline fields if ring has a color)
function wireRingExclusivity(ringInput, outlineInput, outline2Input) {
    if (!ringInput) return;
    const apply = () => {
        const hasRing = !!normHex(ringInput.value);
        [outlineInput, outline2Input].forEach(el => {
            if (!el) return;
            const grp = el.closest('.nl-cc-cell') || el.parentElement;
            if (grp) grp.classList.toggle('nl-cc-disabled', hasRing);
            el.disabled = !!hasRing;
        });
    };
    ringInput.addEventListener('input', apply);
    ringInput.addEventListener('change', apply);
    apply();
}