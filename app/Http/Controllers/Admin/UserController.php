<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\Business;
use App\Models\BusinessUser;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;

class UserController extends Controller
{
    public function index(Request $request)
    {
        $query = User::query();

        if ($request->filled('search')) {
            $search = $request->search;
            $query->where(function ($q) use ($search) {
                $q->where('name', 'like', "%{$search}%")
                  ->orWhere('email', 'like', "%{$search}%");
            });
        }

        if ($request->filled('role')) {
            $query->where('role', $request->role);
        }

        $users = $query->orderBy('created_at', 'desc')->paginate(15)->withQueryString();

        $userIds = $users->getCollection()->pluck('id');
        $userEmails = $users->getCollection()->pluck('email')->filter();

        $memberships = BusinessUser::query()
            ->whereIn('user_id', $userIds)
            ->where('is_active', true)
            ->get(['user_id', 'business_id', 'role']);

        $businessIds = $users->getCollection()->pluck('fuel_business_id')
            ->filter()
            ->merge($memberships->pluck('business_id'))
            ->unique()
            ->values();

        $businessesById = Business::query()
            ->whereIn('id', $businessIds)
            ->get(['id', 'business_name', 'email'])
            ->keyBy('id');

        $fallbackBusinessesByEmail = Business::query()
            ->whereIn('email', $userEmails)
            ->get(['id', 'business_name', 'email'])
            ->keyBy(fn (Business $business) => strtolower((string) $business->email));

        $userBusinessMap = [];
        foreach ($users as $user) {
            $primaryBusiness = null;

            if (!empty($user->fuel_business_id) && isset($businessesById[$user->fuel_business_id])) {
                $primaryBusiness = $businessesById[$user->fuel_business_id];
            } else {
                $emailKey = strtolower((string) $user->email);
                $primaryBusiness = $fallbackBusinessesByEmail[$emailKey] ?? null;
            }

            $memberBusinesses = $memberships
                ->where('user_id', $user->id)
                ->map(function ($membership) use ($businessesById) {
                    $business = $businessesById[$membership->business_id] ?? null;
                    if (!$business) {
                        return null;
                    }

                    return [
                        'id' => $business->id,
                        'business_name' => $business->business_name,
                        'role' => $membership->role,
                    ];
                })
                ->filter()
                ->values();

            $userBusinessMap[$user->id] = [
                'primary' => $primaryBusiness,
                'memberships' => $memberBusinesses,
            ];
        }

        return view('admin.users.index', compact('users', 'userBusinessMap'));
    }

    public function create()
    {
        $businesses = Business::query()
            ->orderBy('business_name')
            ->get(['id', 'business_name', 'email']);

        return view('admin.users.create', compact('businesses'));
    }

    public function store(Request $request)
    {
        $request->validate([
            'name' => 'required|string|max:255',
            'email' => 'required|string|email|max:255|unique:users',
            'password' => 'required|string|min:8|confirmed',
            'role' => ['required', Rule::in(['user', 'admin', 'superadmin'])],
            'business_id' => 'nullable|integer|min:1',
        ]);

        $businessId = $this->normalizeBusinessId($request->input('business_id'));
        $this->assertBusinessExists($businessId);

        $user = User::create([
            'name' => $request->name,
            'email' => $request->email,
            'password' => Hash::make($request->password),
            'role' => $request->role,
        ]);

        $this->syncUserBusiness($user, $businessId);

        return redirect()->route('admin.users.index')->with('success', 'User created successfully.');
    }

    public function edit(User $user)
    {
        $businesses = Business::query()
            ->orderBy('business_name')
            ->get(['id', 'business_name', 'email']);

        $selectedBusinessIds = BusinessUser::query()
            ->where('user_id', $user->id)
            ->where('is_active', true)
            ->pluck('business_id')
            ->map(fn ($id) => (int) $id)
            ->values()
            ->all();

        $selectedBusinessId = $selectedBusinessIds[0] ?? (!empty($user->fuel_business_id) ? (int) $user->fuel_business_id : null);

        return view('admin.users.edit', compact('user', 'businesses', 'selectedBusinessId'));
    }

    public function update(Request $request, User $user)
    {
        $request->validate([
            'name' => 'required|string|max:255',
            'email' => ['required', 'string', 'email', 'max:255', Rule::unique('users')->ignore($user->id)],
            'role' => ['required', Rule::in(['user', 'admin', 'superadmin'])],
            'password' => 'nullable|string|min:8|confirmed',
            'business_id' => 'nullable|integer|min:1',
        ]);

        $businessId = $this->normalizeBusinessId($request->input('business_id'));
        $this->assertBusinessExists($businessId);

        $user->name = $request->name;
        $user->email = $request->email;
        $user->role = $request->role;

        if ($request->filled('password')) {
            $user->password = Hash::make($request->password);
        }

        $user->save();
        $this->syncUserBusiness($user, $businessId);

        return redirect()->route('admin.users.index')->with('success', 'User updated successfully.');
    }

    public function destroy(User $user)
    {
        if ($user->id === auth()->id()) {
            return back()->with('error', 'You cannot delete yourself.');
        }

        $user->delete();

        return redirect()->route('admin.users.index')->with('success', 'User deleted successfully.');
    }

    private function normalizeBusinessId(mixed $businessId): ?int
    {
        $normalized = (int) $businessId;
        return $normalized > 0 ? $normalized : null;
    }

    private function assertBusinessExists(?int $businessId): void
    {
        if (!$businessId) {
            return;
        }

        $exists = Business::query()->whereKey($businessId)->exists();
        if (!$exists) {
            throw ValidationException::withMessages([
                'business_id' => 'Selected business is invalid.',
            ]);
        }
    }

    private function syncUserBusiness(User $user, ?int $businessId): void
    {
        if (!$businessId) {
            BusinessUser::query()
                ->where('user_id', $user->id)
                ->update(['is_active' => false]);

            $user->forceFill(['fuel_business_id' => null])->saveQuietly();
            return;
        }

        BusinessUser::query()
            ->where('user_id', $user->id)
            ->where('business_id', '!=', $businessId)
            ->update(['is_active' => false]);

        $membership = BusinessUser::query()->firstOrNew([
            'business_id' => $businessId,
            'user_id' => $user->id,
        ]);

        if (!$membership->exists) {
            $membership->role = 'member';
        }

        $membership->is_active = true;
        $membership->save();

        $user->forceFill(['fuel_business_id' => $businessId])->saveQuietly();
    }
}
