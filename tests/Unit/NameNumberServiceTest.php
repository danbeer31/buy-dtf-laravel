<?php

namespace Tests\Unit;

use App\Services\NameNumberService;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class NameNumberServiceTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        config([
            'services.namenumber.url' => 'https://renderer.test',
            'services.namenumber.token' => 'test-token',
        ]);
    }

    public function test_render_retries_a_transient_server_failure(): void
    {
        Http::fakeSequence()
            ->push(['success' => false], 503)
            ->push(['success' => true, 'format' => 'json'], 200);

        $result = (new NameNumberService())->renderTemplateRemote(
            'classic',
            'Test',
            '12',
        );

        $this->assertTrue($result['success']);
        Http::assertSentCount(2);
    }

    public function test_render_does_not_retry_a_validation_failure(): void
    {
        Http::fake([
            '*' => Http::response(['message' => 'Invalid template'], 422),
        ]);

        $result = (new NameNumberService())->renderTemplateRemote(
            'missing',
            'Test',
            '12',
        );

        $this->assertFalse($result['success']);
        $this->assertStringContainsString('Renderer error', $result['message']);
        Http::assertSentCount(1);
    }
}
