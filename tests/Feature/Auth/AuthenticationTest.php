<?php

namespace Tests\Feature\Auth;

use App\Models\User;
use Illuminate\Support\Facades\Auth;
use Tests\TestCase;

class AuthenticationTest extends TestCase
{
    public function test_login_screen_can_be_rendered(): void
    {
        $response = $this->get('/login');

        $response->assertStatus(200);
    }

    public function test_users_can_authenticate_using_the_login_screen(): void
    {
        $user = User::factory()->create();

        $response = $this->post('/login', [
            'email' => $user->email,
            'password' => 'password',
        ]);

        $this->assertAuthenticated();
        $response->assertRedirect(route('dashboard', absolute: false));
    }

    public function test_users_can_not_authenticate_with_invalid_password(): void
    {
        $user = User::factory()->create();

        $this->post('/login', [
            'email' => $user->email,
            'password' => 'wrong-password',
        ]);

        $this->assertGuest();
    }

    public function test_users_can_logout(): void
    {
        $user = User::factory()->create();

        $response = $this->actingAs($user)->post('/logout');

        $this->assertGuest();
        $response->assertRedirect('/');
    }

    public function test_stale_remember_cookie_for_a_missing_user_falls_through_as_a_guest(): void
    {
        $user = User::factory()->create([
            'remember_token' => 'remember-token-that-will-become-stale',
        ]);
        $guard = Auth::guard('web');

        $recaller = implode('|', [
            $user->getAuthIdentifier(),
            $user->getRememberToken(),
            $guard->hashPasswordForCookie($user->getAuthPassword()),
        ]);

        $user->delete();

        $response = $this
            ->withCookie($guard->getRecallerName(), $recaller)
            ->get('/');

        $response->assertOk();
        $response->assertViewIs('home');
        $this->assertGuest('web');
        $this->assertFalse($guard->viaRemember());
    }

    public function test_valid_remember_cookie_authenticates_the_matching_user(): void
    {
        $user = User::factory()->create([
            'remember_token' => 'valid-remember-token',
        ]);
        $guard = Auth::guard('web');

        $recaller = implode('|', [
            $user->getAuthIdentifier(),
            $user->getRememberToken(),
            $guard->hashPasswordForCookie($user->getAuthPassword()),
        ]);

        $response = $this
            ->withCookie($guard->getRecallerName(), $recaller)
            ->get('/');

        $response->assertOk();
        $response->assertViewIs('home');
        $this->assertAuthenticatedAs($user, 'web');
        $this->assertTrue($guard->viaRemember());
    }
}
