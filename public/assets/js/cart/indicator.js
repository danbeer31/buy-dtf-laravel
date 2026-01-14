(function () {
    async function refreshCartIndicator() {
        const btn   = document.getElementById('cart-indicator');
        const badge = document.getElementById('cart-badge');
        if (!badge) return;
        try {
            const res = await fetch('/cart/indicator', {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            });
            if (!res.ok || res.status === 401) return;
            const data = await res.json();
            if (!data || data.success === false) return;

            const qty = Number(data.count || 0);
            badge.textContent = qty;
            if (qty > 0) {
                badge.classList.remove('d-none');
            } else {
                badge.classList.add('d-none');
            }
            if (btn) btn.title = qty + ' item' + (qty === 1 ? '' : 's') + ' in cart';
        } catch (_) {/* keep silent */}
    }

    // Expose it globally so other scripts can trigger a refresh
    window.refreshCartIndicator = refreshCartIndicator;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', refreshCartIndicator);
    } else {
        refreshCartIndicator();
    }
    setInterval(refreshCartIndicator, 15000);
})();
