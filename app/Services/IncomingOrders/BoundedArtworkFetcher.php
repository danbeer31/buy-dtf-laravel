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
    public function fetch(
        string $initialUrl,
        string $owner,
        ?callable $heartbeat = null,
        ?int $deadlineNs = null,
    ): FetchedArtwork {
        $deadlineNs ??= hrtime(true)
            + (max(1, (int) config('incoming_order.request_budget_seconds', 60)) * 1_000_000_000);
        $this->assertBeforeDeadline($deadlineNs);
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
                $this->assertBeforeDeadline($deadlineNs);
                [$host, $pinnedIp] = $this->validateDestination($url, $deadlineNs);
                $primaryIp = null;
                $response = $this->request(
                    $url,
                    $host,
                    $pinnedIp,
                    $primaryIp,
                    $this->remainingSeconds($deadlineNs),
                );
                $this->assertBeforeDeadline($deadlineNs);

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
                        throw new ArtworkFetchException('artwork_redirect_invalid', true);
                    }
                    $url = (string) UriResolver::resolve(new Uri($url), new Uri($location));
                    $heartbeat && $heartbeat();
                    $this->assertBeforeDeadline($deadlineNs);

                    continue;
                }

                if ($status < 200 || $status >= 300) {
                    // Access tokens and staged artifact URLs can expire. The URL is
                    // transport-only and may be refreshed without changing the
                    // semantic fingerprint, so every source response is retryable.
                    throw new ArtworkFetchException('artwork_source_unavailable', true);
                }

                $declaredLength = $response->getHeaderLine('Content-Length');
                $maximumBytes = (int) config('incoming_order.fetch.max_bytes', 50 * 1024 * 1024);
                if ($declaredLength !== '' && ctype_digit($declaredLength) && (int) $declaredLength > $maximumBytes) {
                    throw new ArtworkFetchException('artwork_download_too_large');
                }

                $bytes = $this->streamResponse(
                    $response,
                    $temporaryPath,
                    $maximumBytes,
                    $heartbeat,
                    $deadlineNs,
                );
                $this->assertBeforeDeadline($deadlineNs);
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

        throw new ArtworkFetchException('artwork_redirect_invalid', true);
    }

    /**
     * Split out for deterministic receiver tests without external network access.
     */
    protected function request(
        string $url,
        string $host,
        string $pinnedIp,
        ?string &$primaryIp,
        float $remainingSeconds,
    ): ResponseInterface {
        if (! defined('CURLOPT_RESOLVE')) {
            throw new ArtworkFetchException('artwork_transport_unverified', true);
        }
        $address = str_contains($pinnedIp, ':') ? '['.$pinnedIp.']' : $pinnedIp;
        $curlOptions = [CURLOPT_RESOLVE => [sprintf('%s:443:%s', $host, $address)]];

        $timeout = min(
            max(0.001, $remainingSeconds),
            max(1, (int) config('incoming_order.fetch.timeout_seconds', 30)),
        );
        $client = new Client([
            'allow_redirects' => false,
            'connect_timeout' => min(
                $timeout,
                max(1, (int) config('incoming_order.fetch.connect_timeout_seconds', 10)),
            ),
            'timeout' => $timeout,
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
        int $deadlineNs,
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
                $this->assertBeforeDeadline($deadlineNs);
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
                    $this->assertBeforeDeadline($deadlineNs);
                    $lastHeartbeat = microtime(true);
                }
            }

            if ($bytes < 1) {
                throw new ArtworkFetchException('artwork_download_empty', true);
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
    private function validateDestination(string $url, int $deadlineNs): array
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

        $this->assertBeforeDeadline($deadlineNs);
        $addresses = $this->resolveHost($host);
        $this->assertBeforeDeadline($deadlineNs);
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
        $ip = $this->normalizeIp($ip);
        if ($ip === null) {
            return false;
        }
        if (! filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE)) {
            return false;
        }

        $deniedCidrs = filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)
            ? [
                '0.0.0.0/8',
                '10.0.0.0/8',
                '100.64.0.0/10',
                '127.0.0.0/8',
                '169.254.0.0/16',
                '172.16.0.0/12',
                '192.0.0.0/24',
                '192.0.2.0/24',
                '192.88.99.0/24',
                '192.168.0.0/16',
                '198.18.0.0/15',
                '198.51.100.0/24',
                '203.0.113.0/24',
                '224.0.0.0/4',
                '240.0.0.0/4',
            ]
            : [
                '::/96',
                '::1/128',
                '64:ff9b::/96',
                '64:ff9b:1::/48',
                '100::/64',
                '2001::/32',
                '2001:2::/48',
                '2001:db8::/32',
                '2001:10::/28',
                '2001:20::/28',
                '2002::/16',
                'fc00::/7',
                'fe80::/10',
                'ff00::/8',
            ];

        foreach ($deniedCidrs as $cidr) {
            if ($this->isInCidr($ip, $cidr)) {
                return false;
            }
        }

        return true;
    }

    private function sameIp(string $left, string $right): bool
    {
        $left = $this->normalizeIp($left);
        $right = $this->normalizeIp($right);
        if ($left === null || $right === null) {
            return false;
        }
        $leftBinary = @inet_pton($left);
        $rightBinary = @inet_pton($right);

        return is_string($leftBinary)
            && is_string($rightBinary)
            && hash_equals($leftBinary, $rightBinary);
    }

    private function normalizeIp(string $ip): ?string
    {
        $binary = @inet_pton(trim($ip, '[]'));
        if (! is_string($binary)) {
            return null;
        }

        // Canonicalize IPv4-mapped IPv6 so private/link-local IPv4 policy
        // cannot be bypassed with ::ffff:a.b.c.d notation.
        if (strlen($binary) === 16
            && substr($binary, 0, 10) === str_repeat("\0", 10)
            && substr($binary, 10, 2) === "\xff\xff") {
            $mapped = @inet_ntop(substr($binary, 12, 4));

            return is_string($mapped) ? $mapped : null;
        }

        $canonical = @inet_ntop($binary);

        return is_string($canonical) ? strtolower($canonical) : null;
    }

    private function isInCidr(string $ip, string $cidr): bool
    {
        [$network, $prefixText] = explode('/', $cidr, 2);
        $ipBinary = @inet_pton($ip);
        $networkBinary = @inet_pton($network);
        if (! is_string($ipBinary)
            || ! is_string($networkBinary)
            || strlen($ipBinary) !== strlen($networkBinary)) {
            return false;
        }

        $prefix = (int) $prefixText;
        $maximum = strlen($ipBinary) * 8;
        if ($prefix < 0 || $prefix > $maximum) {
            return false;
        }

        $wholeBytes = intdiv($prefix, 8);
        if ($wholeBytes > 0
            && ! hash_equals(substr($networkBinary, 0, $wholeBytes), substr($ipBinary, 0, $wholeBytes))) {
            return false;
        }

        $remainingBits = $prefix % 8;
        if ($remainingBits === 0) {
            return true;
        }

        $mask = (0xFF << (8 - $remainingBits)) & 0xFF;

        return (ord($networkBinary[$wholeBytes]) & $mask) === (ord($ipBinary[$wholeBytes]) & $mask);
    }

    private function assertBeforeDeadline(int $deadlineNs): void
    {
        if (hrtime(true) >= $deadlineNs) {
            throw new ArtworkFetchException('receiver_request_budget_exceeded', true);
        }
    }

    private function remainingSeconds(int $deadlineNs): float
    {
        $this->assertBeforeDeadline($deadlineNs);

        return max(0.001, ($deadlineNs - hrtime(true)) / 1_000_000_000);
    }

    private function removeEmptyDirectory(string $directory): void
    {
        $items = @scandir($directory);
        if ($items === ['.', '..']) {
            @rmdir($directory);
        }
    }
}
