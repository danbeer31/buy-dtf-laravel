<?php

namespace App\Services;

use Carbon\CarbonInterface;

class QboAdminSnapshotBuilder
{
    private const INVOICES_PER_BUSINESS = 20;

    public function build(iterable $businesses, array $openInvoices, array $invoices, CarbonInterface $refreshedAt): array
    {
        $openInvoicesByCustomer = $this->groupInvoicesByCustomer($openInvoices);
        $invoicesByCustomer = $this->groupInvoicesByCustomer($invoices);
        $snapshots = [];

        foreach ($businesses as $business) {
            $businessId = (int) data_get($business, 'id');
            $customerId = (string) data_get($business, 'qbo_customer_id');
            if ($businessId <= 0 || $customerId === '') {
                continue;
            }

            $customerOpenInvoices = $openInvoicesByCustomer[$customerId] ?? [];
            $snapshots[$businessId] = [
                'business_id' => $businessId,
                'qbo_customer_id' => $customerId,
                'balance' => $this->sumPayableBalances($customerOpenInvoices),
                'balance_basis' => 'open_invoices',
                'open_invoice_count' => count($customerOpenInvoices),
                'invoices' => array_slice($invoicesByCustomer[$customerId] ?? [], 0, self::INVOICES_PER_BUSINESS),
                'refreshed_at' => $refreshedAt->toIso8601String(),
                'source' => 'background_refresh',
            ];
        }

        return $snapshots;
    }

    private function groupInvoicesByCustomer(array $invoices): array
    {
        $grouped = [];

        foreach ($invoices as $invoice) {
            if (! is_array($invoice)) {
                continue;
            }

            $customerRef = $invoice['CustomerRef'] ?? null;
            $customerId = is_array($customerRef)
                ? (string) ($customerRef['value'] ?? '')
                : (string) $customerRef;

            if ($customerId !== '') {
                $grouped[$customerId][] = $invoice;
            }
        }

        return $grouped;
    }

    private function sumPayableBalances(array $invoices): float
    {
        $total = 0.0;

        foreach ($invoices as $invoice) {
            if (! is_array($invoice)) {
                continue;
            }

            $total += max(0, (float) ($invoice['PayableBalance'] ?? $invoice['Balance'] ?? 0));
        }

        return round($total, 2);
    }
}
