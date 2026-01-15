(function () {
    const dpiEl = document.getElementById('tpl-dpi');
    const wEl = document.getElementById('tpl-width');
    const hEl = document.getElementById('tpl-height');
    const slugEl = document.getElementById('tpl-slug');

    const canvasEl = new fabric.Canvas('tpl-canvas', {selection: true, preserveObjectStacking: true});

    function resizeCanvas() {
        const dpi = parseInt(dpiEl.value || 300, 10);
        const wIn = parseFloat(wEl.value || 12);
        const hIn = parseFloat(hEl.value || 12);
        const w = Math.round(wIn * dpi);
        const h = Math.round(hIn * dpi);
        canvasEl.setWidth(w);
        canvasEl.setHeight(h);
        canvasEl.renderAll();
    }

    function addBlock(slot) {
        const text = new fabric.Text(slot, {
            left: canvasEl.getWidth() / 2, top: canvasEl.getHeight() / 2,
            originX: 'center', originY: 'center',
            fontFamily: 'Impact', fontSize: 200,
            fill: '#FFFFFF', stroke: '#000000', strokeWidth: 10, paintFirst: 'stroke'
        });
        text.set({_meta: {slot, letterSpacingPx: 0, arcRadiusPx: 0, maxWidthPx: canvasEl.getWidth() - 200}});
        canvasEl.add(text);
        canvasEl.setActiveObject(text);
        canvasEl.renderAll();
    }

    function toTemplateJSON() {
        const dpi = parseInt(dpiEl.value || 300, 10);
        const out = {
            dpi,
            widthIn: parseFloat(wEl.value || 12),
            heightIn: parseFloat(hEl.value || 12),
            background: 'transparent',
            blocks: []
        };
        canvasEl.getObjects().forEach(o => {
            if (!o._meta) return;
            out.blocks.push({
                slot: o._meta.slot, x: Math.round(o.left), y: Math.round(o.top),
                fontFamily: o.fontFamily || 'Impact', fontSizePx: Math.round(o.fontSize),
                letterSpacing: Math.round(o._meta.letterSpacingPx || 0), align: 'center',
                fill: o.fill || '#FFFFFF', stroke: o.stroke || '#000000',
                strokeWidthPx: Math.round(o.strokeWidth || 0),
                maxWidthPx: Math.round(o._meta.maxWidthPx || (canvasEl.getWidth() - 100)),
                arc: {radiusPx: Math.round(o._meta.arcRadiusPx || 0), direction: 'normal'},
                transform: {scaleX: o.scaleX || 1, scaleY: o.scaleY || 1, rotationDeg: o.angle || 0, skewX: 0, skewY: 0}
            });
        });
        return out;
    }

    function fromTemplateJSON(tpl) {
        canvasEl.clear();
        dpiEl.value = tpl.dpi || 300;
        wEl.value = tpl.widthIn || 12;
        hEl.value = tpl.heightIn || 12;
        resizeCanvas();
        (tpl.blocks || []).forEach(b => {
            const text = new fabric.Text(b.slot || 'TEXT', {
                left: b.x || 100, top: b.y || 100, originX: 'left', originY: 'top',
                fontFamily: b.fontFamily || 'Impact', fontSize: b.fontSizePx || 120,
                fill: b.fill || '#FFFFFF', stroke: b.stroke || '#000000', strokeWidth: b.strokeWidthPx || 0,
                angle: (b.transform && b.transform.rotationDeg) || 0, paintFirst: 'stroke'
            });
            text.set({
                _meta: {
                    slot: b.slot || 'TEXT',
                    letterSpacingPx: b.letterSpacing || 0,
                    arcRadiusPx: (b.arc && b.arc.radiusPx) || 0,
                    maxWidthPx: b.maxWidthPx || (canvasEl.getWidth() - 100)
                }
            });
            canvasEl.add(text);
        });
        canvasEl.renderAll();
    }

    function loadFromNode() {
        const slug = slugEl.value.trim();
        if (!slug) return alert('Enter slug first.');
        $.getJSON('/admin/customnames/template/get', {slug})
            .done(res => {
                if (!res.success) return alert(res.message || 'Load failed');
                fromTemplateJSON(res.template);
            })
            .fail(xhr => {
                alert('Load failed: ' + (xhr.responseText || xhr.status));
            });
    }

    function saveToNode(isCreate = false) {
        const slug = slugEl.value.trim();
        if (!slug) return alert('Enter slug first.');
        const schema = JSON.stringify(toTemplateJSON());
        const url = isCreate ? '/admin/customnames/template/create' : '/admin/customnames/template/save';
        $.post(url, {slug, schema_json: schema}, function (res) {
            alert(res.success ? (isCreate ? 'Created' : 'Saved') : (res.message || 'Failed'));
        }, 'json');
    }

    function preview() {
        const slug = slugEl.value.trim();
        if (!slug) return alert('Enter slug first. Save/create on Node, then preview by slug.');

        $.post('/admin/customnames/preview', {
            slug,
            name: $('#sample-name').val(),
            number: $('#sample-number').val(),
            format: $('#preview-format').val()
        }, function (res) {
            if (!res || !res.success) {
                return alert((res && res.message) || 'Preview failed');
            }
            const url = res.url || res.dataUrl || res.png || res.svg;
            if (!url) return alert('Preview returned no URL/data.');
            $('#preview-out').html('<img class="img-fluid" src="' + url + '">');
        }, 'json').fail(function (xhr) {
            alert('Preview error: ' + (xhr.responseText || xhr.status));
        });
    }

    // Font picker
    function populateFonts() {
        $.getJSON('/admin/customnames/fonts/list', function (res) {
            const $sel = $('#block-font');
            $sel.empty();
            if (!res.success) return $sel.append('<option value="">(load failed)</option>');
            const fonts = Array.isArray(res.fonts) ? res.fonts : [];
            $sel.append('<option value="">(default)</option>');
            fonts.forEach(f => {
                const name = f.family || f.slug || f.name || '';
                if (name) $sel.append('<option value="' + name + '">' + name + '</option>');
            });
        });
    }

    $('#btn-font-refresh').on('click', function () {
        $.post('/admin/customnames/font/reload', {}, function () {
            populateFonts();
        }, 'json');
    });
    $('#block-font').on('change', function () {
        const obj = canvasEl.getActiveObject();
        if (!obj) return alert('Select a text object first');
        obj.set({fontFamily: this.value || 'Impact'});
        canvasEl.requestRenderAll();
    });

    // Buttons / init
    $('#add-name').on('click', () => addBlock('NAME'));
    $('#add-number').on('click', () => addBlock('NUMBER'));
    $('#btn-load').on('click', loadFromNode);
    $('#btn-save').on('click', () => saveToNode(false));
    $('#btn-create').on('click', () => saveToNode(true));
    $('#btn-preview').on('click', preview);
    $('#tpl-dpi, #tpl-width, #tpl-height').on('change', resizeCanvas);

    populateFonts();
    const s = (slugEl.value || '').trim();
    if (s) loadFromNode(); else resizeCanvas();
})();
