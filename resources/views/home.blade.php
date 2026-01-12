<x-app-layout>
    <x-slot name="header">
        <h2 class="font-semibold text-xl text-gray-800 leading-tight">
            {{ __('Welcome to Next Level DTF') }}
        </h2>
    </x-slot>

    <div class="py-12">
        <div class="max-w-7xl mx-auto sm:px-6 lg:px-8">
            <!-- Welcome / Hero -->
            <div class="bg-gray-900 text-white text-center py-16 rounded-lg shadow-xl mb-12">
                <div class="container mx-auto px-4">
                    <h1 class="text-4xl md:text-5xl font-bold mb-4">Welcome to Next Level DTF</h1>
                    <p class="text-xl mb-8 text-gray-300">High-quality DTF prints for your business needs. Durable, vibrant, and customizable.</p>

                    <div class="flex flex-col sm:flex-row gap-4 justify-center">
                        @auth
                            <a href="/cart" class="inline-flex items-center px-6 py-3 bg-yellow-500 border border-transparent rounded-md font-bold text-sm text-black uppercase tracking-widest hover:bg-yellow-400 active:bg-yellow-600 focus:outline-none focus:border-yellow-600 focus:ring ring-yellow-300 disabled:opacity-25 transition ease-in-out duration-150">
                                <span class="bg-black text-yellow-500 text-xs px-2 py-0.5 rounded mr-2">NEW</span>
                                Try our Cart & Uploader
                            </a>
                            <a href="/orders/order" class="inline-flex items-center px-6 py-3 bg-transparent border border-white rounded-md font-bold text-sm text-white uppercase tracking-widest hover:bg-white hover:text-gray-900 focus:outline-none focus:border-white focus:ring ring-white disabled:opacity-25 transition ease-in-out duration-150">
                                Classic Order Form
                            </a>
                        @else
                            <a href="/cart" class="inline-flex items-center px-6 py-3 bg-yellow-500 border border-transparent rounded-md font-bold text-sm text-black uppercase tracking-widest hover:bg-yellow-400 active:bg-yellow-600 focus:outline-none focus:border-yellow-600 focus:ring ring-yellow-300 disabled:opacity-25 transition ease-in-out duration-150">
                                <span class="bg-black text-yellow-500 text-xs px-2 py-0.5 rounded mr-2">NEW</span>
                                Try our Cart & Uploader
                            </a>
                            <a href="{{ route('register') }}" class="inline-flex items-center px-6 py-3 bg-transparent border border-white rounded-md font-bold text-sm text-white uppercase tracking-widest hover:bg-white hover:text-gray-900 focus:outline-none focus:border-white focus:ring ring-white disabled:opacity-25 transition ease-in-out duration-150">
                                Create Account
                            </a>
                        @endauth
                    </div>

                    <div class="text-gray-400 text-sm mt-6">
                        Upload PNG / SVG / PDF • Smart duplicate detection • Live progress
                    </div>
                </div>
            </div>

            <!-- Features -->
            <section class="py-12 bg-white rounded-lg shadow-md mb-12">
                <div class="container mx-auto px-4 text-center">
                    <h2 class="text-3xl font-bold text-gray-800 uppercase mb-12 tracking-wide">Why Choose Us?</h2>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                        <div>
                            <div class="text-blue-600 mb-4">
                                <svg class="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.172-1.172a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z"></path></svg>
                            </div>
                            <h5 class="text-xl font-bold mb-2">High Quality & Vibrant Colors</h5>
                            <p class="text-gray-600">Our prints are vivid, long-lasting, and stand out on any fabric.</p>
                        </div>
                        <div>
                            <div class="text-blue-600 mb-4">
                                <svg class="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 4l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path></svg>
                            </div>
                            <h5 class="text-xl font-bold mb-2">Don't Pay for Empty Film</h5>
                            <p class="text-gray-600">You only pay by the square inches of the images—no charges for blank film.</p>
                        </div>
                        <div>
                            <div class="text-blue-600 mb-4">
                                <svg class="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                            </div>
                            <h5 class="text-xl font-bold mb-2">Fast Delivery</h5>
                            <p class="text-gray-600">Quick turnaround to get your orders on time.</p>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Contact -->
            <section class="bg-gray-800 text-white py-12 rounded-lg shadow-lg">
                <div class="container mx-auto px-4 text-center">
                    <h2 class="text-3xl font-bold uppercase mb-4 tracking-wide">Get In Touch</h2>
                    <p class="text-gray-300 mb-8 text-lg">Have questions or need assistance? Contact us!</p>
                    <a href="/contact" class="inline-flex items-center px-8 py-4 bg-white border border-transparent rounded-md font-bold text-sm text-gray-900 uppercase tracking-widest hover:bg-gray-100 focus:outline-none focus:border-gray-300 focus:ring ring-gray-300 disabled:opacity-25 transition ease-in-out duration-150">
                        Contact Us
                    </a>
                </div>
            </section>
        </div>
    </div>
</x-app-layout>
