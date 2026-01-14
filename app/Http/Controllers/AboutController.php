<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class AboutController extends Controller
{
    public function index()
    {
        return view('about.index');
    }

    public function dtf()
    {
        $data = [
            'features' => [
                [
                    'icon' => 'bi bi-palette-fill',
                    'title' => 'High-Quality Prints',
                    'description' => 'Our DTF prints are vibrant, durable, and perfect for any fabric.'
                ],
                [
                    'icon' => 'bi bi-clock-history',
                    'title' => 'Fast Turnaround',
                    'description' => 'Most orders are printed the same day or the next, ensuring timely delivery.'
                ],
                [
                    'icon' => 'bi bi-currency-dollar',
                    'title' => 'Cost-Effective',
                    'description' => 'Pay only for the square inches of your designs, with no charges for blank film.'
                ]
            ],
            'how_to' => [
                [
                    'step' => 1,
                    'title' => 'Create an Account',
                    'description' => 'Sign up on our platform to access our services and manage your orders.'
                ],
                [
                    'step' => 2,
                    'title' => 'Place Your Order',
                    'description' => 'Upload your design, select options, and submit your order through our easy-to-use interface.'
                ],
                [
                    'step' => 3,
                    'title' => 'Receive an Invoice',
                    'description' => 'You will receive a detailed invoice via QuickBooks immediately after placing your order.'
                ],
                [
                    'step' => 4,
                    'title' => 'Production Begins',
                    'description' => 'Once your invoice is paid, we will start production on your order.'
                ]
            ]
        ];

        return view('about.dtf', $data);
    }

    public function us()
    {
        $aboutInfo = [
            'title' => 'About Us',
            'headline' => 'Small Shop, Big Quality',
            'description' => 'We are a dedicated team of passionate individuals, bringing the highest quality DTF printing services to you. Although we are a small shop, our commitment to excellence rivals that of the biggest industry players.',
            'values' => [
                [
                    'title' => 'Customer-Centric',
                    'description' => 'Our customers are at the heart of everything we do. We strive to provide unmatched quality and personalized service.'
                ],
                [
                    'title' => 'State-of-the-Art Technology',
                    'description' => 'We use advanced DTF printing technology to ensure vibrant, long-lasting prints on every order.'
                ],
                [
                    'title' => 'Fast Turnaround',
                    'description' => 'Most orders are completed within 24-48 hours, ensuring you get your products when you need them.'
                ],
                [
                    'title' => 'Eco-Friendly',
                    'description' => 'We are committed to sustainability and use environmentally friendly materials and processes wherever possible.'
                ],
                [
                    'title' => 'Attention to Detail',
                    'description' => 'Every order is treated with care and attention, ensuring top-notch results every time.'
                ],
            ],
            'closing' => 'At our core, we believe in building strong relationships with our customers and providing services that help bring your creative ideas to life. Whether it’s a single print or a bulk order, we’ve got you covered with exceptional quality and service you can trust.'
        ];

        return view('about.us', compact('aboutInfo'));
    }
}
