<?php

namespace App\Services\IncomingOrders;

use App\Exceptions\ArtworkFetchException;
use GuzzleHttp\Client;
use GuzzleHttp\Psr7\Uri;
use GuzzleHttp\Psr7\UriResolver;
use Psr\Http\Message\ResponseInterface;
use Throwable;

class BoundedArtworkFetcher
{
    /**
     * @param  callable(): void|null  $heartbeat
     */
    public function fetch(string $initialUrl, string $owner, ?callable $heartbeat = null): FetchedArtwork
    {
        $temporaryDirectory = storage_path('app/private/incoming-orders/tmp/'.$owner);
        if (! is_dir($temporaryDirectory)
            && ! mkdir($temporaryDirectory, 0700, true)
            && ! is_dir($temporaryDirectory)) {
            throw new ArtworkFetchException('artwork_temporary_storage_failed', true);
        }

        $temporaryPath = $temporaryDirectory.DIRECTORY_SEPARATOR.bin2hex(random_bytes(16)).'.download';
        $url = $initialUrl;
        $maxRedirects = max(0, (int) config('incoming_order.fetch.max_redirects', 3));

        try {
            for ($redirect = 0; $redirect <= $maxRedirects; $redirect++) {
                [$host, $pinnedIp] = $this->validateDestination($url);
                $primaryIp = null;
                $response = $this->request($url, $host, $pinnedIp, $primaryIp);

                if ($primaryIp === null) {
                    throw new ArtworkFetchException('artwork_transport_unverified', true);
                }
                if (! $this->isPublicIp($primaryIp)) {
                    throw new ArtworkFetchException('artwork_network_denied');
                }
                if (! $this->sameIp($primaryIp, $pinnedIp)) {
                    throw new ArtworkFetchException('artwork_destination_changed', true);
                }

                $status = $response->getStatusCode();
                if ($status >= 300 && $status < 400) {
                    $location = trim($response->getHeaderLine('Location'));
                    if ($location === '' || $redirect === $maxRedirects) {
                        throw new ArtworkFetchException('artwork_redirect_invalid');
                    }
                    $url = (string) UriResolver::resolve(new Uri($url), new Uri($location));
                    $heartbeat && $heartbeat();

                    continue;
                }

                if ($status < 200 || $status >= 300) {
                    throw new ArtworkFetchException(
                        $status >= 500 ? 'artwork_source_unavailable' : 'artwork_source_rejected',
                        $status >= 500,
                    );
                }

                $declaredLength = $response->getHeaderLine('Content-Length');
                $maximumBytes = (int) config('incoming_order.fetch.max_bytes', 50 * 1024 * 1024);
                if ($declaredLength !== '' && ctype_digit($declaredLength) && (int) $declaredLength > $maximumBytes) {
                    throw new ArtworkFetchException('artwork_download_too_large');
                }

                $bytes = $this->streamResponse($response, $temporaryPath, $maximumBytes, $heartbeat);
                $contentType = strtolower(trim(explode(';', $response->getHeaderLine('Content-Type'))[0] ?? ''));

                return new FetchedArtwork(
                    temporaryPath: $temporaryPath,
                    approvedHost: $host,
                    bytes: $bytes,
                    declaredContentType: $contentType !== '' ? $contentType : null,
                );
            }
        } catch (ArtworkFetchException $exception) {
            @unlink($temporaryPath);
            $this->removeEmptyDirectory($temporaryDirectory);
            throw $exception;
        } catch (Throwable $exception) {
            @unlink($temporaryPath);
            $this->removeEmptyDirectory($temporaryDirectory);
            throw new ArtworkFetchException('artwork_source_unavailable', true);
        }

        throw new ArtworkFetchException('artwork_redirect_invalid');
    }

    /**
     * Split out for deterministic receiver tests without external network access.
     */
    protected function request(string $url, string $host, string $pinnedIp, ?string &$primaryIp): ResponseInterface
    {
        if (! defined('CURLOPT_RESOLVE')) {
            throw new ArtworkFetchException('artwork_transport_unverified', true);
        }
        $address = str_contains($pinnedIp, ':') ? '['.$pinnedIp.']' : $pinnedIp;
        $curlOptions = [CURLOPT_RESOLVE => [sprintf('%s:443:%s', $host, $address)]];

        $client = new Client([
            'allow_redirects' => false,
            'connect_timeout' => max(1, (int) config('incoming_order.fetch.connect_timeout_seconds', 10)),
            'timeout' => max(1, (int) config('incoming_order.fetch.timeout_seconds', 30)),
            'http_errors' => false,
            'stream' => true,
            'verify' => true,
            'headers' => [
                'Accept' => 'image/png,image/jpeg,image/webp',
                'User-Agent' => 'BuyDTF-IncomingOrder-v1',
            ],
            'curl' => $curlOptions,
            'on_stats' => static function ($stats) use (&$primaryIp): void {
                $handlerStats = $stats->getHandlerStats();
                $primaryIp = isset($handlerStats['primary_ip']) ? (string) $handlerStats['primary_ip'] : null;
            },
        ]);

        return $client->request('GET', $url);
    }

