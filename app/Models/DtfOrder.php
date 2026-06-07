<?php

namespace App\Models;

use App\Mail\AdminNewOrderPlaced;
use App\Mail\OrderInProduction;
use App\Mail\OrderPlaced;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;
use Exception;

class DtfOrder extends FuelModel
{
    protected $table = 'dtforders';

    protected $fillable = [
        'business_id',
        'order_date',
        'shipping_method_id',
        'shipping_method',
        'payment_method_id',
        'paymentmethod',
        'weight',
        'price',
        'shipping_cost',
        'total_price',
        'sales_tax',
        'admin_discount_pct',
        'admin_discount_locked',
        'square_inches',
        'linear_inches',
        'status',
        'qbo_invoice_id',
        'qbo_invoice_number',
        'shippo_service_name',
        'shippo_transaction_id',
        'tracking_number',
        'label_url',
    ];

    /**
     * The attributes that should be cast.
     *
     * @var array<string, string>
     */
    protected $casts = [
        'weight' => 'float',
        'price' => 'float',
        'shipping_cost' => 'float',
        'total_price' => 'float',
        'sales_tax' => 'float',
        'admin_discount_pct' => 'float',
        'admin_discount_locked' => 'integer',
        'square_inches' => 'float',
        'linear_inches' => 'float',
    ];

    // FuelPHP model used UNIX timestamps (mysql_timestamp => false)
    public $timestamps = true;
    protected $dateFormat = 'U';

    protected static function booted(): void
    {
        static::updated(function (self $order) {
            if (!$order->wasChanged('status')) {
                return;
            }

            $previousStatus = (int) $order->getOriginal('status');
            $newStatus = (int) $order->status;

            if ($previousStatus === $newStatus) {
                return;
            }

            try {
                $order->sendStatusNotifications($newStatus);
            } catch (\Throwable $e) {
                Log::error('Failed to send status notification emails', [
                    'order_id' => $order->id,
                    'from_status' => $previousStatus,
                    'to_status' => $newStatus,
                    'error' => $e->getMessage(),
                ]);
            }
        });
    }

    public function setOrderDateAttribute($value)
    {
        $this->attributes['order_date'] = $value instanceof \DateTimeInterface
            ? $value->format('Y-m-d')
            : $value;
    }

    public function getOrderDateAttribute($value)
    {
        return $value ? \Illuminate\Support\Carbon::parse($value) : null;
    }

    public function business(): BelongsTo
    {
        return $this->belongsTo(Business::class);
    }

    public function dtfImages(): HasMany
    {
        return $this->hasMany(DtfImage::class, 'dtforder_id');
    }

    public function shippingMethod(): BelongsTo
    {
        return $this->belongsTo(ShippingMethod::class, 'shipping_method_id');
    }

    public function paymentMethod(): BelongsTo
    {
        return $this->belongsTo(PaymentMethod::class, 'payment_method_id');
    }

    public function paymentInfo(): HasOne
    {
        // Some orders can accumulate multiple payment rows (retries/updates).
        // Always treat the newest row as the authoritative payment state.
        return $this->hasOne(PaymentInfo::class, 'dtforder_id')->latestOfMany('id');
    }

    public function shippingAddress(): HasOne
    {
        return $this->hasOne(ShippingAddress::class, 'order_id');
    }

    public function orderStatus(): BelongsTo
    {
        return $this->belongsTo(OrderStatus::class, 'status');
    }

    public function get_total()
    {
        if ($this->dtfImages->isEmpty()) {
            return 0;
        }

        $total = 0;
        foreach ($this->dtfImages as $image) {
            $total += $image->get_total();
        }

        return round($total, 2);
    }

    public function get_invoice_total()
    {
        if ($this->dtfImages->isEmpty()) {
            return 0;
        }

        $total = 0;
        foreach ($this->dtfImages as $image) {
            $total += $image->get_total();
        }
        $total += $this->shipping_cost;

        return round($total, 2);
    }

    public function get_image_count()
    {
        return $this->dtfImages->count();
    }

    public function get_total_image_count()
    {
        return $this->dtfImages->sum('quantity');
    }

    public function calculate_weight($film_weight = 0.0003, $core_weight = 1.8)
    {
        $area = $this->calculate_area();
        if ($area === false) {
            return false;
        }

        $total_square_inches = $area['square_inches'];
        return ($total_square_inches * $film_weight) + $core_weight;
    }

    public function calculate_area($width = 22)
    {
        if ($this->dtfImages->isEmpty()) {
            return false;
        }

        $total_square_inches = 0;
        foreach ($this->dtfImages as $img) {
            $total_square_inches += $img->get_square_inches() * $img->quantity;
        }

        $result = [];
        $result['width'] = (float)$width;
        $result['square_inches'] = (float)$total_square_inches;
        $result['length'] = $result['square_inches'] / $result['width'];

        // Add 2 inches to length for margins/spacing as per legacy logic (optional but common in this project)
        $result['linear_inches'] = $result['length'] + 2;

        return $result;
    }

