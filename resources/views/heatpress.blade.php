<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Heat Press Instructions') }}
        </h2>
    </x-slot>

    <div class="container py-5">
        <div class="text-center mb-5">
            <h1 class="display-4 text-primary fw-bold">Heat Press Instructions</h1>
            <p class="text-muted fs-5">Follow these steps carefully to ensure perfect application of your DTF transfers.</p>
        </div>

        <div class="steps px-md-5">
            <div class="step mb-4">
                <h3 class="text-secondary"><i class="bi bi-gear-fill text-primary me-2"></i> 1. Prepare the Heat Press</h3>
                <p>Set your heat press to <strong>300°F</strong> (or <strong>275°F</strong> for garments prone to dye migration).</p>
            </div>
            <div class="step mb-4">
                <h3 class="text-secondary"><i class="bi bi-box-arrow-in-down text-primary me-2"></i> 2. Load the Garment</h3>
                <p>Place the garment onto the heat press, ensuring it is smooth and wrinkle-free.</p>
            </div>
            <div class="step mb-4">
                <h3 class="text-secondary"><i class="bi bi-arrows-move text-primary me-2"></i> 3. Position the Transfer</h3>
                <p>Align the DTF transfer at your desired position on the garment.</p>
            </div>
            <div class="step mb-4">
                <h3 class="text-secondary"><i class="bi bi-clock-fill text-primary me-2"></i> 4. First Press</h3>
                <p>Close the heat press and apply pressure for <strong>10 seconds</strong>.</p>
            </div>
            <div class="step mb-4">
                <h3 class="text-secondary"><i class="bi bi-file-earmark-break-fill text-primary me-2"></i> 5. Peel the Transfer</h3>
                <p>Carefully peel the transfer while it is still hot.</p>
            </div>
            <div class="step mb-4">
                <h3 class="text-secondary"><i class="bi bi-file-earmark-richtext-fill text-primary me-2"></i> 6. Cover and Second Press</h3>
                <p>
                    Place a parchment cover sheet over the transfer.<br>
                    Press again for <strong>5 seconds</strong>.
                </p>
            </div>
            <div class="step mb-4">
                <h3 class="text-secondary"><i class="bi bi-check2-circle text-primary me-2"></i> 7. Remove the Cover Sheet</h3>
                <p>Lift the cover sheet carefully. Your transfer is now complete!</p>
            </div>
        </div>

        <div class="alert alert-warning mt-5">
            <h5 class="text-danger"><i class="bi bi-exclamation-triangle-fill me-2"></i> Important Note:</h5>
            <p>For apparel that is prone to dye migration, always press at <strong>275°F</strong> instead of <strong>300°F</strong>.</p>
        </div>

        <div class="mt-3 small text-danger">
            <p>We are not responsible for transfers that are not pressed properly or fail to print correctly. We do not guarantee durability during washing for improperly applied transfers. Please follow all instructions carefully for the best results.</p>
        </div>
    </div>
</x-app-layout>
