<?php

namespace Tests\Unit;

use App\Services\QboService;
use Tests\TestCase;

class QboServiceInvoiceBalanceTest extends TestCase
{
    public function test_unpaid_taxable_invoice_uses_total_amount_when_balance_excludes_tax(): void
    {
        $service = new QboService();

        $this->assertSame(107.0, $service->getInvoicePayableBalance([
            'Balance' => 100,
            'TotalAmt' => 107,
            'TxnTaxDetail' => [
                'TotalTax' => 7,
            ],
        ]));
    }

    public function test_partially_paid_invoice_uses_remaining_balance(): void
    {
        $service = new QboService();

        $this->assertSame(7.0, $service->getInvoicePayableBalance([
            'Balance' => 7,
            'TotalAmt' => 107,
            'LinkedTxn' => [
                [
                    'TxnId' => '123',
                    'TxnType' => 'Payment',
                ],
            ],
        ]));
    }

    public function test_balance_difference_must_match_tax_to_use_total_amount(): void
    {
        $service = new QboService();

        $this->assertSame(57.0, $service->getInvoicePayableBalance([
            'Balance' => 57,
            'TotalAmt' => 107,
            'TxnTaxDetail' => [
                'TotalTax' => 7,
            ],
        ]));
    }

    public function test_paid_invoice_returns_zero(): void
    {
        $service = new QboService();

        $this->assertSame(0.0, $service->getInvoicePayableBalance([
            'Balance' => 0,
            'TotalAmt' => 107,
        ]));
    }
}