    /**
     * @param  callable(): void|null  $heartbeat
     */
    private function streamResponse(
        ResponseInterface $response,
        string $destination,
        int $maximumBytes,
        ?callable $heartbeat,
    ): int {
        $output = @fopen($destination, 'xb');
        if ($output === false) {
            throw new ArtworkFetchException('artwork_temporary_storage_failed', true);
        }

        $bytes = 0;
        $lastHeartbeat = microtime(true);
        try {
            $body = $response->getBody();
            while (! $body->eof()) {
                $chunk = $body->read(64 * 1024);
                if ($chunk === '') {
                    continue;
                }
                $bytes += strlen($chunk);
                if ($bytes > $maximumBytes) {
                    throw new ArtworkFetchException('artwork_download_too_large');
                }
                if (fwrite($output, $chunk) !== strlen($chunk)) {
                    throw new ArtworkFetchException('artwork_temporary_storage_failed', true);
                }
                if ($heartbeat && microtime(true) - $lastHeartbeat >= 15) {
                    $heartbeat();
                    $lastHeartbeat = microtime(true);
                }
            }

            if ($bytes < 1) {
                throw new ArtworkFetchException('artwork_download_empty');
            }
            fflush($output);
            if (function_exists('fsync')) {
                fsync($output);
            }
        } finally {
            fclose($output);
        }

        return $bytes;
    }

    /** @return array{0: string, 1: string} */
    private function validateDestination(string $url): array
    {
        $parts = parse_url($url);
        $host = is_array($parts) ? strtolower((string) ($parts['host'] ?? '')) : '';
        if (($parts['scheme'] ?? null) !== 'https'
            || $host === ''
            || isset($parts['user'])
            || isset($parts['pass'])
            || isset($parts['fragment'])
            || (isset($parts['port']) && (int) $parts['port'] !== 443)) {
            throw new ArtworkFetchException('artwork_url_invalid');
        }

        if (! in_array($host, (array) config('incoming_order.allowed_hosts', []), true)) {
            throw new ArtworkFetchException('artwork_host_not_allowed');
        }

        $addresses = $this->resolveHost($host);
        foreach ($addresses as $address) {
            if (! $this->isPublicIp($address)) {
                throw new ArtworkFetchException('artwork_network_denied');
            }
        }
        if ($addresses === []) {
            throw new ArtworkFetchException('artwork_dns_failed', true);
        }

        sort($addresses, SORT_STRING);

        return [$host, $addresses[0]];
    }

    /** @return list<string> */
    protected function resolveHost(string $host): array
    {
        if (filter_var($host, FILTER_VALIDATE_IP)) {
            return [$host];
        }

        $addresses = [];
        $records = @dns_get_record($host, DNS_A | DNS_AAAA);
        if (is_array($records)) {
            foreach ($records as $record) {
                $address = $record['ip'] ?? $record['ipv6'] ?? null;
                if (is_string($address)) {
                    $addresses[] = $address;
                }
            }
        }

        if ($addresses === []) {
            foreach ((array) @gethostbynamel($host) as $address) {
                if (is_string($address)) {
                    $addresses[] = $address;
                }
            }
        }

        return array_values(array_unique($addresses));
    }

    private function isPublicIp(string $ip): bool
    {
        if (! filter_var($ip, FILTER_VALIDATE_IP)) {
            return false;
        }
        if (! filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)) {
            return false;
        }

        // Explicitly include ranges not consistently classified by older PHP builds.
        if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
            $long = ip2long($ip);
            if ($long === false) {
                return false;
            }
            $unsigned = (int) sprintf('%u', $long);
            foreach ([
                ['100.64.0.0', '100.127.255.255'],
                ['192.0.0.0', '192.0.0.255'],
                ['198.18.0.0', '198.19.255.255'],
            ] as [$start, $end]) {
                if ($unsigned >= (int) sprintf('%u', ip2long($start))
                    && $unsigned <= (int) sprintf('%u', ip2long($end))) {
                    return false;
                }
            }
        }

        return true;
    }

    private function sameIp(string $left, string $right): bool
    {
        $leftBinary = @inet_pton($left);
        $rightBinary = @inet_pton($right);

        return is_string($leftBinary)
            && is_string($rightBinary)
            && hash_equals($leftBinary, $rightBinary);
    }

    private function removeEmptyDirectory(string $directory): void
    {
        $items = @scandir($directory);
        if ($items === ['.', '..']) {
            @rmdir($directory);
        }
    }
}