    /**
     * Finalize and save order metrics (weight, inches, methods) before moving to production/payment.
     */
    public function finalizeMetrics()
    {
        $area = $this->calculate_area();
        $weight = $this->calculate_weight();

        $updateData = [
            'weight' => $weight ?: 1.8,
            'square_inches' => $area ? $area['square_inches'] : 0,
            'linear_inches' => $area ? $area['linear_inches'] : 0,
        ];

        // Ensure we have the latest relations
        $this->load(['paymentMethod', 'shippingMethod']);

        $columns = \Illuminate\Support\Facades\Schema::connection($this->getConnectionName())->getColumnListing('dtforders');

        if ($this->paymentMethod && in_array('paymentmethod', $columns)) {
            $updateData['paymentmethod'] = $this->paymentMethod->method_name;
        }

        if (in_array('shipping_method', $columns)) {
            if ($this->shippingMethod) {
                $updateData['shipping_method'] = $this->shippingMethod->shipping_method;
            } elseif ($this->shipping_method) {
                // Already set as string in startPayment (e.g. for Shippo rates)
                $updateData['shipping_method'] = $this->shipping_method;
            }
        }

        // Populate shippo columns if they exist
        if (in_array('shippo_service_name', $columns)) {
            if ($this->shippo_service_name) {
                 $updateData['shippo_service_name'] = $this->shippo_service_name;
            } elseif ($this->shipping_method) {
                 $updateData['shippo_service_name'] = $this->shipping_method;
            }
        }

        $this->update($updateData);
    }

    /**
     * Check if all images in this order are in production.
     * If they are, we can log it or perform other checks, but we no longer
     * automatically transition the order status to "Ready to Ship" or "Pickup Ready".
     */
    public function checkProductionStatus()
    {
        $this->loadMissing('dtfImages');

        if ($this->dtfImages->isEmpty()) {
            return;
        }

        $allInProduction = $this->dtfImages->every('production', 1);

        if ($allInProduction) {
            \Illuminate\Support\Facades\Log::info("Order #{$this->id} - All images are now in production.");
        }
    }

    public function isPaid()
    {
        $payment = $this->paymentInfo;
        if ($payment) {
            if (!empty($payment->qbo_payment_id)) {
                return true;
            }

            $paymentStatus = strtolower((string)($payment->status ?? ''));
            if (in_array($paymentStatus, ['complete', 'paid'], true)) {
                return true;
            }
        }

        // Open/draft orders are never considered paid.
        if ((int)$this->status === 1) {
            return false;
        }

        // If QuickBooks generated a zero-dollar invoice, treat it as paid.
        if ((float)($this->total_price ?? 0) <= 0 && !empty($this->qbo_invoice_id)) {
            return true;
        }

        return false;
    }

    public function scopePaid($query)
    {
        return $query->where(function ($q) {
            $q->whereHas('paymentInfo', function ($paymentQuery) {
                    $paymentQuery->whereNotNull('qbo_payment_id')
                        ->orWhereIn('status', ['complete', 'paid']);
                })
                ->orWhere(function ($zeroInvoiceQuery) {
                    $zeroInvoiceQuery
                        ->where('status', '!=', 1)
                        ->where('total_price', '<=', 0)
                        ->whereNotNull('qbo_invoice_id');
                });
        });
    }

    public function scopeUnpaid($query)
    {
        return $query->where(function ($q) {
            // Open/draft orders are unpaid.
            $q->where('status', 1)
                // Or not matching paid criteria.
                ->orWhere(function ($notPaidQuery) {
                    $notPaidQuery->whereDoesntHave('paymentInfo', function ($paymentQuery) {
                        $paymentQuery->whereNotNull('qbo_payment_id')
                            ->orWhereIn('status', ['complete', 'paid']);
                    })->where(function ($invoiceQuery) {
                        $invoiceQuery
                            ->where('total_price', '>', 0)
                            ->orWhereNull('qbo_invoice_id')
                            ->orWhere('status', 1);
                    });
                });
        });
    }

    public function stripePayoutEntries(): HasMany
    {
        return $this->hasMany(StripePayoutEntry::class, 'dtforder_id');
    }

    private function sendStatusNotifications(int $newStatus): void
    {
        $this->loadMissing('business');

        if ($newStatus === 2) {
            $this->sendCustomerOrderPlacedEmail();
            $this->sendAdminNewOrderPlacedEmail();
            return;
        }

        if ($newStatus === 3) {
            $this->sendCustomerInProductionEmail();
        }
    }

    private function sendCustomerOrderPlacedEmail(): void
    {
        $customerEmail = trim((string) optional($this->business)->email);
        if ($customerEmail === '') {
            return;
        }

        Mail::to($customerEmail)->send(new OrderPlaced($this));
    }

    private function sendCustomerInProductionEmail(): void
    {
        $customerEmail = trim((string) optional($this->business)->email);
        if ($customerEmail === '') {
            return;
        }

        Mail::to($customerEmail)->send(new OrderInProduction($this));
    }

    private function sendAdminNewOrderPlacedEmail(): void
    {
        $adminEmail = trim((string) Setting::get(
            'admin_order_notification_email',
            env('ADMIN_ORDER_NOTIFICATION_EMAIL', 'danielbeerwart@nlcustomtees.com')
        ));
        if ($adminEmail === '') {
            return;
        }

        Mail::to($adminEmail)->send(new AdminNewOrderPlaced($this));
    }
}
