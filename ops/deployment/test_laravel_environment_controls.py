from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


DEPLOYMENT_DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOYMENT_DIRECTORY))
import laravel_nginx_identity as CONTROLS  # noqa: E402


def valid_fpm_payload() -> dict[str, object]:
    normalized = {
        "opcache.enable": True,
        "opcache.validate_timestamps": True,
        "opcache.revalidate_freq": 2,
        "opcache.file_update_protection": 2,
    }
    return {
        "artifact": CONTROLS.FPM_OPCACHE_ARTIFACT,
        "sapi": "fpm-fcgi",
        "php_version": "8.2.30",
        "directives": {
            "opcache.enable": {"raw": "1", "normalized": True},
            "opcache.validate_timestamps": {"raw": "On", "normalized": True},
            "opcache.revalidate_freq": {"raw": "2", "normalized": 2},
            "opcache.file_update_protection": {"raw": "02", "normalized": 2},
        },
        "opcache_configuration_directives": normalized,
    }


class FpmOpcachePayloadTest(unittest.TestCase):
    def test_exact_fpm_shape_and_independent_normalization_pass(self) -> None:
        validated = CONTROLS.validate_fpm_opcache_payload(valid_fpm_payload())
        self.assertEqual("fpm-fcgi", validated["sapi"])
        self.assertEqual(
            {
                "opcache.enable": True,
                "opcache.validate_timestamps": True,
                "opcache.revalidate_freq": 2,
                "opcache.file_update_protection": 2,
            },
            validated["opcache_configuration_directives"],
        )

    def test_non_fpm_sapi_is_rejected(self) -> None:
        payload = valid_fpm_payload()
        payload["sapi"] = "cli"
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "PHP-FPM"):
            CONTROLS.validate_fpm_opcache_payload(payload)

    def test_missing_or_extra_directive_is_rejected(self) -> None:
        for mutation in ("missing", "extra"):
            with self.subTest(mutation=mutation):
                payload = valid_fpm_payload()
                directives = payload["directives"]
                normalized = payload["opcache_configuration_directives"]
                assert isinstance(directives, dict)
                assert isinstance(normalized, dict)
                if mutation == "missing":
                    directives.pop("opcache.revalidate_freq")
                    normalized.pop("opcache.revalidate_freq")
                else:
                    directives["opcache.memory_consumption"] = {
                        "raw": "128",
                        "normalized": 128,
                    }
                    normalized["opcache.memory_consumption"] = 128
                with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "directive set"):
                    CONTROLS.validate_fpm_opcache_payload(payload)

    def test_normalized_mismatch_and_boolean_integer_confusion_are_rejected(self) -> None:
        payload = valid_fpm_payload()
        directives = payload["directives"]
        assert isinstance(directives, dict)
        directives["opcache.revalidate_freq"] = {"raw": "2", "normalized": True}
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "not integer"):
            CONTROLS.validate_fpm_opcache_payload(payload)

        payload = valid_fpm_payload()
        directives = payload["directives"]
        assert isinstance(directives, dict)
        directives["opcache.enable"] = {"raw": "off", "normalized": True}
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "independent normalization"):
            CONTROLS.validate_fpm_opcache_payload(payload)

    def test_disabled_timestamp_validation_is_rejected(self) -> None:
        payload = valid_fpm_payload()
        directives = payload["directives"]
        normalized = payload["opcache_configuration_directives"]
        assert isinstance(directives, dict)
        assert isinstance(normalized, dict)
        directives["opcache.validate_timestamps"] = {"raw": "0", "normalized": False}
        normalized["opcache.validate_timestamps"] = False
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "must be enabled"):
            CONTROLS.validate_fpm_opcache_payload(payload)

    def test_ini_and_opcache_configuration_disagreement_is_rejected(self) -> None:
        payload = valid_fpm_payload()
        normalized = payload["opcache_configuration_directives"]
        assert isinstance(normalized, dict)
        normalized["opcache.file_update_protection"] = 3
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "normalized views"):
            CONTROLS.validate_fpm_opcache_payload(payload)


class NginxIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="buy-dtf-nginx-controls-")
        self.root = Path(self.temporary.name)
        self.expected_document_root = self.root / "application/public"
        self.expected_document_root.mkdir(parents=True)
        self.evidence = self.root / "evidence"
        self.evidence.mkdir(mode=0o700)
        os.chmod(self.evidence, 0o700)
        self.nginx = self.root / "nginx"
        self.nginx.write_bytes(b"reviewed-nginx-binary-fixture\n")
        os.chmod(self.nginx, 0o755)
        self.sudo = self.root / "sudo"
        self.sudo.write_bytes(b"reviewed-sudo-binary-fixture\n")
        os.chmod(self.sudo, 0o755)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def config(self, *, root: Path | None = None, duplicate_tls: bool = False) -> str:
        document_root = root or self.expected_document_root
        tls_block = f"""
        server {{
            listen 443 ssl http2;
            listen [::]:443 ssl http2;
            server_name buy-dtf.com www.buy-dtf.com;
            root \"{document_root}\";
            ssl_certificate /private/certificate.pem;
            ssl_certificate_key SUPER_SECRET_DO_NOT_COPY;
            location / {{ try_files $uri $uri/ /index.php?$query_string; }}
            location ~ \\.php$ {{
                fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
                fastcgi_pass unix:/run/php/php8.2-fpm.sock;
            }}
        }}
        """
        return f"""
        # nginx -T concatenates expanded include files.
        http {{ include /etc/nginx/sites-enabled/*; }}
        server {{
            listen 80;
            server_name buy-dtf.com;
            return 301 https://buy-dtf.com$request_uri;
        }}
        {tls_block}
        {tls_block if duplicate_tls else ''}
        """

    def completed(self, config: str, *, returncode: int = 0):
        def run(command, **kwargs):
            self.assertEqual(subprocess.PIPE, kwargs["stdout"])
            self.assertEqual(subprocess.PIPE, kwargs["stderr"])
            self.assertFalse(kwargs["check"])
            self.assertEqual(
                {
                    "LANG": "C",
                    "LC_ALL": "C",
                    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                },
                kwargs["env"],
            )
            if command == [str(self.nginx.resolve()), "-V"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=b"",
                    stderr=b"nginx version: nginx/1.24.0\nconfigure arguments: --fixture\n",
                )
            self.assertEqual(
                [str(self.sudo.resolve()), "-n", "--", str(self.nginx.resolve()), "-T"],
                command,
            )
            return subprocess.CompletedProcess(
                command,
                returncode,
                stdout=config.encode("utf-8"),
                stderr=b"nginx: configuration file syntax is ok\n",
            )

        return run

    def test_unique_tls_server_and_exact_resolved_root_pass(self) -> None:
        identity = CONTROLS.identify_nginx_document_root(
            self.config(), expected_document_root=self.expected_document_root
        )
        self.assertEqual(1, identity["matching_tls_server_count"])
        self.assertEqual(str(self.expected_document_root.resolve()), identity["resolved_document_root"])
        self.assertEqual(2, len(identity["listen_directives"]))
        route = identity["php_index_route"]
        self.assertEqual("/index.php", route["request_uri"])
        self.assertEqual(["~", r"\.php$"], route["location_selector"])
        self.assertEqual(
            "unix:/run/php/php8.2-fpm.sock",
            route["fastcgi_pass"],
        )
        self.assertEqual("/run/php/php8.2-fpm.sock", route["fpm_socket"])
        self.assertEqual(
            "$document_root$fastcgi_script_name",
            route["script_filename_expression"],
        )
        self.assertEqual(
            str((self.expected_document_root / "index.php").resolve()),
            route["resolved_script_filename"],
        )
        self.assertRegex(route["location_block_sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(route["route_identity_sha256"], r"^[a-f0-9]{64}$")

    def test_fpm_socket_mismatch_is_rejected(self) -> None:
        mutations = (
            "unix:/run/php/php8.3-fpm.sock",
            "127.0.0.1:9000",
        )
        for replacement in mutations:
            with self.subTest(replacement=replacement), self.assertRaisesRegex(
                CONTROLS.EnvironmentControlError,
                "reviewed PHP-FPM socket",
            ):
                CONTROLS.identify_nginx_document_root(
                    self.config().replace(
                        "unix:/run/php/php8.2-fpm.sock",
                        replacement,
                    ),
                    expected_document_root=self.expected_document_root,
                )

    def test_script_filename_mismatch_or_unknown_variable_is_rejected(self) -> None:
        mutations = (
            "$document_root/not-index.php",
            "$document_root$request_uri",
        )
        for replacement in mutations:
            with self.subTest(replacement=replacement), self.assertRaises(
                CONTROLS.EnvironmentControlError
            ):
                CONTROLS.identify_nginx_document_root(
                    self.config().replace(
                        "$document_root$fastcgi_script_name",
                        replacement,
                    ),
                    expected_document_root=self.expected_document_root,
                )

    def test_missing_or_duplicate_php_route_directives_are_rejected(self) -> None:
        mutations = (
            self.config().replace(
                "fastcgi_pass unix:/run/php/php8.2-fpm.sock;",
                "# fastcgi_pass deliberately absent",
            ),
            self.config().replace(
                "fastcgi_pass unix:/run/php/php8.2-fpm.sock;",
                "fastcgi_pass unix:/run/php/php8.2-fpm.sock; "
                "fastcgi_pass unix:/run/php/php8.2-fpm.sock;",
            ),
            self.config().replace(
                "fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;",
                "# SCRIPT_FILENAME deliberately absent",
            ),
            self.config().replace("SCRIPT_FILENAME", "script_filename"),
            self.config().replace(
                "fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;",
                "fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name; "
                "fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;",
            ),
        )
        for config in mutations:
            with self.subTest(config=config), self.assertRaisesRegex(
                CONTROLS.EnvironmentControlError,
                "exactly one",
            ):
                CONTROLS.identify_nginx_document_root(
                    config,
                    expected_document_root=self.expected_document_root,
                )

    def test_effective_index_location_must_be_the_reviewed_php_handler(self) -> None:
        exact_override = self.config().replace(
            "location / {",
            "location = /index.php { return 200; } location / {",
        )
        preferred_prefix = self.config().replace("location / {", "location ^~ / {")
        first_regex_override = self.config().replace(
            "location ~ \\.php$ {",
            "location ~ ^/index\\.php$ { return 200; } location ~ \\.php$ {",
        )
        for config in (exact_override, preferred_prefix, first_regex_override):
            with self.subTest(config=config), self.assertRaisesRegex(
                CONTROLS.EnvironmentControlError,
                "exactly one fastcgi_pass",
            ):
                CONTROLS.identify_nginx_document_root(
                    config,
                    expected_document_root=self.expected_document_root,
                )

    def test_duplicate_tls_server_is_rejected(self) -> None:
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "exactly one"):
            CONTROLS.identify_nginx_document_root(
                self.config(duplicate_tls=True),
                expected_document_root=self.expected_document_root,
            )

    def test_wrong_or_variable_document_root_is_rejected(self) -> None:
        wrong = self.root / "wrong/public"
        wrong.mkdir(parents=True)
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "differs"):
            CONTROLS.identify_nginx_document_root(
                self.config(root=wrong), expected_document_root=self.expected_document_root
            )
        variable_config = self.config().replace(
            str(self.expected_document_root), "$application_root/public"
        )
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "fixed absolute"):
            CONTROLS.identify_nginx_document_root(
                variable_config, expected_document_root=self.expected_document_root
            )

    def test_missing_server_level_document_root_is_rejected(self) -> None:
        config = self.config().replace(
            f'root "{self.expected_document_root}";',
            "# reviewed root deliberately absent",
        )
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "exactly one document root"):
            CONTROLS.identify_nginx_document_root(
                config, expected_document_root=self.expected_document_root
            )

    def test_nested_root_alias_and_unexpanded_include_are_rejected(self) -> None:
        replacements = (
            ("location / {", "location / { root /srv/wrong;"),
            ("location / {", "location / { alias /srv/wrong/;"),
            ("location / {", "location / { include /etc/nginx/private-root.conf;"),
        )
        for needle, replacement in replacements:
            with self.subTest(replacement=replacement), self.assertRaisesRegex(
                CONTROLS.EnvironmentControlError,
                "included, aliased, or nested",
            ):
                CONTROLS.identify_nginx_document_root(
                    self.config().replace(needle, replacement),
                    expected_document_root=self.expected_document_root,
                )

    def test_tls_must_be_on_the_same_loopback_compatible_443_listener(self) -> None:
        split_tls = self.config().replace(
            "listen 443 ssl http2;",
            "listen 443; listen 8443 ssl;",
        ).replace("listen [::]:443 ssl http2;", "listen [::]:443;")
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "[Mm]atching TLS server"):
            CONTROLS.identify_nginx_document_root(
                split_tls,
                expected_document_root=self.expected_document_root,
            )
        remote_only = self.config().replace(
            "listen 443 ssl http2;",
            "listen 192.0.2.20:443 ssl http2;",
        )
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "loopback origin"):
            CONTROLS.identify_nginx_document_root(
                remote_only,
                expected_document_root=self.expected_document_root,
            )

    def test_nginx_dump_include_is_expanded_in_server_context(self) -> None:
        main = """
        events {}
        http { include /etc/nginx/sites-enabled/*; }
        """
        site = self.config().replace(
            "http { include /etc/nginx/sites-enabled/*; }",
            "",
        ).replace(
            "location / {",
            "location / { include /etc/nginx/snippets/root-override.conf;",
        )
        dump = (
            "# configuration file /etc/nginx/nginx.conf:\n"
            + main
            + "\n# configuration file /etc/nginx/sites-enabled/buy-dtf:\n"
            + site
            + "\n# configuration file /etc/nginx/snippets/root-override.conf:\n"
            + "root /srv/wrong;\n"
        )
        with self.assertRaisesRegex(CONTROLS.EnvironmentControlError, "nested"):
            CONTROLS.identify_nginx_document_root(
                dump,
                expected_document_root=self.expected_document_root,
            )
        safe_dump = dump.replace("root /srv/wrong;", "fastcgi_param SCRIPT_FILENAME fixture;")
        identity = CONTROLS.identify_nginx_document_root(
            safe_dump,
            expected_document_root=self.expected_document_root,
        )
        self.assertTrue(identity["origin_loopback_compatible"])
        self.assertEqual("127.0.0.1:443", identity["origin_probe_address"])

    def test_php_route_directives_from_expanded_include_are_bound(self) -> None:
        main = """
        events {}
        http { include /etc/nginx/sites-enabled/*; }
        """
        site = self.config().replace(
            "http { include /etc/nginx/sites-enabled/*; }",
            "",
        ).replace(
            "fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;\n"
            "                fastcgi_pass unix:/run/php/php8.2-fpm.sock;",
            "include /etc/nginx/snippets/buy-dtf-php-route.conf;",
        )
        dump = (
            "# configuration file /etc/nginx/nginx.conf:\n"
            + main
            + "\n# configuration file /etc/nginx/sites-enabled/buy-dtf:\n"
            + site
            + "\n# configuration file /etc/nginx/snippets/buy-dtf-php-route.conf:\n"
            + "fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;\n"
            + "fastcgi_pass unix:/run/php/php8.2-fpm.sock;\n"
        )
        identity = CONTROLS.identify_nginx_document_root(
            dump,
            expected_document_root=self.expected_document_root,
        )
        self.assertEqual(
            "unix:/run/php/php8.2-fpm.sock",
            identity["php_index_route"]["fastcgi_pass"],
        )
        self.assertEqual(
            str((self.expected_document_root / "index.php").resolve()),
            identity["php_index_route"]["resolved_script_filename"],
        )

    def test_capture_is_private_and_summary_does_not_copy_raw_configuration(self) -> None:
        config = self.config()
        with patch.dict(
            os.environ,
            {
                "LD_PRELOAD": "/tmp/hostile.so",
                "SUDO_ASKPASS": "/tmp/hostile-askpass",
                "NGINX": "/tmp/hostile-nginx",
            },
            clear=False,
        ):
            result = CONTROLS.capture_nginx_identity(
                self.evidence,
                sudo_executable=self.sudo,
                nginx_executable=self.nginx,
                expected_document_root=self.expected_document_root,
                expected_executable_uid=os.geteuid(),
                expected_executable_gid=os.getegid(),
                command_runner=self.completed(config),
            )
        raw_path = Path(result["raw_capture"]["path"])
        summary_path = Path(result["summary_capture"]["path"])
        self.assertEqual(0o600, stat.S_IMODE(raw_path.stat().st_mode))
        self.assertEqual(0o600, stat.S_IMODE(summary_path.stat().st_mode))
        self.assertIn("SUPER_SECRET_DO_NOT_COPY", raw_path.read_text(encoding="utf-8"))
        summary_text = summary_path.read_text(encoding="utf-8")
        self.assertNotIn("SUPER_SECRET_DO_NOT_COPY", summary_text)
        summary = json.loads(summary_text)
        self.assertEqual(CONTROLS.NGINX_IDENTITY_ARTIFACT, summary["artifact"])
        self.assertEqual("sudo-noninteractive-exact-nginx-T", summary["privilege_boundary"])
        self.assertEqual("1.24.0", summary["nginx_version"])
        self.assertEqual(self.sudo.resolve().as_posix(), Path(summary["sudo_executable"]).as_posix())
        self.assertEqual("private-do-not-commit", summary["raw_capture"]["classification"])
        self.assertEqual(CONTROLS.sha256_bytes(config.encode()), summary["effective_config_sha256"])

    def test_capture_refuses_overwrite_and_preserves_first_evidence(self) -> None:
        runner = self.completed(self.config())
        CONTROLS.capture_nginx_identity(
            self.evidence,
            sudo_executable=self.sudo,
            nginx_executable=self.nginx,
            expected_document_root=self.expected_document_root,
            expected_executable_uid=os.geteuid(),
            expected_executable_gid=os.getegid(),
            command_runner=runner,
        )
        raw = self.evidence / "nginx-effective-config.private.txt"
        before = raw.read_bytes()
        with self.assertRaises(FileExistsError):
            CONTROLS.capture_nginx_identity(
                self.evidence,
                sudo_executable=self.sudo,
                nginx_executable=self.nginx,
                expected_document_root=self.expected_document_root,
                expected_executable_uid=os.geteuid(),
                expected_executable_gid=os.getegid(),
                command_runner=runner,
            )
        self.assertEqual(before, raw.read_bytes())

    def test_noninteractive_sudo_failure_is_fail_closed_with_private_raw_capture(self) -> None:
        with self.assertRaisesRegex(
            CONTROLS.EnvironmentControlError,
            "effective-config capture failed",
        ):
            CONTROLS.capture_nginx_identity(
                self.evidence,
                sudo_executable=self.sudo,
                nginx_executable=self.nginx,
                expected_document_root=self.expected_document_root,
                expected_executable_uid=os.geteuid(),
                expected_executable_gid=os.getegid(),
                command_runner=self.completed("", returncode=1),
            )
        raw = self.evidence / "nginx-effective-config.private.txt"
        self.assertTrue(raw.is_file())
        self.assertEqual(0o600, stat.S_IMODE(raw.stat().st_mode))
        self.assertFalse((self.evidence / "nginx-document-root-summary.json").exists())


if __name__ == "__main__":
    unittest.main()
