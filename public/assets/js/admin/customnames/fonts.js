(function () {
    function rowHtml(f, idx) {
        const slug = f.slug || f.name || f.family || f.id || ('font-' + idx);
        const family = f.family || '';
        const file = f.filename || f.file || '';
        return `
      <tr>
        <td>${idx + 1}</td>
        <td><code>${slug}</code></td>
        <td>${family}</td>
        <td>${file}</td>
      </tr>
    `;
    }

    const URLS = window.API_URLS || {
        list: '/admin/customnames/fonts/list',
        upload: '/admin/customnames/fonts/upload',
        reload: '/admin/customnames/fonts/reload'
    };

    function loadList() {
        $('#fonts-table').text('Loading…');
        $.getJSON(URLS.list, function (res) {
            if (!res.success) return $('#fonts-table').text('Failed: ' + (res.message || 'Unknown'));
            const items = Array.isArray(res.fonts) ? res.fonts : (Array.isArray(res.data) ? res.data : []);
            const rows = items.map((f, i) => rowHtml(f, i)).join('');
            $('#fonts-table').html(`
        <div class="table-responsive">
          <table class="table table-sm align-middle">
            <thead><tr><th>#</th><th>Slug</th><th>Family</th><th>File</th></tr></thead>
            <tbody>${rows || '<tr><td colspan="4">No fonts reported by Node.</td></tr>'}</tbody>
          </table>
        </div>
      `);
        }).fail(() => $('#fonts-table').text('Error loading fonts.'));
    }

    $('#font-upload-form').on('submit', function (e) {
        e.preventDefault();
        const fd = new FormData(this);
        const file = fd.get('font');
        if (!file || !file.size) return alert('Choose a font file first.');
        $.ajax({
            url: URLS.upload,
            type: 'POST',
            data: fd,
            processData: false,
            contentType: false,
            dataType: 'json',
            headers: {
                'X-CSRF-TOKEN': $('meta[name="csrf-token"]').attr('content')
            }
        }).done(res => {
            if (res.success) {
                alert('Uploaded. Now reloading fonts…');
                $('#btn-reload-fonts').trigger('click');
            } else {
                alert(res.message || 'Upload failed');
            }
        }).fail(() => alert('Upload error'));
    });

    $('#btn-reload-fonts').on('click', function () {
        $.ajax({
            url: URLS.reload,
            type: 'POST',
            dataType: 'json',
            headers: {
                'X-CSRF-TOKEN': $('meta[name="csrf-token"]').attr('content')
            }
        }).done(res => {
            if (res.success) {
                alert('Fonts reloaded on Node.');
                loadList();
            } else {
                alert(res.message || 'Reload failed');
            }
        }).fail(() => alert('Reload error'));
    });

    $('#btn-refresh-list').on('click', loadList);

    loadList();
})();
