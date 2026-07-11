<h5 class="mb-4">My Images</h5>
@if($images->count() > 0)
    <div class="row row-cols-2 row-cols-md-4 row-cols-lg-6 g-3">
        @foreach($images as $image)
            <div class="col">
                <div class="card h-100 shadow-sm border-0 rounded-3">
                    <div class="checkerboard d-flex align-items-center justify-content-center p-2 rounded-top position-relative overflow-hidden border-bottom" style="height: 140px; background-color: #f8f9fa;">
                        <img src="{{ $image->image }}" class="img-fluid rounded" style="max-height: 120px; transition: transform .3s ease; image-rendering: -webkit-optimize-contrast;" alt="{{ $image->image_name }}" onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'">
                    </div>
                    <div class="card-body p-2 text-center d-flex flex-column">
                        <p class="small fw-bold mb-1 text-truncate" title="{{ $image->image_name }}">
                            {{ $image->image_name ?: 'Unnamed' }}
                        </p>
                        <div class="d-flex justify-content-center gap-1 mt-auto pt-2">
                            <a href="{{ $image->image }}" target="_blank" class="btn btn-sm btn-light p-1" title="View full size">
                                <i class="bi bi-zoom-in"></i>
                            </a>
                            <a href="{{ route('account.images.download', $image->id) }}" class="btn btn-sm btn-light p-1" title="Download image">
                                <i class="bi bi-download"></i>
                            </a>
                            <form action="{{ route('cart.use_existing') }}" method="POST" class="d-inline">
                                @csrf
                                <input type="hidden" name="dtfimage_id" value="{{ $image->id }}">
                                <button type="submit" class="btn btn-sm btn-outline-primary p-1" style="font-size: 0.7rem;" title="Re-order this image">
                                    <i class="bi bi-cart-plus me-1"></i>Re-order
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        @endforeach
    </div>
@else
    <div class="text-center py-5">
        <i class="bi bi-image fs-1 text-muted opacity-25"></i>
        <p class="mt-3 text-muted">No images found.</p>
    </div>
@endif
