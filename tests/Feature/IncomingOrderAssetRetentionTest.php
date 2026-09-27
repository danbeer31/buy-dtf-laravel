<?php

namespace Tests\Feature;

use App\Models\ApiAssetRecord;
use App\Models\IncomingOrderJob;
use Illuminate\Support\Facades\Artisan;
use Tests\TestCase;

class IncomingOrderAssetRetentionTest extends TestCase
{
    /** @var list<string> */
    private array $files = [];

    protected function tearDown(): void
    {
        foreach ($this->files as $file) {
            if (is_file($file)) {
                unlink($file);
            }
        }

        parent::tearDown();
    }

    public function test_retention_report_selects_only_explicit_future_api_records_and_never_deletes(): void
    {
        $job = $this->incomingJob();
        $legacyFile = $this->publicFixture('retention-legacy.png');
        $candidateFile = $this->publicFixture('retention-api-candidate.png');

        ApiAssetRecord::create([
            'incoming_order_job_id' => $job->id,
            'origin' => 'incoming_order_v1',
            'asset_role' => 'original',
            'storage_scope' => 'public_root',
            'asset_path' => '/uploads/images/retention-api-candidate.png',
            'path_hash' => hash('sha256', '/uploads/images/retention-api-candidate.png'),
            'sha256' => hash_file('sha256', $candidateFile),
            'bytes' => filesize($candidateFile),
            'retention_policy' => 'expirable',
            'retention_enabled' => true,
            'retention_days' => 30,
            'expires_at' => now()->subDay(),
        ]);
        ApiAssetRecord::create([
            'incoming_order_job_id' => $job->id,
            'origin' => 'incoming_order_v1',
            'asset_role' => 'job_card',
            'storage_scope' => 'public_root',
            'asset_path' => '/uploads/images/retention-legacy.png',
            'path_hash' => hash('sha256', '/uploads/images/retention-legacy.png'),
            'sha256' => hash_file('sha256', $legacyFile),
            'bytes' => filesize($legacyFile),
            'retention_policy' => 'forever',
            'retention_enabled' => false,
        ]);

        $this->assertSame(0, Artisan::call('incoming-orders:retention-report', ['--json' => true]));
        $output = Artisan::output();
        $this->assertStringContainsString('"mode": "report_only"', $output);
        $this->assertStringContainsString('"candidate_rows": 1', $output);
        $this->assertStringContainsString('retention-api-candidate.png', $output);

        $this->assertFileExists($candidateFile);
        $this->assertFileExists($legacyFile);
        $this->assertDatabaseCount('api_asset_records', 2, 'fuelmysql');
    }

    private function incomingJob(): IncomingOrderJob
    {
        return IncomingOrderJob::create([
            'integration_client' => 'shopnltees',
            'idempotency_key' => 'retention-test-key',
            'request_fingerprint' => str_repeat('a', 64),
            'expected_art_sha256' => str_repeat('b', 64),
            'state' => 'completed',
            'attempt_count' => 1,
            'art_width_in' => '1.0000',
            'art_height_in' => '1.0000',
        ]);
    }

    private function publicFixture(string $name): string
    {
        $path = public_path('uploads/images/'.$name);
        if (! is_dir(dirname($path))) {
            mkdir(dirname($path), 0777, true);
        }
        file_put_contents($path, 'retention-fixture-'.$name);
        $this->files[] = $path;

        return $path;
    }
}
