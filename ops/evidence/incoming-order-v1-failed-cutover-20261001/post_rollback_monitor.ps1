param(
    [int] $Samples = 30,
    [int] $IntervalSeconds = 60
)

$ErrorActionPreference = 'Stop'
$outputPath = Join-Path $PSScriptRoot 'post-rollback-monitor.jsonl'
$runtimeHelper = '/var/www/buy-dtf/storage/app/private/operations/incoming-order-v1-releases/0799440b-20261001T013235Z/inputs/incoming_order_v1_runtime_probe.php'
$expectedFrontController = 'eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9'
$expectedSchema = '4f1990336946bde95c6a13d0245fe4a5845eff2f23999f62e8529478d95d51ed'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (Test-Path -LiteralPath $outputPath) {
    throw "Monitoring evidence already exists: $outputPath"
}

$routes = @(
    @{ url = 'https://buy-dtf.com/'; expected = 200 },
    @{ url = 'https://buy-dtf.com/up'; expected = 200 },
    @{ url = 'https://buy-dtf.com/login'; expected = 200 },
    @{ url = 'https://buy-dtf.com/admin'; expected = 302 },
    @{ url = 'https://buy-dtf.com/checkout'; expected = 302 },
    @{ url = 'https://www.buy-dtf.com/'; expected = 200 },
    @{ url = 'https://www.buy-dtf.com/up'; expected = 200 }
)

function Get-HttpProbe {
    param([string] $Url)

    $raw = & curl.exe --silent --show-error --output NUL --write-out '%{http_code}|%{size_download}|%{redirect_url}' --connect-timeout 5 --max-time 15 --max-redirs 0 $Url
    if ($LASTEXITCODE -ne 0) {
        throw "HTTP probe failed for $Url"
    }
    $parts = $raw -split '\|', 3
    if ($parts.Count -ne 3) {
        throw "HTTP probe returned an invalid result for $Url"
    }
    [ordered]@{
        url = $Url
        status = [int] $parts[0]
        bytes = [int] $parts[1]
        redirect_url = $parts[2]
    }
}

for ($index = 1; $index -le $Samples; $index++) {
    $runtimeLines = & ssh dan@134.209.175.25 "/usr/bin/php $runtimeHelper /var/www/buy-dtf"
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime probe failed for sample $index"
    }
    $runtime = ($runtimeLines -join "`n") | ConvertFrom-Json

    $identityLines = & ssh dan@134.209.175.25 "sha256sum /var/www/buy-dtf/public/index.php; stat -c 'mode=%a owner=%U:%G' /var/www/buy-dtf/public/index.php; if test -f /var/www/buy-dtf/storage/framework/down; then echo maintenance=1; else echo maintenance=0; fi; if test -e /var/www/buy-dtf/app/Services/IncomingOrders/IncomingOrderV1Receiver.php; then echo receiver_source=1; else echo receiver_source=0; fi"
    if ($LASTEXITCODE -ne 0) {
        throw "Live identity probe failed for sample $index"
    }
    $frontController = ($identityLines[0] -split '\s+')[0]
    $mode = ($identityLines[1] -split ' ')[0].Substring(5)
    $owner = ($identityLines[1] -split ' ')[1].Substring(6)
    $maintenanceActive = $identityLines[2] -eq 'maintenance=1'
    $receiverSourcePresent = $identityLines[3] -eq 'receiver_source=1'

    $health = @()
    $healthPass = $true
    foreach ($route in $routes) {
        $probe = Get-HttpProbe -Url $route.url
        if ($probe.status -ne $route.expected) {
            $healthPass = $false
        }
        $health += $probe
    }

    $invariants = [ordered]@{
        environment = $runtime.application_environment -eq 'local'
        debug_disabled = $runtime.application_debug -eq $false
        php_version = $runtime.runtime.php_version -eq '8.2.30'
        laravel_version = $runtime.runtime.laravel_version -eq '12.69.0'
        schema_identity = $runtime.schema.sha256 -eq $expectedSchema
        migration_recorded_once = $runtime.migration_ledger.target_entry_count -eq 1
        incoming_order_jobs_empty = $runtime.schema.target_table_row_counts.incoming_order_jobs -eq 0
        api_asset_records_empty = $runtime.schema.target_table_row_counts.api_asset_records -eq 0
        receiver_disabled = $runtime.capabilities.receiver_enabled -eq $false
        job_label_disabled = $runtime.capabilities.job_label_enabled -eq $false
        retention_disabled = $runtime.capabilities.retention_enabled -eq $false
        artwork_hosts_empty = $runtime.capabilities.allowed_host_count -eq 0
        queue_sync = $runtime.queue.connection -eq 'sync'
        queue_empty = $runtime.queue.counts.jobs -eq 0
        failed_jobs_empty = $runtime.queue.counts.failed_jobs -eq 0
        original_front_controller = $frontController -eq $expectedFrontController
        front_controller_mode = $mode -eq '644'
        front_controller_owner = $owner -eq 'dan:dan'
        maintenance_inactive = -not $maintenanceActive
        receiver_source_absent = -not $receiverSourcePresent
        health = $healthPass
    }
    $pass = -not ($invariants.Values -contains $false)

    $sample = [ordered]@{
        number = $index
        at_utc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
        pass = $pass
        health = $health
        runtime = [ordered]@{
            php_version = $runtime.runtime.php_version
            laravel_version = $runtime.runtime.laravel_version
            schema_sha256 = $runtime.schema.sha256
            migration_ledger_rows = $runtime.migration_ledger.row_count
            migration_ledger_sha256 = $runtime.migration_ledger.rows_sha256
            target_migration_count = $runtime.migration_ledger.target_entry_count
            target_table_rows = $runtime.schema.target_table_row_counts
            capabilities = $runtime.capabilities
            queue = $runtime.queue
        }
        front_controller = [ordered]@{
            sha256 = $frontController
            mode = $mode
            owner = $owner
        }
        maintenance_active = $maintenanceActive
        receiver_source_present = $receiverSourcePresent
        invariants = $invariants
    }

    $line = $sample | ConvertTo-Json -Compress -Depth 10
    [System.IO.File]::AppendAllText($outputPath, $line + "`n", $utf8NoBom)
    Write-Output ("sample={0}/{1} at={2} pass={3}" -f $index, $Samples, $sample.at_utc, $pass)

    if (-not $pass) {
        throw "A post-rollback monitoring invariant failed in sample $index"
    }
    if ($index -lt $Samples) {
        Start-Sleep -Seconds $IntervalSeconds
    }
}

Write-Output "monitor_path=$outputPath"
Write-Output ("monitor_sha256=" + (Get-FileHash -Algorithm SHA256 -LiteralPath $outputPath).Hash.ToLowerInvariant())
