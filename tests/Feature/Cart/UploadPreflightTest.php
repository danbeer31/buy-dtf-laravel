<?php

namespace Tests\Feature\Cart;

use App\Models\Business;
use App\Models\User;
use Tests\TestCase;

class UploadPreflightTest extends TestCase
{
    public function test_supported_upload_metadata_is_accepted_and_scoped_to_the_users_business(): void
    {
        [$user, $business] = $this->customerWithBusiness();

        $response = $this->actingAs($user)->postJson(route('cart.preflight'), [
            'name' => 'gang-sheet.png',
            'size' => 1024,
            'mime' => 'image/png',
        ]);

        $response
            ->assertOk()
            ->assertJsonPath('success', true)
            ->assertJsonPath('max_size_mb', 50)
            ->assertJsonPath('use_chunked', false);

        $uploadId = $response->json('upload_id');

        $this->assertNotEmpty($uploadId);
        $this->assertSame(
            $business->id,
            session("uploader_pending.{$uploadId}.business")
        );
    }

    public function test_upload_metadata_rejects_unsupported_file_types(): void
    {
        [$user] = $this->customerWithBusiness();

        $this->actingAs($user)->postJson(route('cart.preflight'), [
            'name' => 'payload.exe',
            'size' => 1024,
            'mime' => 'application/octet-stream',
        ])->assertStatus(415)->assertJsonPath('success', false);
    }

    public function test_upload_metadata_rejects_files_over_fifty_megabytes(): void
    {
        [$user] = $this->customerWithBusiness();

        $this->actingAs($user)->postJson(route('cart.preflight'), [
            'name' => 'oversized.pdf',
            'size' => (50 * 1024 * 1024) + 1,
            'mime' => 'application/pdf',
        ])->assertStatus(413)->assertJsonPath('success', false);
    }

    public function test_upload_metadata_requires_name_size_and_mime(): void
    {
        [$user] = $this->customerWithBusiness();

        $this->actingAs($user)->postJson(route('cart.preflight'), [])
            ->assertStatus(422)
            ->assertJsonPath('success', false);
    }

    /** @return array{User, Business} */
    private function customerWithBusiness(): array
    {
        $business = Business::create([
            'business_name' => 'Test Transfers',
            'contact_name' => 'Test Customer',
            'email' => 'customer@example.test',
            'status' => 1,
        ]);

        $user = User::factory()->create([
            'email' => 'customer@example.test',
            'role' => 'customer',
            'fuel_business_id' => $business->id,
        ]);

        return [$user, $business];
    }
}
