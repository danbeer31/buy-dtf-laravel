<?php

namespace Tests\Feature\Production;

use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\User;
use Tests\TestCase;

class PricingAndHandoffTest extends TestCase
{
    public function test_gang_sheet_price_uses_the_quantity_tier_and_is_persisted(): void
    {
        $order = $this->createOrder();
        $image = DtfImage::create([
            'dtforder_id' => $order->id,
            'item_type' => 'gang_sheet',
            'item_meta' => ['size_key' => '22x96'],
            'quantity' => 6,
            'price' => 0,
            'production' => 0,
        ]);

        $this->assertSame(50.0, $image->get_price());
        $this->assertSame(50.0, (float) $image->fresh()->price);
    }

    public function test_locked_admin_price_overrides_calculated_pricing(): void
    {
        $order = $this->createOrder();
        $image = DtfImage::create([
            'dtforder_id' => $order->id,
            'item_type' => 'gang_sheet',
            'item_meta' => ['size_key' => '22x96'],
            'quantity' => 10,
            'price' => 0,
            'admin_price_locked' => 1,
            'admin_unit_price' => 44.129,
            'production' => 0,
        ]);

        $this->assertSame(44.13, $image->get_price());
    }

    public function test_gang_sheet_cannot_enter_the_automated_production_handoff(): void
    {
        $admin = User::factory()->create(['role' => 'admin']);
        $order = $this->createOrder();
        $image = DtfImage::create([
            'dtforder_id' => $order->id,
            'item_type' => 'gang_sheet',
            'item_meta' => ['size_key' => '22x48'],
            'quantity' => 1,
            'price' => 29,
            'production' => 0,
        ]);

        $this->actingAs($admin)
            ->postJson(route('admin.orders.add-to-production'), ['image_id' => $image->id])
            ->assertStatus(422)
            ->assertJsonPath('status', 'error');

        $this->assertSame(0, (int) $image->fresh()->production);
    }

    private function createOrder(): DtfOrder
    {
        return DtfOrder::create([
            'order_date' => now(),
            'status' => 1,
        ]);
    }
}
