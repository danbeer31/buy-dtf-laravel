<?php

namespace App\Services\IncomingOrders;

use App\Exceptions\ArtworkValidationException;
use RuntimeException;

class IncomingOrderAssetStore
{
    /**
     * @return array{relative_path: string, absolute_path: string, duplicate: bool}
     */
    public function promoteOriginal(InspectedArtwork $artwork): array
    {
        $extension = $artwork->format === 'jpeg' ? 'jpg' : $artwork->format;
        $relative = sprintf(
            'uploads/images/api/v1/%s/%s.%s',
            substr($artwork->sha256, 0, 2),
            $artwork->sha256,
            $extension,
        );
        $absolute = public_path($relative);

        if (is_file($absolute)) {
            if (! hash_equals($artwork->sha256, (string) hash_file('sha256', $absolute))) {
                throw new ArtworkValidationException('artwork_asset_collision');
            }

            @unlink($artwork->path);
            $this->removeOwnerDirectory(dirname($artwork->path));

            return [
                'relative_path' => '/'.$relative,
                'absolute_path' => $absolute,
                'duplicate' => true,
            ];
        }

        $directory = dirname($absolute);
        if (! is_dir($directory) && ! mkdir($directory, 0775, true) && ! is_dir($directory)) {
            throw new RuntimeException('Unable to create immutable artwork directory.');
        }

        $candidate = $absolute.'.'.bin2hex(random_bytes(8)).'.tmp';
        if (! $this->copyAndSync($artwork->path, $candidate)
            || ! hash_equals($artwork->sha256, (string) hash_file('sha256', $candidate))) {
            @unlink($candidate);
            throw new RuntimeException('Unable to promote immutable artwork.');
        }
        @chmod($candidate, 0644);

        if (! @rename($candidate, $absolute)) {
            // A concurrent identical request may have won the content-addressed name.
            if (! is_file($absolute)
                || ! hash_equals($artwork->sha256, (string) hash_file('sha256', $absolute))) {
                @unlink($candidate);
                throw new RuntimeException('Unable to finalize immutable artwork.');
            }
            @unlink($candidate);
        }

        @unlink($artwork->path);
        $this->removeOwnerDirectory(dirname($artwork->path));

        return [
            'relative_path' => '/'.$relative,
            'absolute_path' => $absolute,
            'duplicate' => false,
        ];
    }

    private function copyAndSync(string $source, string $destination): bool
    {
        $input = @fopen($source, 'rb');
        $output = @fopen($destination, 'xb');
        if ($input === false || $output === false) {
            is_resource($input) && fclose($input);
            is_resource($output) && fclose($output);

            return false;
        }

        try {
            if (stream_copy_to_stream($input, $output) === false || ! fflush($output)) {
                return false;
            }
            if (function_exists('fsync') && ! fsync($output)) {
                return false;
            }

            return true;
        } finally {
            fclose($input);
            fclose($output);
        }
    }

    private function removeOwnerDirectory(string $directory): void
    {
        if (@scandir($directory) === ['.', '..']) {
            @rmdir($directory);
        }
    }
}
