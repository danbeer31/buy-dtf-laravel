<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('My Account') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <!-- Business Information -->
            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-header bg-white border-0 py-3">
                    <h5 class="mb-0 fw-bold">Business Information</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <p><strong>Business Name:</strong> {{ $business->business_name }}</p>
                            <p><strong>Contact Name:</strong> {{ $business->contact_name }}</p>
                            <p><strong>Email:</strong> {{ $business->email }}</p>
                            <p><strong>Phone:</strong> {{ $business->phone }}</p>
                        </div>
                        <div class="col-md-6">
                            <p><strong>Address:</strong> {{ $business->address }} {{ $business->address2 }}</p>
                            <p><strong>City:</strong> {{ $business->city }}</p>
                            <p><strong>State:</strong> {{ $business->state }}</p>
                            <p><strong>Zip:</strong> {{ $business->zip }}</p>
                        </div>
                    </div>
                    <div class="mt-3">
                        <a href="{{ route('profile.edit') }}" class="btn btn-sm btn-outline-primary">Edit Profile Settings</a>
                    </div>
                </div>
            </div>

            <!-- Tabs for Orders and Images -->
            <div class="card shadow-sm border-0 rounded-4">
                <div class="card-header bg-white border-0 p-0">
                    <ul class="nav nav-tabs border-0" id="accountTabs" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link active px-4 py-3 fw-bold border-0" id="orders-tab" data-bs-toggle="tab" data-bs-target="#orders" type="button" role="tab" aria-controls="orders" aria-selected="true">
                                Orders
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link px-4 py-3 fw-bold border-0" id="images-tab" data-bs-toggle="tab" data-bs-target="#images" type="button" role="tab" aria-controls="images" aria-selected="false">
                                Images
                            </button>
                        </li>
                    </ul>
                </div>
                <div class="card-body p-0">
                    <div class="tab-content" id="accountTabsContent">
                        <!-- Orders Tab -->
                        <div class="tab-pane fade show active p-4" id="orders" role="tabpanel" aria-labelledby="orders-tab">
                            <div class="d-flex justify-content-between align-items-center mb-4">
                                <h5 class="mb-0">Order History</h5>
                                @if(!$business->open_order())
                                    <a href="{{ route('orders.new') }}" class="btn btn-primary">
                                        <i class="bi bi-plus-circle me-1"></i> Start New Order
                                    </a>
                                @else
                                    <a href="{{ route('orders.show', $business->open_order()->id) }}" class="btn btn-success">
                                        <i class="bi bi-cart-plus me-1"></i> Continue Open Order
                                    </a>
                                @endif
                            </div>

                            @if($orders->count() > 0)
                                <div class="table-responsive">
                                    <table class="table table-hover align-middle">
                                        <thead class="table-light">
                                            <tr>
                                                <th>Order #</th>
                                                <th>Date</th>
                                                <th>Status</th>
                                                <th class="text-center">Images</th>
                                                <th class="text-end">Total</th>
                                                <th class="text-end">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            @foreach($orders as $order)
                                                <tr>
                                                    <td>{{ $order->id }}</td>
                                                    <td>{{ $order->order_date->format('m/d/Y') }}</td>
                                                    <td>
                                                        <span class="badge" style="background-color: {{ $order->orderStatus->color ?? '#6c757d' }}">
                                                            {{ ucfirst($order->orderStatus->name ?? 'Unknown') }}
                                                        </span>
                                                    </td>
                                                    <td class="text-center">{{ $order->get_total_image_count() }}</td>
                                                    <td class="text-end fw-bold">
                                                        ${{ number_format($order->total_price + $order->sales_tax + $order->shipping_cost, 2) }}
                                                    </td>
                                                    <td class="text-end">
                                                        <a href="{{ route('orders.show', $order->id) }}" class="btn btn-sm btn-outline-dark">View</a>
                                                    </td>
                                                </tr>
                                            @endforeach
                                        </tbody>
                                    </table>
                                </div>
                            @else
                                <div class="text-center py-5">
                                    <i class="bi bi-receipt fs-1 text-muted opacity-25"></i>
                                    <p class="mt-3 text-muted">No orders found.</p>
                                </div>
                            @endif
                        </div>

                        <!-- Images Tab -->
                        <div class="tab-pane fade p-4" id="images" role="tabpanel" aria-labelledby="images-tab">
                            <h5 class="mb-4">My Images</h5>
                            @if($images->count() > 0)
                                <div class="row row-cols-2 row-cols-md-4 row-cols-lg-6 g-3">
                                    @foreach($images as $image)
                                        <div class="col">
                                            <div class="card h-100 shadow-sm border-0 rounded-3">
                                                <div class="checkerboard d-flex align-items-center justify-content-center p-2 rounded-top" style="height: 120px; background-color: #f8f9fa;">
                                                    <img src="{{ $image->image }}" class="img-fluid rounded" style="max-height: 100px;" alt="{{ $image->image_name }}">
                                                </div>
                                                <div class="card-body p-2">
                                                    <p class="small mb-0 text-truncate text-center" title="{{ $image->image_name }}">
                                                        {{ $image->image_name ?: 'Unnamed' }}
                                                    </p>
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
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <style>
        .checkerboard {
            background-image: linear-gradient(45deg, #e5e5e5 25%, transparent 25%),
                              linear-gradient(-45deg, #e5e5e5 25%, transparent 25%),
                              linear-gradient(45deg, transparent 75%, #e5e5e5 75%),
                              linear-gradient(-45deg, transparent 75%, #e5e5e5 75%);
            background-size: 20px 20px;
            background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
        }
        .nav-tabs .nav-link {
            color: #6c757d;
            border-bottom: 3px solid transparent !important;
        }
        .nav-tabs .nav-link.active {
            color: #000;
            background: transparent !important;
            border-bottom: 3px solid #ffc107 !important;
        }
    </style>
</x-app-layout>
