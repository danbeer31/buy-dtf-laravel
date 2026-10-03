#!/usr/bin/env python3
"""Run the reviewed Composer lock against an actual PHP 8.2.30 CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import laravel_remember_cookie_dependency_deploy as runner


EXPECTED_ARCHIVE_SHA256 = "8a6e409adb5f7fb196c07315c69195c4eb87eec8acae2e74a0e04ec50745a055"
EXPECTED_PHP_EXECUTABLE_SHA256 = "132075655257b1558c5d896dce117081bc068c90c50dfc5fd9c24c93dbc4312a"
EXPECTED_COMPOSER_SHA256 = "3b3f9503a2d46590170e45edd29734197e797cea545b396d0b2823cac8ef4643"
EXPECTED_LOCK_SHA256 = "77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d"
ARCHIVE_URL = "https://windows.php.net/downloads/releases/archives/php-8.2.30-nts-Win32-vs16-x64.zip"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write(path: Path, content: bytes) -> str:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return sha256_file(path)


def run(
    command: list[str], cwd: Path, *, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=environment,
    )


def windows_path(path: Path) -> str:
    completed = subprocess.run(
        ["/usr/bin/wslpath", "-w", str(path.resolve(strict=True))],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Could not convert path for the Windows PHP CLI: {path}")
    return completed.stdout.strip()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--php", required=True, type=Path)
    parser.add_argument("--php-archive", required=True, type=Path)
    parser.add_argument("--composer", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    project = args.project.resolve(strict=True)
    output = args.output_dir.resolve(strict=True)
    if output.name != "laravel-remember-cookie-runner-v2-20261002" or output.is_symlink():
        raise RuntimeError("Platform evidence directory is not the reviewed v2 evidence root.")
    for path in (args.php, args.php_archive, args.composer, project / "composer.lock"):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"Required platform input is not a regular file: {path}")
    if sha256_file(args.php_archive) != EXPECTED_ARCHIVE_SHA256:
        raise RuntimeError("PHP 8.2.30 archive checksum differs from review.")
    if sha256_file(args.php) != EXPECTED_PHP_EXECUTABLE_SHA256:
        raise RuntimeError("PHP 8.2.30 executable checksum differs from review.")
    if sha256_file(args.composer) != EXPECTED_COMPOSER_SHA256:
        raise RuntimeError("Composer 2.9.3 checksum differs from review.")
    if sha256_file(project / "composer.lock") != EXPECTED_LOCK_SHA256:
        raise RuntimeError("Candidate composer.lock checksum differs from review.")
    if not (project / "vendor/composer/installed.json").is_file():
        raise RuntimeError("Installed candidate vendor metadata is missing.")
    source_identity = runner.source_manifest(project)
    if source_identity != runner.EXPECTED_SOURCE_MANIFEST:
        raise RuntimeError("Installed candidate source CAS differs from review.")
    vendor_identity = runner.require_candidate_vendor(project / "vendor")
    autoload_identity = runner.require_application_autoload(project)
    runner.require_candidate_cache(
        project / "bootstrap/cache",
        runner.EXPECTED_CANDIDATE_CACHE_IDENTITY,
    )
    cache_identity = runner.cache_identity(project / "bootstrap/cache")
    installed = json.loads(
        (project / "vendor/composer/installed.json").read_text(encoding="utf-8")
    )
    packages = installed.get("packages", installed) if isinstance(installed, dict) else installed
    versions = {
        package.get("name"): runner.normalize_package_version(package.get("version"))
        for package in packages
        if isinstance(package, dict)
    }
    installed_candidate_versions = {
        name: versions.get(name) for name in runner.NEW_PACKAGE_VERSIONS
    }
    if installed_candidate_versions != runner.NEW_PACKAGE_VERSIONS:
        raise RuntimeError("Installed candidate package versions differ from review.")

    php_root = args.php.parent.resolve(strict=True)
    php_windows = windows_path(args.php)
    composer_windows = windows_path(args.composer)
    extension_windows = windows_path(php_root / "ext")
    project_windows = windows_path(project)
    php_prefix = [
        str(args.php),
        "-n",
        "-d",
        f"extension_dir={extension_windows}",
        "-d",
        "extension=php_curl.dll",
        "-d",
        "extension=php_fileinfo.dll",
        "-d",
        "extension=php_mbstring.dll",
        "-d",
        "extension=php_openssl.dll",
    ]
    version = run([*php_prefix, "-r", "echo PHP_VERSION, '|', PHP_ZTS;"], output)
    if version.returncode != 0 or version.stdout != b"8.2.30|0":
        raise RuntimeError("PHP CLI is not exactly 8.2.30 NTS.")
    modules = run([*php_prefix, "-m"], output)
    if modules.returncode != 0:
        raise RuntimeError("PHP module inventory failed.")
    loaded_modules = {
        line.strip().lower()
        for line in modules.stdout.decode("utf-8", errors="strict").splitlines()
        if line and not line.startswith("[")
    }
    required_extensions = {"curl", "fileinfo", "mbstring", "openssl"}
    if not required_extensions.issubset(loaded_modules):
        raise RuntimeError("PHP 8.2.30 is missing required native extensions.")
    ini = run([*php_prefix, "--ini"], output)
    if ini.returncode != 0:
        raise RuntimeError("PHP configuration inventory failed.")

    command = [
        *php_prefix,
        composer_windows,
        "--no-plugins",
        "check-platform-reqs",
        "--no-dev",
        "--format=json",
        "--no-interaction",
        "--no-ansi",
        f"--working-dir={project_windows}",
    ]
    platform_environment = dict(os.environ)
    platform_environment["COMPOSER_ROOT_VERSION"] = "1.0.0"
    inherited_wslenv = platform_environment.get("WSLENV", "")
    platform_environment["WSLENV"] = ":".join(
        item for item in (inherited_wslenv, "COMPOSER_ROOT_VERSION") if item
    )
    platform = run(command, output, environment=platform_environment)
    stdout_sha256 = write(output / "php-8.2.30-platform.stdout", platform.stdout)
    stderr_sha256 = write(output / "php-8.2.30-platform.stderr", platform.stderr)
    modules_sha256 = write(output / "php-8.2.30-modules.txt", modules.stdout)
    ini_sha256 = write(output / "php-8.2.30-ini.txt", ini.stdout)
    write(output / "php-8.2.30-version.txt", version.stdout + b"\n")
    if platform.returncode != 0:
        raise RuntimeError(f"PHP 8.2.30 platform check failed: {platform.returncode}")

    receipt = {
        "artifact": "buy-dtf-laravel-remember-cookie-php-platform-v2",
        "status": "pass",
        "verifier_sha256": sha256_file(Path(__file__).resolve(strict=True)),
        "runner_sha256": sha256_file(Path(runner.__file__).resolve(strict=True)),
        "php_version": "8.2.30",
        "php_thread_safety": False,
        "php_executable_sha256": sha256_file(args.php),
        "php_archive_url": ARCHIVE_URL,
        "php_archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "composer_sha256": EXPECTED_COMPOSER_SHA256,
        "candidate_lock_sha256": EXPECTED_LOCK_SHA256,
        "source_manifest": source_identity,
        "vendor_identity": vendor_identity,
        "application_autoload_identity": autoload_identity,
        "cache_identity": cache_identity,
        "package_versions": installed_candidate_versions,
        "command": [
            "php.exe",
            "-n",
            "-d",
            "extension_dir=<isolated-php-8.2.30-nts>/ext",
            "-d",
            "extension=php_curl.dll",
            "-d",
            "extension=php_fileinfo.dll",
            "-d",
            "extension=php_mbstring.dll",
            "-d",
            "extension=php_openssl.dll",
            "composer.phar",
            "--no-plugins",
            "check-platform-reqs",
            "--no-dev",
            "--format=json",
            "--no-interaction",
            "--no-ansi",
            "--working-dir=<installed-candidate-shadow>",
        ],
        "exit_code": platform.returncode,
        "stdout_sha256": stdout_sha256,
        "stderr_sha256": stderr_sha256,
        "modules_sha256": modules_sha256,
        "ini_sha256": ini_sha256,
        "native_extensions": sorted(required_extensions),
        "installed_candidate_project": project_windows,
        "composer_root_version": "1.0.0",
    }
    write(
        output / "php-8.2.30-platform-receipt.json",
        json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exception:
        print(f"STOP: {exception}", file=sys.stderr)
        raise SystemExit(1)
