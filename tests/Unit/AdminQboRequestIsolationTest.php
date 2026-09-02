<?php

namespace Tests\Unit;

use App\Http\Controllers\Admin\DashboardController;
use App\Http\Controllers\Admin\OrderController;
use App\Services\QboAdminSnapshotStore;
use Illuminate\Http\Request;
use PHPUnit\Framework\TestCase;
use ReflectionMethod;

class AdminQboRequestIsolationTest extends TestCase
{
    public function test_admin_controllers_only_depend_on_cached_qbo_snapshots(): void
    {
        $dashboardParameters = (new ReflectionMethod(DashboardController::class, 'index'))->getParameters();
        $orderParameters = (new ReflectionMethod(OrderController::class, 'index'))->getParameters();

        $this->assertSame(
            [QboAdminSnapshotStore::class],
            array_map(fn ($parameter) => $parameter->getType()->getName(), $dashboardParameters),
        );
        $this->assertSame(
            [Request::class, QboAdminSnapshotStore::class],
            array_map(fn ($parameter) => $parameter->getType()->getName(), $orderParameters),
        );
    }
}
