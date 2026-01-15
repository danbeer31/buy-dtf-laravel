// templatebuilder.js — full editor with outlines, ring, dyPx, AutoFix + manual scale + unified Data UI
(function () {
    "use strict";

    // ---------- helpers ----------
    const $  = (s, r=document) => r.querySelector(s);
    const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
    const on = (el, ev, fn, opts) => el && el.addEventListener(ev, fn, opts);
    const esc = (s) => String(s ?? "");
    const asInt = (v, d=0) => { const n = Number(v); return Number.isFinite(n) ? parseInt(n, 10) : d; };
    const asNum = (v, d=0) => { const n = Number(v); return Number.isFinite(n) ? n : d; };
    const asHex = (v, f="") => { const s = String(v || "").trim(); return /^#?[0-9a-fA-F]{6}$/.test(s) ? ("#" + s.replace("#","")) : f; };
    const shallowClone = (o) => JSON.parse(JSON.stringify(o || {}));
    const normType = (t) => (String(t || "text").toLowerCase() === "straight" ? "text" : String(t || "text").toLowerCase());

    function showAlert(type, msg) {
        const box = $("#tb-alert");
        if (!box) return;
        box.className = `alert alert-${type}`;
        box.textContent = msg;
        box.classList.remove("d-none");
        clearTimeout(showAlert._t);
        showAlert._t = setTimeout(() => box.classList.add("d-none"), 3000);
    }

    async function fetchJSON(url, opts = {}) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        const headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            ...(opts.headers || {})
        };
        if (csrfToken) {
            headers['X-CSRF-TOKEN'] = csrfToken;
        }
        const r = await fetch(url, {
            credentials: "same-origin",
            headers: headers,
            ...opts,
        });
        if (!r.ok) {
            let msg = `HTTP ${r.status}`;
            try {
                const err = await r.json();
                if (err && err.message) msg = err.message;
            } catch (_) {}
            throw new Error(`${msg} @ ${url}`);
        }
        const ct = r.headers.get("content-type") || "";
        return ct.includes("application/json") ? r.json() : r.text();
    }
    function compatAutoFixShim(b) {
        const bb = {...b};
        // Map new -> old (only when old is not already present)
        if (bb.autoFix !== undefined && bb.squeezeToFit === undefined) {
            bb.squeezeToFit = !!bb.autoFix;
        }
        if (bb.autoFixMode && bb.squeezeMode === undefined) {
            bb.squeezeMode = bb.autoFixMode;
        }
        if (typeof bb.autoFixWidthPx === "number" && bb.fitWidthPx === undefined) {
            bb.fitWidthPx = bb.autoFixWidthPx;
        }
        if (bb.autoFixBox && bb.fitBox === undefined) {
            bb.fitBox = {...bb.autoFixBox};
        }
        return bb;
    }
    // ---------- MIGRATION: old squeeze* -> new AutoFix + manualScale ----------
    function migrateBlockFields(b) {
        const t = String(b.type || "text").toLowerCase();

        // per-block manual scale defaults
        if (t !== "svg") {
            if (typeof b.manualScaleX !== "number") b.manualScaleX = 1;
            if (typeof b.manualScaleY !== "number") b.manualScaleY = 1;
        }

        // If new fields already present, just ensure shapes
        if (b.autoFix !== undefined || b.autoFixMode !== undefined || b.autoFixBox !== undefined || b.autoFixWidthPx !== undefined) {
            if (t !== "svg") {
                if (typeof b.autoFix !== "boolean") b.autoFix = false;
                b.autoFixMode = b.autoFixMode || "width";
                if (typeof b.autoFixWidthPx !== "number") b.autoFixWidthPx = 0;
                b.autoFixBox = b.autoFixBox && typeof b.autoFixBox === "object"
                    ? { leftPx:+(b.autoFixBox.leftPx||0), rightPx:+(b.autoFixBox.rightPx||0), topPx:+(b.autoFixBox.topPx||0), bottomPx:+(b.autoFixBox.bottomPx||0) }
                    : { leftPx:0, rightPx:0, topPx:0, bottomPx:0 };
            }
            return b;
        }

        // Map legacy squeeze* to new autoFix*
        if (b.squeezeToFit !== undefined || b.squeezeMode !== undefined || b.fitBox !== undefined || b.fitWidthPx !== undefined) {
            b.autoFix        = !!b.squeezeToFit;
            b.autoFixMode    = (b.squeezeMode || "width");
            b.autoFixBox     = b.fitBox ? {
                leftPx: +(b.fitBox.leftPx || 0),
                rightPx:+(b.fitBox.rightPx|| 0),
                topPx:  +(b.fitBox.topPx  || 0),
                bottomPx:+(b.fitBox.bottomPx||0)
            } : { leftPx:0, rightPx:0, topPx:0, bottomPx:0 };
            b.autoFixWidthPx = (typeof b.fitWidthPx === "number" ? b.fitWidthPx : 0);
        } else {
            // Default off
            b.autoFix = false;
            b.autoFixMode = "width";
            b.autoFixBox = { leftPx:0, rightPx:0, topPx:0, bottomPx:0 };
            b.autoFixWidthPx = 0;
        }

        return b;
    }

    // ---------- STATE ----------
    const STATE = {
        fonts: [],
        tpl: null,
        blocks: [],
        data: {}, // unified data map used for preview
    };

    // ---------- URLs ----------
    const urls = (window.__TB_URLS && typeof window.__TB_URLS === "object") ? window.__TB_URLS : {
        get: "/admin/customnames/template/get",
        save: "/admin/customnames/template/save",
        create: "/admin/customnames/template/create",
        del: "/admin/customnames/template/delete",
        reload: "/admin/customnames/templates/reload",
        fonts: "/admin/customnames/fonts/list",
        preview: "/admin/customnames/preview",
    };

    // ---------- DOM refs ----------
    const elSlug   = $("#tb-slug");
    const elLoad   = $("#tb-load");
    const elSave   = $("#tb-save");
    const elSaveAs = $("#tb-saveas");
    const elDelete = $("#tb-delete");
    const elJson   = $("#tb-json");

    const elWidthIn  = $("#f-widthIn");
    const elHeightIn = $("#f-heightIn");
    const elDpi      = $("#f-dpi");
    const elGap      = $("#f-gap");

    const elScaleName   = $("#f-scale-name");
    const elScaleNum    = $("#f-scale-number");
    const elScaleStroke = $("#f-scale-stroke");

    const elNameFont  = $("#f-name-font");
    const elNameFill  = $("#f-name-fill");
    const elNameStroke= $("#f-name-stroke");
    const elNameSW    = $("#f-name-strokeWidth");
    const elNameLS    = $("#f-name-letterSpacing");
    const elNameRingColor = $("#f-name-ring-color");
    const elNameRingWidth = $("#f-name-ring-width");
    const elNameRingGap   = $("#f-name-ring-gap");
    const elNameO2Color   = $("#f-name-o2-color");
    const elNameO2Width   = $("#f-name-o2-width");
    const elNameO2Font    = $("#f-name-o2-font");

    const elNumFont  = $("#f-number-font");
    const elNumFill  = $("#f-number-fill");
    const elNumStroke= $("#f-number-stroke");
    const elNumSW    = $("#f-number-strokeWidth");
    const elNumLS    = $("#f-number-letterSpacing");
    const elNumRingColor = $("#f-number-ring-color");
    const elNumRingWidth = $("#f-number-ring-width");
    const elNumRingGap   = $("#f-number-ring-gap");
    const elNumO2Color   = $("#f-number-o2-color");
    const elNumO2Width   = $("#f-number-o2-width");
    const elNumO2Font    = $("#f-number-o2-font");

    const elBlockRows = $("#f-block-rows");
    const elAddBlock  = $("#f-add-block");

    const elPvWrap    = $("#pv-wrap");
    const elPvSpinner = $("#pv-wrap .pv-spinner");
    const elPvPlaceholder = $("#pv-wrap .pv-placeholder");
    const elPvImg     = $("#pv-img");
    const elPvRun     = $("#pv-run");

    // ---------- fonts ----------
    async function loadFonts() {
        try {
            const data = await fetchJSON(urls.fonts, {method:"GET"});
            const list = (data && (data.fonts || data.items || data)) || [];
            STATE.fonts = list.map(x => ({slug: x.slug || x.family || "", family: x.family || x.slug || ""}));
        } catch {
            showAlert("warning","Could not load fonts; font dropdowns will be empty.");
            STATE.fonts = [];
        } finally {
            [elNameFont, elNumFont, elNameO2Font, elNumO2Font].forEach(fillFontSelect);
        }
    }
    function fillFontSelect(sel) {
        if (!sel) return;
        const before = sel.value;
        sel.innerHTML = `<option value="">(system)</option>`;
        for (const f of STATE.fonts) {
            const opt = document.createElement("option");
            opt.value = f.slug;
            opt.textContent = `${f.family} (${f.slug})`;
            sel.appendChild(opt);
        }
        if (before) sel.value = before;
    }
    const colorInput = (val, cls) => `<input type="text" class="form-control form-control-sm ${cls}" value="${esc(val||'')}" placeholder="#RRGGBB">`;
    function fontSelectHtml(current) {
        const opts = ['<option value="">(system)</option>'].concat(
            STATE.fonts.map(f => `<option value="${esc(f.slug)}"${(f.slug===current||f.family===current)?' selected':''}>${esc(f.family)} (${esc(f.slug)})</option>`)
        );
        return `<select class="form-select form-select-sm bi-font">${opts.join("")}</select>`;
    }

    // ---------- template defaults ----------
    function blankTemplate() {
        return {
            widthIn: 12, heightIn: 4, dpi: 300, gapAdjustPx: 0,
            scaling: {name: 1, number: 1, scaleStroke: true},
            defaults: {
                name:   { font: "", fill:"#000000", stroke:"#ffffff", strokeWidth:20, letterSpacing:-10,
                    separatedOutline:{outerColor:"#000000", outerWidthPx:0, gapPx:0}, outline2:{color:"#000000", widthPx:0, font:""} },
                number: { font: "", fill:"#000000", stroke:"#ffffff", strokeWidth:20, letterSpacing:0,
                    separatedOutline:{outerColor:"#000000", outerWidthPx:0, gapPx:0}, outline2:{color:"#000000", widthPx:0, font:""} },
            },
            blocks: [
                { slot:"NAME", type:"text", x:600, y:250, fontSizePx:240, letterSpacing:-8, align:"center", vAlign:"baseline", dyPx:0, value:"",
                    autoFix:false, autoFixMode:"width", autoFixWidthPx:0, autoFixBox:{leftPx:0,rightPx:0,topPx:0,bottomPx:0},
                    manualScaleX:1, manualScaleY:1 },
                { slot:"NUMBER", type:"text", x:600, y:650, fontSizePx:440, letterSpacing:0,  align:"center", vAlign:"baseline", dyPx:0, value:"",
                    autoFix:false, autoFixMode:"width", autoFixWidthPx:0, autoFixBox:{leftPx:0,rightPx:0,topPx:0,bottomPx:0},
                    manualScaleX:1, manualScaleY:1 },
            ],
        };
    }

    // ---------- Data UI ----------
    function dataCard() { return document.getElementById("tb-data-card"); }
    function dataRowsBody() { return dataCard()?.querySelector("#tb-data-rows"); }

    function ensureDataUI() {
        const cards = Array.from(document.querySelectorAll("#tb-data-card"));
        if (cards.length > 1) cards.slice(1).forEach(c => c.remove());
        let card = cards[0];

        if (!card) {
            const previewCard = elPvWrap && elPvWrap.closest(".card");
            const html = `
        <div class="card mb-3" id="tb-data-card">
          <div class="card-header d-flex align-items-center justify-content-between">
            <strong>Data</strong>
            <div>
              <button type="button" class="btn btn-sm btn-outline-secondary" id="tb-data-generate">Generate from template</button>
              <button type="button" class="btn btn-sm btn-outline-primary" id="tb-data-add">Add custom key</button>
            </div>
          </div>
          <div class="card-body">
            <p class="mb-2 help-hint">
              Values here become the <code>data</code> object sent to the renderer
              (<code>{&quot;NAME&quot;:&quot;…&quot;,&quot;NUMBER&quot;:&quot;…&quot;,&quot;CITY&quot;:&quot;…&quot;}</code>).
              Placeholders like <code>{{CITY}}</code> are auto-detected from label text.
            </p>
            <div class="table-responsive">
              <table class="table table-sm mb-0">
                <thead><tr><th style="width:40%">Key</th><th>Value</th><th style="width:40px"></th></tr></thead>
                <tbody id="tb-data-rows"></tbody>
              </table>
            </div>
          </div>
        </div>`;
            const wrap = document.createElement("div");
            wrap.innerHTML = html;
            card = wrap.firstElementChild;
            if (previewCard && previewCard.parentNode) previewCard.parentNode.insertBefore(card, previewCard);
            else ($("#tpl-builder") || document.body).appendChild(card);
        } else if (!dataRowsBody()) {
            card.querySelector(".card-body").insertAdjacentHTML("beforeend", `
        <div class="table-responsive">
          <table class="table table-sm mb-0">
            <thead><tr><th style="width:40%">Key</th><th>Value</th><th style="width:40px"></th></tr></thead>
            <tbody id="tb-data-rows"></tbody>
          </table>
        </div>`);
        }

        if (!ensureDataUI._wired) {
            ensureDataUI._wired = true;

            on(document, "click", (e) => {
                const btn = e.target.closest("#tb-data-add");
                if (!btn) return;
                addEmptyDataRow(); updateDataFromTable();
            });

            on(document, "click", (e) => {
                const btn = e.target.closest("#tb-data-generate");
                if (!btn) return;
                generateDataFromTemplate({preserveExisting:true});
            });

            on(document, "input", (e) => {
                if (!e.target.closest("#tb-data-rows")) return;
                updateDataFromTable();
            });

            on(document, "click", (e) => {
                const del = e.target.closest("#tb-data-rows .td-del");
                if (!del) return;
                const tr = del.closest("tr");
                tr && tr.remove();
                updateDataFromTable();
            });
        }
    }

    function renderDataRows() {
        ensureDataUI();
        const body = dataRowsBody();
        if (!body) return;

        const keys = Object.keys(STATE.data || {}).sort();
        if (!keys.length) {
            body.innerHTML = `<tr class="text-muted"><td colspan="3">No data yet — click “Generate from template” or “Add custom key”.</td></tr>`;
            return;
        }
        body.innerHTML = keys.map(k => `
      <tr>
        <td><input class="form-control form-control-sm td-key" value="${esc(k)}"></td>
        <td><input class="form-control form-control-sm td-val" value="${esc(STATE.data[k])}"></td>
        <td class="text-end"><button type="button" class="btn btn-sm btn-outline-danger td-del">✕</button></td>
      </tr>
    `).join("");
    }

    function addEmptyDataRow() {
        ensureDataUI();
        const body = dataRowsBody();
        if (!body) return;
        if (body.querySelector(".text-muted")) body.innerHTML = "";
        const tr = document.createElement("tr");
        tr.innerHTML = `
      <td><input class="form-control form-control-sm td-key" value=""></td>
      <td><input class="form-control form-control-sm td-val" value=""></td>
      <td class="text-end"><button type="button" class="btn btn-sm btn-outline-danger td-del">✕</button></td>
    `;
        body.appendChild(tr);
        tr.querySelector(".td-key").focus();
    }

    function updateDataFromTable() {
        const body = dataRowsBody();
        if (!body) return;
        const obj = {};
        $$("#tb-data-rows tr").forEach(tr => {
            const k = tr.querySelector(".td-key")?.value?.trim();
            if (!k) return;
            const v = tr.querySelector(".td-val")?.value ?? "";
            obj[k] = v;
        });
        STATE.data = obj;
    }

    function scanTemplateForData(tpl) {
        const found = new Set();
        (tpl.blocks || []).forEach(b => {
            const t = normType(b.type);
            if ((t === "text" || t === "arc") && b.slot) found.add(String(b.slot).trim());
            if (t === "label" && typeof b.text === "string") {
                const re = /\{\{([A-Z0-9_]+)\}\}/g;
                let m; while ((m = re.exec(b.text)) !== null) if (m[1]) found.add(m[1]);
            }
        });
        return Array.from(found);
    }

    function generateDataFromTemplate({preserveExisting=true}={}) {
        const tpl = getTemplateFromForm();
        const keys = scanTemplateForData(tpl);
        const merged = {...(preserveExisting ? STATE.data : {})};
        for (const k of keys) {
            if (preserveExisting && merged[k] !== undefined) continue;
            const seed = (tpl.blocks || []).find(b => normType(b.type)==="text" && b.slot===k && typeof b.value === "string" && b.value.length);
            merged[k] = seed ? seed.value : "";
        }
        STATE.data = merged;
        renderDataRows();
    }

    // ---------- Blocks table ----------
    function shortType(b) {
        const t = (b.type || "text").toLowerCase();
        return t === "straight" ? "text" : t;
    }
    function posSummary(b) {
        const t = shortType(b);
        if (t === "arc") return `cx:${b.cx ?? 0}, cy:${b.cy ?? 0}`;
        if (t === "svg") return `x:${b.x ?? 0}, y:${b.y ?? 0}`;
        return `x:${b.x ?? 0}, y:${b.y ?? 0}`;
    }
    function sizeSummary(b) {
        const t = shortType(b);
        if (t === "arc" || t === "text" || t === "label") return `fsz:${b.fontSizePx ?? 0}`;
        if (t === "svg") return `${b.widthPx ?? 0}×${b.heightPx ?? 0}`;
        return "";
    }
    function displayValue(b) {
        const t = shortType(b);
        if (t === "label") return b.text || "";
        if (t === "text")  return b.value || "";
        return "";
    }
    function miscSummary(b) {
        const t = (b.type || "text").toLowerCase();
        let parts = [];
        if (b.align) parts.push(`align:${b.align}`);

        // AutoFix summary
        const af = !!b.autoFix;
        const mode = b.autoFixMode || "width";
        if (t !== "svg" && af) {
            parts.push(`autoFix:${mode}`);
            if (typeof b.autoFixWidthPx === "number" && b.autoFixWidthPx > 0) {
                parts.push(`fitW:${b.autoFixWidthPx}`);
            }
            const bx = b.autoFixBox || {};
            const hasH = Number.isFinite(bx.leftPx) && Number.isFinite(bx.rightPx) && bx.rightPx > bx.leftPx;
            const hasV = Number.isFinite(bx.topPx) && Number.isFinite(bx.bottomPx) && bx.bottomPx > bx.topPx;
            if (hasH || hasV) {
                parts.push(`box:L${bx.leftPx||0},R${bx.rightPx||0}${(hasV?`,T${bx.topPx||0},B${bx.bottomPx||0}`:"")}`);
            }
        }

        // per-block manual scale
        if (t !== "svg" && (b.manualScaleX !== 1 || b.manualScaleY !== 1)) {
            const sx = (typeof b.manualScaleX === "number" ? b.manualScaleX : 1);
            const sy = (typeof b.manualScaleY === "number" ? b.manualScaleY : 1);
            parts.push(`scaleX:${sx}`);
            parts.push(`scaleY:${sy}`);
        }

        return parts.join(", ");
    }

    function rowHtmlForBlock(b, idx) {
        return `
      <tr data-idx="${idx}">
        <td class="align-middle"><input class="form-control form-control-sm bl-slot" value="${esc(b.slot || "")}"></td>
        <td class="align-middle">
          <select class="form-select form-select-sm bl-type">
            <option value="text" ${shortType(b)==="text"?"selected":""}>text</option>
            <option value="label" ${shortType(b)==="label"?"selected":""}>label</option>
            <option value="arc" ${shortType(b)==="arc"?"selected":""}>arc</option>
            <option value="svg" ${shortType(b)==="svg"?"selected":""}>svg</option>
          </select>
        </td>
        <td class="align-middle"><input class="form-control form-control-sm bl-value" value="${esc(displayValue(b))}" disabled></td>
        <td class="align-middle"><input class="form-control form-control-sm bl-pos" value="${esc(posSummary(b))}" disabled></td>
        <td class="align-middle"><input class="form-control form-control-sm bl-size" value="${esc(sizeSummary(b))}" disabled></td>
        <td class="align-middle"><input class="form-control form-control-sm bl-misc" value="${esc(miscSummary(b))}" disabled></td>
        <td class="align-middle text-end">
          <div class="d-flex justify-content-end gap-1">
            <button class="btn btn-sm btn-outline-secondary bl-edit" type="button">Edit</button>
            <button class="btn btn-sm btn-outline-danger bl-del" type="button">✕</button>
          </div>
        </td>
      </tr>`;
    }
    function renderBlocksTable() {
        const body = $("#f-block-rows");
        if (!body) return;
        body.innerHTML = (STATE.blocks || []).map((b, i) => rowHtmlForBlock(b, i)).join("");
    }

    function applyTableInlineEdits() {
        $$("#f-block-rows tr").forEach((tr) => {
            const i = +tr.dataset.idx;
            const b = STATE.blocks[i];
            if (!b) return;
            const newSlot = $(".bl-slot", tr)?.value ?? b.slot;
            const newType = $(".bl-type", tr)?.value ?? b.type;

            if (newSlot !== b.slot) b.slot = newSlot;

            if (newType !== b.type) {
                const t = (newType || "text").toLowerCase();
                if (t === "svg") {
                    STATE.blocks[i] = {
                        ...b,
                        type: "svg",
                        widthPx: b.widthPx ?? 200,
                        heightPx: b.heightPx ?? 200,
                        href: b.href ?? "",
                        // remove text-only fields
                        cx: undefined, cy: undefined, radiusPx: undefined, startAngleDeg: undefined, endAngleDeg: undefined,
                        fontSizePx: undefined, letterSpacing: undefined, text: undefined, value: undefined,
                        autoFix: undefined, autoFixMode: undefined, autoFixWidthPx: undefined, autoFixBox: undefined,
                        manualScaleX: undefined, manualScaleY: undefined
                    };
                } else if (t === "arc") {
                    STATE.blocks[i] = {
                        ...b, type:"arc",
                        cx: b.cx ?? (b.x ?? 0), cy: b.cy ?? (b.y ?? 0),
                        radiusPx: b.radiusPx ?? 100, startAngleDeg: b.startAngleDeg ?? 0, endAngleDeg: b.endAngleDeg ?? 180,
                        x: undefined, y: undefined, value: undefined, text: undefined,
                        // defaults for text-like properties
                        autoFix: false, autoFixMode: "width", autoFixWidthPx: 0, autoFixBox:{leftPx:0,rightPx:0,topPx:0,bottomPx:0},
                        manualScaleX: 1, manualScaleY: 1
                    };
                } else if (t === "label") {
                    STATE.blocks[i] = {
                        ...b, type:"label",
                        text: b.text ?? (b.value ?? ""), fontSizePx: b.fontSizePx ?? 120, value: undefined,
                        autoFix: false, autoFixMode: "width", autoFixWidthPx: 0, autoFixBox:{leftPx:0,rightPx:0,topPx:0,bottomPx:0},
                        manualScaleX: 1, manualScaleY: 1
                    };
                } else {
                    STATE.blocks[i] = {
                        ...b, type:"text", x: b.x ?? (b.cx ?? 0), y: b.y ?? (b.cy ?? 0), value: b.value ?? "",
                        autoFix: false, autoFixMode: "width", autoFixWidthPx: 0, autoFixBox:{leftPx:0,rightPx:0,topPx:0,bottomPx:0},
                        manualScaleX: 1, manualScaleY: 1
                    };
                }
            }
        });
    }

    // ---------- Inspector ----------
    function openInspector(idx) {
        const b0 = STATE.blocks[idx] || {};
        const t0 = normType(b0.type);

        const ring = b0.separatedOutline || {};
        const o2   = b0.outline2 || {};
        const afb  = b0.autoFixBox || {};

        const wrap = document.createElement("div");
        wrap.className = "tb-modal-wrap";
        wrap.innerHTML = `
      <div class="tb-modal-backdrop"></div>
      <div class="tb-modal">
        <div class="tb-modal-header">
          <strong>Edit Block ${idx + 1}: ${esc(b0.slot || "(no slot)")}</strong>
          <div class="tb-modal-actions">
            <button type="button" class="btn btn-sm btn-outline-secondary tb-close">Close</button>
            <button type="button" class="btn btn-sm btn-primary tb-save">Save</button>
          </div>
        </div>
        <div class="tb-modal-body">
          <div class="tb-grid">
            <div>
              <label class="form-label">Slot</label>
              <input type="text" class="form-control form-control-sm bi-slot" value="${esc(b0.slot || "")}">
            </div>
            <div>
              <label class="form-label">Type</label>
              <select class="form-select form-select-sm bi-type">
                <option value="text" ${t0==="text"?"selected":""}>text</option>
                <option value="label" ${t0==="label"?"selected":""}>label</option>
                <option value="arc" ${t0==="arc"?"selected":""}>arc</option>
                <option value="svg" ${t0==="svg"?"selected":""}>svg</option>
              </select>
            </div>
            <div>
              <label class="form-label">Rotation (deg)</label>
              <input type="number" class="form-control form-control-sm bi-rot" value="${esc(b0.rotationDeg || 0)}">
            </div>
          </div>

          <hr>

          <!-- Position -->
          <div class="tb-grid">
            <div ${t0!=="arc" ? "" : "style='display:none'"} >
              <label class="form-label">X (px)</label>
              <input type="number" class="form-control form-control-sm bi-x" value="${esc(b0.x ?? 0)}">
            </div>
            <div ${t0!=="arc" ? "" : "style='display:none'"} >
              <label class="form-label">Y (px)</label>
              <input type="number" class="form-control form-control-sm bi-y" value="${esc(b0.y ?? 0)}">
            </div>
            <div ${t0==="arc" ? "" : "style='display:none'"} >
              <label class="form-label">cx</label>
              <input type="number" class="form-control form-control-sm bi-cx" value="${esc(b0.cx ?? 0)}">
            </div>
            <div ${t0==="arc" ? "" : "style='display:none'"} >
              <label class="form-label">cy</label>
              <input type="number" class="form-control form-control-sm bi-cy" value="${esc(b0.cy ?? 0)}">
            </div>
            <div ${t0==="arc" ? "" : "style='display:none'"} >
              <label class="form-label">radiusPx</label>
              <input type="number" class="form-control form-control-sm bi-radius" value="${esc(b0.radiusPx ?? 0)}">
            </div>
            <div ${t0==="arc" ? "" : "style='display:none'"} >
              <label class="form-label">start°</label>
              <input type="number" class="form-control form-control-sm bi-start" value="${esc(b0.startAngleDeg ?? 0)}">
            </div>
            <div ${t0==="arc" ? "" : "style='display:none'"} >
              <label class="form-label">end°</label>
              <input type="number" class="form-control form-control-sm bi-end" value="${esc(b0.endAngleDeg ?? 0)}">
            </div>
          </div>

          <!-- Core text/label/arc styling -->
          <div class="tb-grid" ${t0==="svg" ? "style='display:none'" : ""}>
            ${t0==="label" ? `
              <div class="col-12">
                <label class="form-label">Label Text</label>
                <input type="text" class="form-control form-control-sm bi-text" value="${esc(b0.text ?? "")}">
              </div>
            ` : `
              <div class="col-12">
                <label class="form-label">Value (the text to render)</label>
                <input type="text" class="form-control form-control-sm bi-value" value="${esc(b0.value ?? "")}" placeholder="If set, this overrides slot data">
              </div>
            `}
            <div>
              <label class="form-label">Font</label>
              ${fontSelectHtml(b0.font || "")}
            </div>
            <div>
              <label class="form-label">Font Size (px)</label>
              <input type="number" class="form-control form-control-sm bi-fsz" value="${esc(b0.fontSizePx ?? 0)}">
            </div>
            <div>
              <label class="form-label">Letter Spacing</label>
              <input type="number" step="0.1" class="form-control form-control-sm bi-ls" value="${esc(b0.letterSpacing ?? 0)}">
            </div>
            <div>
              <label class="form-label">Fill</label>
              ${colorInput(b0.fill ?? "#000000", "bi-fill")}
            </div>
            <div>
              <label class="form-label">Stroke</label>
              ${colorInput(b0.stroke ?? "#000000", "bi-stroke")}
            </div>
            <div>
              <label class="form-label">Stroke Width</label>
              <input type="number" class="form-control form-control-sm bi-sw" value="${esc(b0.strokeWidth ?? 0)}">
            </div>
            <div>
              <label class="form-label">Align</label>
              <select class="form-select form-select-sm bi-align">
                <option value="left" ${b0.align==="left"?"selected":""}>left</option>
                <option value="center" ${(!b0.align||b0.align==="center")?"selected":""}>center</option>
                <option value="right" ${b0.align==="right"?"selected":""}>right</option>
              </select>
            </div>
            <div>
              <label class="form-label">vAlign</label>
              <select class="form-select form-select-sm bi-valign">
                <option value="baseline" ${(b0.vAlign||b0.yAnchor||"baseline")==="baseline"?"selected":""}>baseline</option>
                <option value="middle" ${b0.vAlign==="middle"?"selected":""}>middle</option>
                <option value="top" ${b0.vAlign==="top"||b0.yAnchor==="top"?"selected":""}>top</option>
                <option value="bottom" ${b0.vAlign==="bottom"?"selected":""}>bottom</option>
              </select>
            </div>
            <div>
              <label class="form-label">dyPx</label>
              <input type="number" class="form-control form-control-sm bi-dy" value="${esc(b0.dyPx ?? 0)}">
            </div>
          </div>

          <!-- AutoFix (shrink to fit) + Manual scale -->
          <div class="tb-grid" ${t0==="svg" ? "style='display:none'" : ""}>
            <div>
              <label class="form-label">AutoFix (shrink to fit)</label>
              <div class="form-check">
                <input class="form-check-input bi-af" type="checkbox" ${b0.autoFix ? "checked":""}>
                <label class="form-check-label">Enable</label>
              </div>
            </div>
            <div>
              <label class="form-label">AutoFix Mode</label>
              <select class="form-select form-select-sm bi-afmode">
                <option value="width" ${(b0.autoFixMode||"width")==="width"?"selected":""}>width</option>
                <option value="height" ${(b0.autoFixMode||"width")==="height"?"selected":""}>height</option>
                <option value="box" ${(b0.autoFixMode||"width")==="box"?"selected":""}>box</option>
              </select>
            </div>
            <div>
              <label class="form-label">fitWidthPx</label>
              <input type="number" class="form-control form-control-sm bi-afw" value="${esc(b0.autoFixWidthPx ?? 0)}">
            </div>

            <div>
              <label class="form-label">Box Left (px)</label>
              <input type="number" class="form-control form-control-sm bi-afl" value="${esc(afb.leftPx ?? 0)}">
            </div>
            <div>
              <label class="form-label">Box Right (px)</label>
              <input type="number" class="form-control form-control-sm bi-afr" value="${esc(afb.rightPx ?? 0)}">
            </div>
            <div>
              <label class="form-label">Box Top (px)</label>
              <input type="number" class="form-control form-control-sm bi-aft" value="${esc(afb.topPx ?? 0)}">
            </div>
            <div>
              <label class="form-label">Box Bottom (px)</label>
              <input type="number" class="form-control form-control-sm bi-afb" value="${esc(afb.bottomPx ?? 0)}">
            </div>

            <div>
              <label class="form-label">Manual scaleX</label>
              <input type="number" step="0.01" class="form-control form-control-sm bi-sx" value="${esc(b0.manualScaleX ?? 1)}">
            </div>
            <div>
              <label class="form-label">Manual scaleY</label>
              <input type="number" step="0.01" class="form-control form-control-sm bi-sy" value="${esc(b0.manualScaleY ?? 1)}">
            </div>
          </div>

          <hr>

          <!-- Separated Ring Outline -->
          <div class="tb-grid" ${t0==="svg" ? "style='display:none'" : ""}>
            <div>
              <label class="form-label">Ring Color</label>
              ${colorInput(ring.outerColor || "", "bi-ring-color")}
            </div>
            <div>
              <label class="form-label">Ring Width (px)</label>
              <input type="number" class="form-control form-control-sm bi-ring-width" value="${esc(ring.outerWidthPx ?? 0)}">
            </div>
            <div>
              <label class="form-label">Ring Gap (px)</label>
              <input type="number" class="form-control form-control-sm bi-ring-gap" value="${esc(ring.gapPx ?? 0)}">
            </div>
          </div>

          <!-- Double / Second Outline (font follows main font automatically) -->
          <div class="tb-grid" ${t0==="svg" ? "style='display:none'" : ""}>
            <div>
              <label class="form-label">Outline2 Color</label>
              ${colorInput(o2.color || "", "bi-o2-color")}
            </div>
            <div>
              <label class="form-label">Outline2 Width (px)</label>
              <input type="number" class="form-control form-control-sm bi-o2-width" value="${esc(o2.widthPx ?? 0)}">
            </div>
          </div>
        </div>
      </div>`;
        document.body.appendChild(wrap);

        if (!document.getElementById("tb-modal-css")) {
            const css = document.createElement("style");
            css.id = "tb-modal-css";
            css.textContent = `
        .tb-modal-wrap{position:fixed;inset:0;z-index:1050;display:flex;align-items:center;justify-content:center;}
        .tb-modal-backdrop{position:absolute;inset:0;background:rgba(0,0,0,.35);}
        .tb-modal{position:relative;background:#fff;border-radius:.5rem;box-shadow:0 10px 30px rgba(0,0,0,.25);width:min(1000px,94vw);max-height:88vh;display:flex;flex-direction:column;}
        .tb-modal-header{padding:.75rem 1rem;border-bottom:1px solid #e5e7eb;display:flex;align-items:center;justify-content:space-between;gap:8px;}
        .tb-modal-body{padding:1rem;overflow:auto;}
        .tb-modal-actions{display:flex;gap:.5rem;}
        .tb-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem;margin-bottom:.5rem;}
        @media (max-width: 1100px){ .tb-grid{grid-template-columns:1fr} }
      `;
            document.head.appendChild(css);
        }

        on(wrap.querySelector(".tb-close"), "click", () => wrap.remove());

        on(wrap.querySelector(".tb-save"), "click", () => {
            const tNew = normType(wrap.querySelector(".bi-type")?.value || t0);
            const out = { type: tNew };

            out.slot = wrap.querySelector(".bi-slot")?.value || b0.slot || "";
            out.rotationDeg = asNum(wrap.querySelector(".bi-rot")?.value, b0.rotationDeg || 0);

            if (tNew === "svg") {
                out.x = asNum(wrap.querySelector(".bi-x")?.value, b0.x || 0);
                out.y = asNum(wrap.querySelector(".bi-y")?.value, b0.y || 0);
                out.widthPx  = asNum(wrap.querySelector(".bi-w")?.value, b0.widthPx || 0);
                out.heightPx = asNum(wrap.querySelector(".bi-h")?.value, b0.heightPx || 0);
                out.href = esc(wrap.querySelector(".bi-href")?.value || b0.href || "");
            } else if (tNew === "arc") {
                out.cx = asNum(wrap.querySelector(".bi-cx")?.value, b0.cx || 0);
                out.cy = asNum(wrap.querySelector(".bi-cy")?.value, b0.cy || 0);
                out.radiusPx = asNum(wrap.querySelector(".bi-radius")?.value, b0.radiusPx || 0);
                out.startAngleDeg = asNum(wrap.querySelector(".bi-start")?.value, b0.startAngleDeg || 0);
                out.endAngleDeg   = asNum(wrap.querySelector(".bi-end")?.value, b0.endAngleDeg || 0);
            } else {
                out.x = asNum(wrap.querySelector(".bi-x")?.value, b0.x || 0);
                out.y = asNum(wrap.querySelector(".bi-y")?.value, b0.y || 0);
                if (tNew === "label") out.text  = esc(wrap.querySelector(".bi-text")?.value || b0.text || "");
                else                   out.value = esc(wrap.querySelector(".bi-value")?.value || b0.value || "");
            }

            if (tNew !== "svg") {
                out.font = ($(".bi-font", wrap)?.value ?? b0.font) || "";
                out.fontSizePx    = asInt($(".bi-fsz", wrap)?.value, b0.fontSizePx || 0);
                out.letterSpacing = asNum($(".bi-ls",  wrap)?.value, b0.letterSpacing || 0);
                out.fill   = asHex($(".bi-fill",  wrap)?.value || b0.fill || "#000000", "#000000");
                out.stroke = asHex($(".bi-stroke",wrap)?.value || b0.stroke || "#000000", "#000000");
                out.strokeWidth = asInt($(".bi-sw", wrap)?.value, b0.strokeWidth || 0);
                out.align  = ($(".bi-align",  wrap)?.value || b0.align  || "center");
                out.vAlign = ($(".bi-valign", wrap)?.value || b0.vAlign || "baseline");
                out.dyPx   = asInt($(".bi-dy",    wrap)?.value, b0.dyPx || 0);

                // AutoFix reads
                out.autoFix        = !!$(".bi-af", wrap)?.checked;
                out.autoFixMode    = $(".bi-afmode", wrap)?.value || (b0.autoFixMode || "width");
                out.autoFixWidthPx = asInt($(".bi-afw", wrap)?.value, b0.autoFixWidthPx || 0);

                const leftPx   = asInt($(".bi-afl", wrap)?.value, b0.autoFixBox?.leftPx   || 0);
                const rightPx  = asInt($(".bi-afr", wrap)?.value, b0.autoFixBox?.rightPx  || 0);
                const topPx    = asInt($(".bi-aft", wrap)?.value, b0.autoFixBox?.topPx    || 0);
                const bottomPx = asInt($(".bi-afb", wrap)?.value, b0.autoFixBox?.bottomPx || 0);
                out.autoFixBox = { leftPx, rightPx, topPx, bottomPx };

                // Manual scale
                out.manualScaleX = asNum($(".bi-sx", wrap)?.value, b0.manualScaleX ?? 1);
                out.manualScaleY = asNum($(".bi-sy", wrap)?.value, b0.manualScaleY ?? 1);

                // separated ring outline
                const ringColor = $(".bi-ring-color", wrap)?.value || b0.separatedOutline?.outerColor || "";
                const ringWidth = asInt($(".bi-ring-width", wrap)?.value, b0.separatedOutline?.outerWidthPx || 0);
                const ringGap   = asInt($(".bi-ring-gap",   wrap)?.value, b0.separatedOutline?.gapPx || 0);
                out.separatedOutline = { outerColor: ringColor, outerWidthPx: ringWidth, gapPx: ringGap };

                // double/second outline (font follows main font)
                const o2Color = $(".bi-o2-color", wrap)?.value || b0.outline2?.color || "";
                const o2Width = asInt($(".bi-o2-width", wrap)?.value, b0.outline2?.widthPx || 0);
                const mainFont = out.font || b0.font || "";
                out.outline2 = { color: o2Color, widthPx: o2Width, font: mainFont };
            }

            // merge + cleanup incompatible/legacy fields
            const merged = {...b0, ...out};
            const tt = normType(merged.type);

            // legacy squeeze fields -> drop
            delete merged.squeezeToFit;
            delete merged.squeezeMode;
            delete merged.fitWidthPx;
            delete merged.fitBox;

            if (tt === "svg") {
                delete merged.font; delete merged.fontSizePx; delete merged.letterSpacing;
                delete merged.fill; delete merged.stroke; delete merged.strokeWidth;
                delete merged.align; delete merged.vAlign; delete merged.dyPx;
                delete merged.outline2; delete merged.separatedOutline;
                delete merged.autoFix; delete merged.autoFixMode; delete merged.autoFixWidthPx; delete merged.autoFixBox;
                delete merged.manualScaleX; delete merged.manualScaleY;
                delete merged.text; delete merged.value;
                delete merged.cx; delete merged.cy; delete merged.radiusPx; delete merged.startAngleDeg; delete merged.endAngleDeg;
            } else if (tt === "arc") {
                delete merged.widthPx; delete merged.heightPx; delete merged.href;
            } else if (tt === "label") {
                delete merged.value;
            } else if (tt === "text") {
                delete merged.text;
            }

            STATE.blocks[idx] = merged;
            renderBlocksTable();
            syncJsonFromState();
            wrap.remove();
        });
    }

    // ---------- form <-> template ----------
    function setFormFromTemplate(tpl) {
        STATE.tpl = shallowClone(tpl || blankTemplate());
        STATE.blocks = shallowClone(STATE.tpl.blocks || []);

        (STATE.blocks || []).forEach(b => {
            if (!b.vAlign && b.yAnchor) {
                const m = String(b.yAnchor).toLowerCase();
                b.vAlign = (m === "middle" ? "middle" : (m === "baseline" ? "baseline" : m));
            }
            if (normType(b.type) === "text" && typeof b.value !== "string") b.value = "";
            migrateBlockFields(b);
        });

        if (elWidthIn)  elWidthIn.value  = STATE.tpl.widthIn ?? 12;
        if (elHeightIn) elHeightIn.value = STATE.tpl.heightIn ?? 4;
        if (elDpi)      elDpi.value      = STATE.tpl.dpi ?? 300;
        if (elGap)      elGap.value      = STATE.tpl.gapAdjustPx ?? 0;

        const sc = STATE.tpl.scaling || {};
        if (elScaleName)    elScaleName.value   = sc.name ?? 1;
        if (elScaleNum)     elScaleNum.value    = sc.number ?? 1;
        if (elScaleStroke)  elScaleStroke.checked = (sc.scaleStroke !== false);

        const dn = STATE.tpl.defaults?.name || {};
        if (elNameFont)  elNameFont.value  = dn.font || "";
        if (elNameFill)  elNameFill.value  = dn.fill || "#000000";
        if (elNameStroke)elNameStroke.value= dn.stroke || "#ffffff";
        if (elNameSW)    elNameSW.value    = dn.strokeWidth ?? 0;
        if (elNameLS)    elNameLS.value    = dn.letterSpacing ?? 0;
        if (elNameRingColor) elNameRingColor.value = dn.separatedOutline?.outerColor || "";
        if (elNameRingWidth) elNameRingWidth.value = dn.separatedOutline?.outerWidthPx ?? 0;
        if (elNameRingGap)   elNameRingGap.value   = dn.separatedOutline?.gapPx ?? 0;
        if (elNameO2Color)   elNameO2Color.value   = dn.outline2?.color || "";
        if (elNameO2Width)   elNameO2Width.value   = dn.outline2?.widthPx ?? 0;
        if (elNameO2Font)    elNameO2Font.value    = dn.outline2?.font || "";

        const dm = STATE.tpl.defaults?.number || {};
        if (elNumFont)   elNumFont.value   = dm.font || "";
        if (elNumFill)   elNumFill.value   = dm.fill || "#000000";
        if (elNumStroke) elNumStroke.value = dm.stroke || "#ffffff";
        if (elNumSW)     elNumSW.value     = dm.strokeWidth ?? 0;
        if (elNumLS)     elNumLS.value     = dm.letterSpacing ?? 0;
        if (elNumRingColor) elNumRingColor.value = dm.separatedOutline?.outerColor || "";
        if (elNumRingWidth) elNumRingWidth.value = dm.separatedOutline?.outerWidthPx ?? 0;
        if (elNumRingGap)   elNumRingGap.value   = dm.separatedOutline?.gapPx ?? 0;
        if (elNumO2Color)   elNumO2Color.value   = dm.outline2?.color || "";
        if (elNumO2Width)   elNumO2Width.value   = dm.outline2?.widthPx ?? 0;
        if (elNumO2Font)    elNumO2Font.value    = dm.outline2?.font || "";

        renderBlocksTable();
        syncJsonFromState();

        ensureDataUI();
        generateDataFromTemplate({preserveExisting:true});
    }

    function getTemplateFromForm() {
        const tpl = shallowClone(STATE.tpl || blankTemplate());
        tpl.widthIn   = asNum(elWidthIn?.value  || tpl.widthIn,   12);
        tpl.heightIn  = asNum(elHeightIn?.value || tpl.heightIn,   4);
        tpl.dpi       = asInt(elDpi?.value      || tpl.dpi,      300);
        tpl.gapAdjustPx = asInt(elGap?.value    || tpl.gapAdjustPx, 0);
        tpl.scaling   = {
            name: asNum(elScaleName?.value || 1, 1),
            number: asNum(elScaleNum?.value || 1, 1),
            scaleStroke: !!(elScaleStroke?.checked),
        };
        tpl.defaults = shallowClone(STATE.tpl.defaults || {});
        tpl.blocks   = shallowClone(STATE.blocks || []);
        return tpl;
    }

    function syncJsonFromState() {
        if (!elJson) return;
        try { elJson.value = JSON.stringify(getTemplateFromForm(), null, 2); } catch {}
    }
    function syncFormFromJson() {
        if (!elJson) return;
        try {
            const raw = elJson.value.trim();
            if (!raw) return;
            const tpl = JSON.parse(raw);
            // ensure migrated fields after manual JSON edits
            (tpl.blocks || []).forEach(migrateBlockFields);
            setFormFromTemplate(tpl);
        } catch { showAlert("warning", "Invalid JSON; fix JSON or use the form controls."); }
    }

    // ---------- Template CRUD ----------
    async function loadTemplateBySlug(slug) {
        if (!slug) throw new Error("Slug required.");
        const url = `${urls.get}${urls.get.includes("?") ? "&" : "?"}slug=${encodeURIComponent(slug)}`;
        const data = await fetchJSON(url, {method:"GET"});

        let tpl = null;
        if (data && data.success && (data.template || data.item)) {
            tpl = data.template || data.item;
        } else if (data && data.widthIn && data.heightIn && data.dpi) {
            tpl = data;
        } else if (data && data.templates && Array.isArray(data.templates)) {
            tpl = data.templates.find(t => (t.id || t.slug) === slug) || null;
        }
        if (!tpl) throw new Error("Template not found or bad response.");

        (tpl.blocks || []).forEach(b => {
            if (!b.vAlign && b.yAnchor) {
                const m = String(b.yAnchor).toLowerCase();
                b.vAlign = (m === "middle" ? "middle" : (m === "baseline" ? "baseline" : m));
            }
            if (normType(b.type) === "text" && typeof b.value !== "string") b.value = "";
            migrateBlockFields(b);
        });

        if (elJson) elJson.value = JSON.stringify(tpl, null, 2);
        setFormFromTemplate(tpl);
        showAlert("success", `Loaded template "${slug}".`);
    }

    async function saveTemplate(slug, tpl) {
        const payload = {slug, template: tpl};
        const data = await fetchJSON(urls.save, {method:"POST", body: JSON.stringify(payload)});
        if (!data || data.success === false) throw new Error(data?.message || "Save failed");
        showAlert("success", "Template saved.");
    }
    async function saveAsTemplate(slug, tpl) {
        const payload = {slug, template: tpl};
        const data = await fetchJSON(urls.create, {method:"POST", body: JSON.stringify(payload)});
        if (!data || data.success === false) throw new Error(data?.message || "Save As failed");
        showAlert("success", `Created template "${slug}".`);
    }
    async function deleteTemplate(slug) {
        const payload = {slug};
        const data = await fetchJSON(urls.del, {method:"POST", body: JSON.stringify(payload)});
        if (!data || data.success === false) throw new Error(data?.message || "Delete failed");
        showAlert("success", `Deleted template "${slug}".`);
    }

    // ---------- Preview ----------
    async function runPreview() {
        // inline edits + gather current template + data
        applyTableInlineEdits();
        updateDataFromTable?.();
        const tpl = getTemplateFromForm();

        // data object
        const dataOut = {};
        Object.entries(STATE.data || {}).forEach(([k, v]) => {
            if (String(k).trim().length) dataOut[k] = v;
        });

        // robust debug detector
        function isDebugOn() {
            const sels = ['#tb-debug', '#f-debug', '#pv-debug', '#debug', '[name="debug"]'];
            for (const sel of sels) {
                const el = document.querySelector(sel);
                if (!el) continue;
                if (typeof el.checked === 'boolean') return !!el.checked;
                const v = String(el.value ?? '').toLowerCase();
                if (v === '1' || v === 'true' || v === 'on' || v === 'yes') return true;
            }
            return false;
        }
        const debugEnabled = isDebugOn();

        // normalize block types (straight->text)
        const normalizedBlocks = (tpl.blocks || []).map(b => {
            const t = String(b.type || 'text').toLowerCase() === 'straight' ? 'text' : String(b.type || 'text').toLowerCase();
            return compatAutoFixShim({ ...b, type: t });
        });

        const payload = {
            template_inline: { ...tpl, blocks: normalizedBlocks },
            data: dataOut,
            format: "png",
            preserveCase: true,
            embedFonts: true,
            dpi: tpl.dpi || 300,
            debug: !!debugEnabled
        };

        // UI: spinner on
        if (elPvImg) elPvImg.src = "";
        elPvWrap && elPvWrap.classList.add("loading");
        elPvPlaceholder && elPvPlaceholder.classList.add("d-none");
        elPvSpinner && elPvSpinner.classList.remove("d-none");

        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
            const headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            };
            if (csrfToken) {
                headers['X-CSRF-TOKEN'] = csrfToken;
            }

            const r = await fetch(urls.preview + (debugEnabled ? (urls.preview.includes('?') ? '&' : '?') + 'debug=1' : ''), {
                method: "POST",
                credentials: "same-origin",
                headers: headers,
                body: JSON.stringify(payload),
                cache: "no-store"
            });
            if (!r.ok) {
                let msg = `HTTP ${r.status}`;
                try {
                    const err = await r.json();
                    if (err && err.message) msg = err.message;
                } catch (_) {}
                throw new Error(msg);
            }

            // dump debug headers into <pre id="tb-debug-log"> if present (or console)
            if (debugEnabled) {
                const wanted = [
                    "X-Fit-Log", "X-Fit-Passes", "X-Fit-Mode", "X-Fit-Tried",
                    "X-Arc-Relax", "X-NN-SizeIn", "X-NN-ViewBoxPx", "X-NN-Pixels", "X-NN-DPI-Req"
                ];
                const lines = [];
                for (const k of wanted) {
                    const v = r.headers.get(k);
                    if (v !== null) lines.push(`${k}: ${v}`);
                }
                const dump = lines.join("\n") || "(no debug headers returned)";
                const sink = document.getElementById("tb-debug-log");
                if (sink) sink.textContent = dump;
                else console.info("[Preview Debug Headers]\n" + dump);
            }

            const ct = r.headers.get("content-type") || "";
            if (ct.startsWith("image/") || ct === "application/octet-stream") {
                const blob = await r.blob();
                const url = URL.createObjectURL(blob);
                elPvImg && (elPvImg.src = url);
                elPvImg && elPvImg.classList.remove("d-none");
            } else if (ct.includes("application/json")) {
                const j = await r.json();
                if (j.png_base64) {
                    elPvImg && (elPvImg.src = `data:image/png;base64,${j.png_base64}`);
                    elPvImg && elPvImg.classList.remove("d-none");
                } else if (j.url || j.png) {
                    elPvImg && (elPvImg.src = j.url || j.png);
                    elPvImg && elPvImg.classList.remove("d-none");
                } else {
                    throw new Error(j.message || "No preview image returned");
                }
            } else {
                const txt = await r.text();
                throw new Error(`Unexpected preview content-type: ${ct} — ${txt.slice(0, 200)}`);
            }
        } catch (e) {
            elPvPlaceholder && elPvPlaceholder.classList.remove("d-none");
            if (typeof showAlert === "function") showAlert("danger", `Preview failed: ${e.message}`);
            console.error(e);
        } finally {
            elPvWrap && elPvWrap.classList.remove("loading");
            elPvSpinner && elPvSpinner.classList.add("d-none");
        }
    }

    // ---------- wire up ----------
    on(elBlockRows, "click", (ev) => {
        const tr = ev.target.closest("tr");
        if (!tr) return;
        const idx = +tr.dataset.idx;

        if (ev.target.closest(".bl-edit")) { openInspector(idx); return; }
        if (ev.target.closest(".bl-del"))  { STATE.blocks.splice(idx, 1); renderBlocksTable(); syncJsonFromState(); return; }
    });

    on(elBlockRows, "change", () => { applyTableInlineEdits(); renderBlocksTable(); syncJsonFromState(); });

    on(elAddBlock, "click", () => {
        STATE.blocks.push({
            slot:"TEXT1", type:"text", x:100, y:100, fontSizePx:120, letterSpacing:0,
            align:"left", vAlign:"baseline", dyPx:0, value:"",
            autoFix:false, autoFixMode:"width", autoFixWidthPx:0, autoFixBox:{leftPx:0,rightPx:0,topPx:0,bottomPx:0},
            manualScaleX:1, manualScaleY:1,
            separatedOutline:{outerColor:"", outerWidthPx:0, gapPx:0}, outline2:{color:"", widthPx:0, font:""}
        });
        renderBlocksTable();
        syncJsonFromState();
    });

    on(elLoad, "click", async () => {
        try {
            const slug = (elSlug && elSlug.value || "").trim();
            if (!slug) return showAlert("warning", "Enter a slug to load.");
            await loadTemplateBySlug(slug);
        } catch (e) { showAlert("danger", e.message || "Load failed"); }
    });

    on(elSave, "click", async () => {
        try {
            const slug = (elSlug && elSlug.value || "").trim();
            if (!slug) return showAlert("warning", "Enter a slug to save.");
            await saveTemplate(slug, getTemplateFromForm());
        } catch (e) { showAlert("danger", e.message || "Save failed"); }
    });

    on(elSaveAs, "click", async () => {
        try {
            const slug = (elSlug && elSlug.value || "").trim();
            if (!slug) return showAlert("warning", "Enter a slug for Save As.");
            await saveAsTemplate(slug, getTemplateFromForm());
        } catch (e) { showAlert("danger", e.message || "Save As failed"); }
    });

    on(elDelete, "click", async () => {
        try {
            const slug = (elSlug && elSlug.value || "").trim();
            if (!slug) return showAlert("warning", "Enter a slug to delete.");
            if (!confirm(`Delete template "${slug}"?`)) return;
            await deleteTemplate(slug);
            const tpl = blankTemplate();
            setFormFromTemplate(tpl);
            elJson && (elJson.value = JSON.stringify(tpl, null, 2));
        } catch (e) { showAlert("danger", e.message || "Delete failed"); }
    });

    on(elPvRun, "click", runPreview);

    [
        elWidthIn, elHeightIn, elDpi, elGap,
        elScaleName, elScaleNum, elScaleStroke,
        elNameFont, elNameFill, elNameStroke, elNameSW, elNameLS,
        elNameRingColor, elNameRingWidth, elNameRingGap,
        elNameO2Color, elNameO2Width, elNameO2Font,
        elNumFont, elNumFill, elNumStroke, elNumSW, elNumLS,
        elNumRingColor, elNumRingWidth, elNumRingGap,
        elNumO2Color, elNumO2Width, elNumO2Font
    ].forEach((el) => on(el, "input", syncJsonFromState));

    on(elJson, "input", () => {
        clearTimeout(elJson?._t);
        if (elJson) elJson._t = setTimeout(syncFormFromJson, 300);
    });

    // ---------- init ----------
    (async function init() {
        await loadFonts();
        ensureDataUI();
        const initSlug = (elSlug && typeof elSlug.value === "string") ? elSlug.value.trim() : "";
        if (initSlug) {
            try { await loadTemplateBySlug(initSlug); return; }
            catch (e) { showAlert("warning", `Auto-load failed for "${initSlug}": ${e.message}. Starting blank.`); }
        }
        const initial = blankTemplate();
        setFormFromTemplate(initial);
        elJson && (elJson.value = JSON.stringify(initial, null, 2));
    })();
})();
