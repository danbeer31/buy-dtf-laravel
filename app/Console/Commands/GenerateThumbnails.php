<?php

namespace App\Console\Commands;

use App\Models\DtfImage;
use App\Models\SavedImage;
use App\Helpers\ImageHelper;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\File;

class GenerateThumbnails extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'images:generate-thumbnails {--force : Regenerate existing thumbnails}';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'Generate thumbnails for all existing DTF and Saved images';

    /**
     * Execute the console command.
     */
    public function handle()
    {
        $force = $this->option('force');

        $this->info('Starting thumbnail generation for DTF Images...');
        $dtfImages = DtfImage::all();
        $this->processImages($dtfImages, 'DtfImage', $force);

        $this->info('Starting thumbnail generation for Saved Images...');
        $savedImages = SavedImage::all();
        $this->processImages($savedImages, 'SavedImage', $force);

        $this->info('Thumbnail generation completed!');
    }

    protected function processImages($images, $type, $force)
    {
        $bar = $this->output->createProgressBar(count($images));
        $bar->start();

        foreach ($images as $img) {
            if (!$force && $img->thumbnail && File::exists(public_path($img->thumbnail))) {
                $bar->advance();
                continue;
            }

            $originalPath = public_path($img->image);
            if (!File::exists($originalPath)) {
                $bar->advance();
                continue;
            }

            $relativeThumb = 'uploads/images/thumbs/' . basename($img->image);
            $thumbPath = public_path($relativeThumb);

            if (!is_dir(dirname($thumbPath))) {
                mkdir(dirname($thumbPath), 0777, true);
            }

            $result = ImageHelper::generateThumbnail($originalPath, $thumbPath);

            if ($result['success']) {
                $img->update(['thumbnail' => '/' . $relativeThumb]);
            }

            $bar->advance();
        }

        $bar->finish();
        $this->line('');
    }
}
