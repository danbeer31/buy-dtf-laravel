<?php

namespace App\Console\Commands;

use App\Services\Accounting\StripeQboReconciliationService;
use Illuminate\Console\Command;

class ReconcileStripeHolding extends Command
{
    protected $signature = 'accounting:reconcile-stripe-holding
        {--business_id= : Optional business filter for expected side calculation}
        {--date= : Optional as-of date (YYYY-MM-DD)}
        {--dry-run : Compute only, do not persist}';

    protected $description = 'Compute Stripe/QBO holding reconciliation snapshot (read-only).';

    public function handle(StripeQboReconciliationService $service): int
    {
        $businessId = $this->option('business_id');
        $asOfDate = $this->option('date');
        $dryRun = (bool) $this->option('dry-run');

        $result = $service->run([
            'business_id' => $businessId ? (int) $businessId : null,
            'as_of_date' => $asOfDate ?: null,
            'scope' => $asOfDate ? 'as_of' : 'current',
            'persist' => !$dryRun,
            'tolerance_cents' => 1,
        ]);

        $this->line('Stripe/QBO Holding Reconciliation');
        $this->line('--------------------------------');
        $this->line('Status: ' . $result['status']);
        $this->line('Expected (cents): ' . $result['expected_holding_amount_cents']);
        $this->line('Actual (cents):   ' . $result['actual_holding_amount_cents']);
        $this->line('Difference:       ' . $result['difference_amount_cents']);
        $this->line('Tolerance:        ' . $result['tolerance_cents']);
        $this->line('Scope:            ' . $result['scope']);
        $this->line('As Of:            ' . ($result['as_of_date'] ?? 'current'));
        $this->line('Persisted:        ' . ($dryRun ? 'no' : 'yes'));

        if (!empty($result['notes'])) {
            $this->warn('Notes: ' . $result['notes']);
        }

        if ($result['status'] === 'error') {
            return self::FAILURE;
        }

        return self::SUCCESS;
    }
}

