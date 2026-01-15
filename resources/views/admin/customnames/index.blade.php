<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Custom Names • Templates') }}
        </h2>
    </x-slot>

    <div class="container py-4">
        <div class="d-flex align-items-center mb-3 gap-2">
            <h3 class="mb-0"><i class="bi bi-layers me-2"></i>Local Templates</h3>
            <a href="{{ route('admin.customnames.templatebuilder') }}" class="btn btn-sm btn-success ms-auto">
                <i class="bi bi-plus-lg me-1"></i> New Template
            </a>
        </div>

        <form method="get" action="{{ route('admin.customnames.index') }}" class="mb-3">
            <div class="row g-2">
                <div class="col-md-5">
                    <input type="text" name="q" value="{{ $q }}" class="form-control"
                           placeholder="Search by ID, slug, or name">
                </div>
                <div class="col-md-2">
                    <select name="limit" class="form-select">
                        @foreach ([25,50,100,200] as $opt)
                            <option value="{{ $opt }}" {{ $limit == $opt ? 'selected' : '' }}>{{ $opt }} / page</option>
                        @endforeach
                    </select>
                </div>
                <div class="col-md-2">
                    <button class="btn btn-primary w-100"><i class="bi bi-search me-1"></i> Filter</button>
                </div>
                <div class="col-md-2">
                    <a class="btn btn-outline-secondary w-100" href="{{ route('admin.customnames.index') }}">
                        <i class="bi bi-arrow-clockwise me-1"></i> Reset
                    </a>
                </div>
            </div>
        </form>

        <div class="card shadow-sm border-0 rounded-3">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="bg-light">
                    <tr>
                        <th style="width:110px;">ID</th>
                        <th>Slug</th>
                        <th>Name</th>
                        <th style="width:180px;">Updated</th>
                        <th style="width:260px;" class="text-end">Actions</th>
                    </tr>
                    </thead>
                    <tbody>
                    @if($templates->count() > 0)
                        @foreach ($templates as $t)
                            <tr>
                                <td class="text-muted">{{ $t->id }}</td>
                                <td><code>{{ $t->slug }}</code></td>
                                <td>{{ $t->name ?: "(untitled)" }}</td>
                                <td>
                                    @if ($t->updated_at)
                                        {{ $t->updated_at->format('Y-m-d H:i') }}
                                    @else—@endif
                                </td>
                                <td class="text-end">
                                    <a href="{{ route('admin.customnames.templatebuilder', ['slug' => $t->slug]) }}" class="btn btn-sm btn-primary">
                                        <i class="bi bi-pencil me-1"></i> Edit
                                    </a>
                                    <button type="button" class="btn btn-sm btn-outline-secondary js-preview" data-slug="{{ $t->slug }}">
                                        <i class="bi bi-eye me-1"></i> Preview
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-danger js-delete" data-slug="{{ $t->slug }}">
                                        <i class="bi bi-trash me-1"></i> Delete
                                    </button>
                                </td>
                            </tr>
                        @endforeach
                    @else
                        <tr>
                            <td colspan="5" class="text-center text-muted py-4">No templates found.</td>
                        </tr>
                    @endif
                    </tbody>
                </table>
            </div>
        </div>

        @if ($templates->hasPages())
            <div class="mt-3">
                {{ $templates->links() }}
            </div>
        @endif
    </div>

    @push('scripts')
    <script>
        document.addEventListener('DOMContentLoaded', function () {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

            // Delete
            document.querySelectorAll('.js-delete').forEach(function (btn) {
                btn.addEventListener('click', async function () {
                    const slug = this.dataset.slug;
                    if (!confirm('Delete template "' + slug + '"?')) return;

                    try {
                        const resp = await fetch('{{ route('admin.customnames.template.delete') }}', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Accept': 'application/json',
                                'X-CSRF-TOKEN': csrfToken
                            },
                            body: JSON.stringify({ slug: slug })
                        });
                        const out = await resp.json();
                        if (out && out.success) {
                            location.reload();
                        } else {
                            alert('Delete failed: ' + (out && (out.message || out.error) || 'Unknown error'));
                        }
                    } catch (e) {
                        alert('Delete error: ' + e.message);
                    }
                });
            });

            // Preview
            document.querySelectorAll('.js-preview').forEach(function (btn) {
                btn.addEventListener('click', async function () {
                    const slug = this.dataset.slug;
                    try {
                        const resp = await fetch('{{ route('admin.customnames.preview') }}', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Accept': 'application/json',
                                'X-CSRF-TOKEN': csrfToken
                            },
                            body: JSON.stringify({ slug: slug })
                        });
                        const out = await resp.json();
                        if (out && out.success && out.url) {
                            window.open(out.url, '_blank');
                        } else {
                            alert('Preview failed: ' + (out && (out.message || out.error) || 'Unknown error'));
                        }
                    } catch (e) {
                        alert('Preview error: ' + e.message);
                    }
                });
            });
        });
    </script>
    @endpush
</x-app-layout>
