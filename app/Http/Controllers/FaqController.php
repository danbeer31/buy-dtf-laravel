<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class FaqController extends Controller
{
    public function index()
    {
        $faqs = [
            [
                'category' => 'General',
                'icon' => 'bi-info-circle',
                'question' => 'What is DTF printing?',
                'answer' => 'DTF (Direct to Film) printing is a method where designs are printed onto special films and then transferred to garments using heat pressing.'
            ],
            [
                'category' => 'Ordering',
                'icon' => 'bi-cart-plus',
                'question' => 'How do I place an order?',
                'answer' => 'You can create an account, upload your designs, and place your order through our user-friendly online portal.'
            ],
            [
                'category' => 'General',
                'icon' => 'bi-clock-history',
                'question' => 'What is your turnaround time?',
                'answer' => 'Most orders are printed and shipped within 1-2 business days, depending on the order size and complexity.'
            ],
            [
                'category' => 'Ordering',
                'icon' => 'bi-tag',
                'question' => 'Do you provide bulk discounts?',
                'answer' => 'Yes, we offer discounts for bulk orders. Contact us for a custom quote tailored to your needs.'
            ],
            [
                'category' => 'Ordering',
                'icon' => 'bi-palette',
                'question' => 'Can I use my own designs?',
                'answer' => 'Absolutely! You can upload your designs in supported formats, and we’ll handle the rest.'
            ],
            [
                'category' => 'Care',
                'icon' => 'bi-heart-pulse',
                'question' => 'How do I care for garments with DTF transfers?',
                'answer' => 'Wash garments inside out in cold water, and avoid using bleach. Hang dry for best results.'
            ],
        ];

        // Group FAQs by category
        $groupedFaqs = collect($faqs)->groupBy('category');

        return view('faq', compact('groupedFaqs'));
    }
}
