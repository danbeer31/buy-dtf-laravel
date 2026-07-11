<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Frequently Asked Questions') }}
        </h2>
    </x-slot>

    <div class="container py-5">
        <div class="text-center mb-5">
            <h1 class="display-4 text-primary fw-bold mb-3">Frequently Asked Questions</h1>
            <p class="text-muted fs-5 mx-auto" style="max-width: 600px;">
                Got questions? We've got answers. If you don't find what you're looking for, feel free to
                <a href="{{ route('contact') }}" class="text-primary text-decoration-none fw-bold">contact our support team</a>.
            </p>
        </div>

        <div class="row justify-content-center">
            <div class="col-lg-10">
                @foreach ($groupedFaqs as $category => $faqs)
                    <div class="mb-5">
                        <h3 class="fw-bold text-dark border-bottom pb-2 mb-4">
                            @php
                                $categoryIcon = match($category) {
                                    'General' => 'bi-gear',
                                    'Ordering' => 'bi-cart3',
                                    'Care' => 'bi-stars',
                                    default => 'bi-question-circle'
                                };
                            @endphp
                            <i class="bi {{ $categoryIcon }} me-2 text-primary"></i> {{ $category }}
                        </h3>

                        <div class="accordion font-blinker" id="faqAccordion{{ Str::slug($category) }}">
                            @foreach ($faqs as $index => $faq)
                                <div class="accordion-item border-0 mb-3 shadow-sm rounded-3 overflow-hidden">
                                    <h2 class="accordion-header" id="heading{{ Str::slug($category) }}{{ $index }}">
                                        <button class="accordion-button fs-5 fw-bold collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse{{ Str::slug($category) }}{{ $index }}" aria-expanded="false" aria-controls="collapse{{ Str::slug($category) }}{{ $index }}">
                                            <i class="bi {{ $faq['icon'] }} me-3 text-primary"></i>
                                            {{ $faq['question'] }}
                                        </button>
                                    </h2>
                                    <div id="collapse{{ Str::slug($category) }}{{ $index }}" class="accordion-collapse collapse" aria-labelledby="heading{{ Str::slug($category) }}{{ $index }}" data-bs-parent="#faqAccordion{{ Str::slug($category) }}">
                                        <div class="accordion-body bg-white border-top">
                                            <div class="ps-4 py-2 border-start border-4 border-primary">
                                                {{ $faq['answer'] }}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            @endforeach
                        </div>
                    </div>
                @endforeach
            </div>
        </div>
    </div>
</x-app-layout>
