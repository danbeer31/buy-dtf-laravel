<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\AccountingReconciliationCheck;
use App\Models\Business;
use App\Models\DtfOrder;
use App\Services\QboService;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Carbon\Carbon;

class DashboardController extends Controller
{
    public function index(QboService $qbo)
    {
        $salesTimezone = (string) config('app.timezone', 'America/Chicago');
        $now = Carbon::now($salesTimezone);
        $today = $now->copy()->startOfDay();
        $lastYearStart = $today->copy()->subYear()->startOfYear();
        $lastYearEnd = $today->copy()->subYear()->endOfYear();

        // Weekly Sales (last 7 days)
        $weeklySales = DtfOrder::where('status', '!=', 1) // Exclude open orders
            ->where('order_date', '>=', Carbon::now()->subDays(6)->startOfDay())
            ->select(
                DB::raw('DATE(order_date) as date'),
                DB::raw('SUM(total_price) as total')
            )
            ->groupBy('date')
            ->orderBy('date')
            ->get()
            ->pluck('total', 'date')
            ->toArray();

        // Fill in missing days for weekly
        $weeklyData = [];
        for ($i = 6; $i >= 0; $i--) {
            $date = Carbon::now()->subDays($i)->format('Y-m-d');
            $weeklyData[$date] = $weeklySales[$date] ?? 0;
        }

        // Monthly Sales (Current Month)
        $monthlySales = DtfOrder::where('status', '!=', 1)
            ->where('order_date', '>=', Carbon::now()->startOfMonth())
            ->select(
                DB::raw('DATE(order_date) as date'),
                DB::raw('SUM(total_price) as total')
            )
            ->groupBy('date')
            ->orderBy('date')
            ->get()
            ->pluck('total', 'date')
            ->toArray();

        $monthlyData = [];
        $daysInMonth = Carbon::now()->daysInMonth;
        for ($i = 1; $i <= $daysInMonth; $i++) {
            $date = Carbon::now()->startOfMonth()->addDays($i - 1)->format('Y-m-d');
            $monthlyData[$date] = $monthlySales[$date] ?? 0;
        }

        // Yearly Sales (Current Year)
        $yearlySales = DtfOrder::where('status', '!=', 1)
            ->where('order_date', '>=', Carbon::now()->startOfYear())
            ->select(
                DB::raw('MONTH(order_date) as month'),
                DB::raw('SUM(total_price) as total')
            )
            ->groupBy('month')
            ->orderBy('month')
            ->get()
            ->pluck('total', 'month')
            ->toArray();

        $yearlyData = [];
        for ($i = 1; $i <= 12; $i++) {
            $yearlyData[date('F', mktime(0, 0, 0, $i, 1))] = $yearlySales[$i] ?? 0;
        }

        // Quick View Stats
        $stats = [
            'waiting_production' => DtfOrder::where('status', 2)->count(),
            'in_production' => DtfOrder::where('status', 3)->count(),
            'pickup_ready' => DtfOrder::where('status', 5)->count(),
            'shipped' => DtfOrder::where('status', 4)->count(),
            'in_transit' => DtfOrder::where('status', 11)->count(),
            'out_for_delivery' => DtfOrder::where('status', 12)->count(),
        ];

        $latestCheckIds = AccountingReconciliationCheck::select(DB::raw('MAX(id) as id'))
            ->where('provider', 'stripe')
            ->groupBy('business_id')
            ->pluck('id')
            ->filter()
            ->all();

        $latestChecks = empty($latestCheckIds)
            ? collect()
            : AccountingReconciliationCheck::whereIn('id', $latestCheckIds)->get();

        $reconSummary = [
            'balanced' => $latestChecks->where('status', 'balanced')->count(),
            'mismatch' => $latestChecks->where('status', 'mismatch')->count(),
            'error' => $latestChecks->where('status', 'error')->count(),
            'total' => $latestChecks->count(),
        ];

        $salesSummary = [
            'today' => (float) DtfOrder::where('status', '!=', 1)
                ->whereDate('order_date', $today)
                ->sum('total_price'),
            'last_year_total' => (float) DtfOrder::where('status', '!=', 1)
                ->whereBetween('order_date', [$lastYearStart->toDateString(), $lastYearEnd->toDateString()])
                ->sum('total_price'),
            'today_date' => $today->toDateString(),
            'last_year_label' => $lastYearStart->format('Y'),
            'sales_timezone' => $salesTimezone,
            'same_month_last_year' => (float) DtfOrder::where('status', '!=', 1)
                ->whereBetween('order_date', [
                    $now->copy()->subYear()->startOfMonth()->toDateString(),
                    $now->copy()->subYear()->endOfMonth()->toDateString(),
                ])
                ->sum('total_price'),
            'weekly_last_year_same_window' => (float) DtfOrder::where('status', '!=', 1)
                ->whereBetween('order_date', [
                    $today->copy()->subYear()->subDays(6)->toDateString(),
                    $today->copy()->subYear()->toDateString(),
                ])
                ->sum('total_price'),
            'year_to_date_last_year' => (float) DtfOrder::where('status', '!=', 1)
                ->whereBetween('order_date', [
                    $now->copy()->subYear()->startOfYear()->toDateString(),
                    $now->copy()->subYear()->toDateString(),
                ])
                ->sum('total_price'),
            'weekly_last_year_label_start' => $today->copy()->subYear()->subDays(6)->toDateString(),
            'weekly_last_year_label_end' => $today->copy()->subYear()->toDateString(),
            'same_month_last_year_label' => $now->copy()->subYear()->format('F Y'),
            'year_to_date_last_year_label' => $now->copy()->subYear()->toDateString(),
        ];

        $businessesWhoOwe = [];
        $totalOwed = 0.0;
        $owedBusinessesCount = 0;

        $businesses = Business::query()
            ->select(['id', 'business_name', 'qbo_customer_id'])
            ->whereNotNull('qbo_customer_id')
            ->where('qbo_customer_id', '!=', '')
            ->orderBy('business_name')
            ->get();

        foreach ($businesses as $business) {
            $cacheKey = 'qbo_data_' . $business->id;
            $qboData = Cache::get($cacheKey);

            if (!is_array($qboData) || !array_key_exists('balance', $qboData)) {
                try {
                    $qboData = [
                        'balance' => $qbo->getCustomerBalance($business->qbo_customer_id),
                    ];
                    Cache::put($cacheKey, $qboData, 600);
                } catch (\Throwable $e) {
                    Log::warning("Admin dashboard: failed to fetch QBO balance for business {$business->id}: " . $e->getMessage());
                    continue;
                }
            }

            $balance = (float) ($qboData['balance'] ?? 0);
            if ($balance > 0) {
                $owedBusinessesCount++;
                $totalOwed += $balance;
                $businessesWhoOwe[] = [
                    'id' => (int) $business->id,
                    'business_name' => (string) ($business->business_name ?: ('Business #' . $business->id)),
                    'balance' => $balance,
                ];
            }
        }

        usort($businessesWhoOwe, fn (array $a, array $b) => $b['balance'] <=> $a['balance']);

        return view('admin.dashboard', compact(
            'weeklyData',
            'monthlyData',
            'yearlyData',
            'stats',
            'reconSummary',
            'salesSummary',
            'businessesWhoOwe',
            'owedBusinessesCount',
            'totalOwed'
        ));
    }
}
