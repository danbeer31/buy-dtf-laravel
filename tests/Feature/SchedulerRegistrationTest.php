<?php

namespace Tests\Feature;

use Illuminate\Console\Scheduling\Event;
use Illuminate\Console\Scheduling\Schedule;
use Tests\TestCase;

class SchedulerRegistrationTest extends TestCase
{
    public function test_payout_and_reconciliation_commands_have_expected_frequencies(): void
    {
        $events = collect($this->app->make(Schedule::class)->events());

        $payoutEvents = $events->filter(
            fn (Event $event): bool => str_contains((string) $event->command, 'stripe:sync-payouts')
        );
        $reconciliationEvents = $events->filter(
            fn (Event $event): bool => str_contains((string) $event->command, 'accounting:reconcile-stripe-holding')
        );

        $this->assertCount(1, $payoutEvents);
        $this->assertSame('0 * * * *', $payoutEvents->first()->expression);
        $this->assertSame('America/Chicago', $payoutEvents->first()->timezone);

        $this->assertCount(1, $reconciliationEvents);
        $this->assertSame('30 1 * * *', $reconciliationEvents->first()->expression);
        $this->assertSame('America/Chicago', $reconciliationEvents->first()->timezone);
    }
}
