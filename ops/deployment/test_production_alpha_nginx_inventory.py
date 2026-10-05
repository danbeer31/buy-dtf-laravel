#!/usr/bin/env python3
"""Exercise the real verifier and Phase 0 with an isolated 18-file inventory.

The approved path/symlink inventory is replayed with synthetic configuration
bytes. Filesystem names are mapped into a disposable directory; only the Dan
writability result and external process/runtime dependencies are simulated.
No production paths, nginx commands, services, or release directories are used.
"""
from contextlib import ExitStack, contextmanager
import copy
import glob
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import production_alpha_gate_controls as controls
import production_alpha_transparency_deploy as runner
import rehearse_production_alpha_transparency as rehearsal


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "ops/evidence/production-alpha-transparency-source-only-v5-scheduler-20261005"
SSL_INCLUDE = "/etc/letsencrypt/options-ssl-nginx.conf"


class NginxInventoryFixture:
    def __init__(self, root):
        self.root = root
        self.envelope = copy.deepcopy(controls.frozen_envelope())
        self.inventory = self.envelope["nginx"]["current_files"]
        self.names = [record["path"] for record in self.inventory]
        self.writable_paths = set()
        self.services = b"Id=nginx.service\nMainPID=123\nActiveState=active\n"
        self.envelope["services_sha256"] = controls.sha256_bytes(self.services)
        self.capture_name = "/private-evidence/nginx.private.txt"
        self.envelope["accepted_nginx_dump_path"] = self.capture_name
        for record in self.inventory:
            target = self.host(record["resolved_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"# synthetic include\n")
            target.chmod(0o644)
            if record["resolved_path"] != record["path"]:
                alias = self.host(record["path"])
                alias.parent.mkdir(parents=True, exist_ok=True)
                alias.symlink_to(os.path.relpath(target, alias.parent))
        self.write("/etc/nginx/nginx.conf", b"include /etc/nginx/modules-enabled/*.conf;\nevents {}\nhttp {\n include mime.types;\n include /etc/nginx/sites-enabled/*;\n}\n")
        self.write("/etc/nginx/sites-enabled/buy-dtf", b"server {\n listen 443 ssl;\n server_name buy-dtf.com;\n root /var/www/buy-dtf/public;\n include /etc/letsencrypt/options-ssl-nginx.conf;\n location / { try_files $uri $uri/ /index.php?$query_string; }\n location ~ \\.php$ {\n  include /etc/nginx/snippets/fastcgi-php.conf;\n  fastcgi_pass unix:/run/php/php8.2-fpm.sock;\n }\n}\n")
        self.write(SSL_INCLUDE, b"ssl_protocols TLSv1.2 TLSv1.3;\n")
        self.write("/etc/nginx/snippets/fastcgi-php.conf", b"include /etc/nginx/fastcgi.conf;\n")
        self.write("/etc/nginx/fastcgi.conf", b"fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;\n")
        self.write("/etc/nginx/sites-enabled/shopnltest.com", b"server {\n listen 80;\n server_name synthetic.example;\n include /etc/nginx/fastcgi_params;\n}\n")
        self.app = self.host("/var/www/buy-dtf")
        self.front = self.app / "public/index.php"
        self.front.parent.mkdir(parents=True)
        self.front.write_bytes(b"<?php echo 'synthetic original';\n")
        self.front.chmod(0o644)
        os.chown(self.app, 1000, 1000)
        os.chown(self.front, 1000, 1000)
        self.release_root = root / "must-not-create-release"
        self.rebuild_capture()

    def host(self, name):
        return self.root / str(name).lstrip("/")

    def write(self, name, content):
        self.host(name).write_bytes(content)

    def rebuild_capture(self, *, extra_names=()):
        raw = b""
        for name in [*self.names, *extra_names]:
            data = self.host(name).read_bytes()
            raw += b"# configuration file " + name.encode() + b":\n" + data + b"\n"
        for record in self.inventory:
            data = self.host(record["path"]).read_bytes()
            record.update(bytes=len(data), sha256=controls.sha256_bytes(data))
        capture = self.host(self.capture_name)
        capture.parent.mkdir(parents=True, exist_ok=True)
        capture.write_bytes(raw)
        capture.chmod(0o600)
        self.envelope["nginx"]["accepted_stable_identity"]["effective_config_sha256"] = controls.sha256_bytes(raw)
        return raw

    @contextmanager
    def verifier_environment(self):
        fixture = self
        original_glob = glob.glob
        original_access = os.access
        identify = controls.environment_controls.identify_nginx_document_root

        class MappedPath(type(Path())):
            def stat(self, *, follow_symlinks=True):
                return fixture.host(self).stat(follow_symlinks=follow_symlinks)

            def lstat(self):
                return fixture.host(self).lstat()

            def read_bytes(self):
                return fixture.host(self).read_bytes()

            def resolve(self, strict=False):
                target = fixture.host(self).resolve(strict=strict)
                return MappedPath("/" + target.relative_to(fixture.root).as_posix())

        def access(path, mode):
            if isinstance(path, MappedPath):
                return str(path) in fixture.writable_paths if mode == os.W_OK else original_access(fixture.host(path), mode)
            return original_access(path, mode)

        def expand(pattern):
            return ["/" + Path(name).relative_to(fixture.root).as_posix() for name in original_glob(str(fixture.host(pattern)))]

        def route(text):
            return identify(text, expected_document_root=MappedPath("/var/www/buy-dtf/public"))

        def service_command(argv, **kwargs):
            if argv[:3] != ["/usr/bin/systemctl", "show", "nginx.service"]:
                raise AssertionError("Unexpected external process in verifier regression")
            return subprocess.CompletedProcess(argv, 0, fixture.services, b"")

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(controls, "Path", MappedPath))
            stack.enter_context(mock.patch.object(controls.environment_controls, "Path", MappedPath))
            stack.enter_context(mock.patch.object(controls, "frozen_envelope", return_value=self.envelope))
            stack.enter_context(mock.patch.object(controls.os, "access", side_effect=access))
            stack.enter_context(mock.patch.object(controls.glob, "glob", side_effect=expand))
            stack.enter_context(mock.patch.object(controls.subprocess, "run", side_effect=service_command))
            stack.enter_context(mock.patch.object(controls.environment_controls, "identify_nginx_document_root", side_effect=route))
            raw = self.host(self.capture_name).read_bytes()
            self.envelope["nginx"]["accepted_stable_identity"]["document_root_identity"] = route(raw.decode())
            yield

    @contextmanager
    def phase0_environment(self):
        snapshot = rehearsal.runtime_snapshot()
        with self.verifier_environment(), ExitStack() as stack:
            for name, value in {
                "APP_ROOT": self.app,
                "FRONT_CONTROLLER": self.front,
                "EXPECTED_APP_DEVICE": self.app.stat().st_dev,
                "EXPECTED_FRONT_CONTROLLER_SHA256": controls.sha256_file(self.front),
                "RELEASE_ROOT": self.release_root,
                "LARAVEL_MAINTENANCE_FILE": self.app / "storage/framework/down",
                "FPM_SOCKET": mock.Mock(is_socket=mock.Mock(return_value=True)),
            }.items():
                stack.enter_context(mock.patch.object(runner, name, value))
            stack.enter_context(mock.patch.object(controls, "APP_ROOT", self.app))
            stack.enter_context(mock.patch.object(controls, "FRONT_CONTROLLER", self.front))
            stack.enter_context(mock.patch.object(runner.os, "geteuid", return_value=1000))
            stack.enter_context(mock.patch.object(runner.sys, "version_info", (3, 10, 12)))
            for name, value in {
                "lock_is_free": True, "scoped_processes": [],
                "full_source_identity": self.envelope["source"],
                "live_manifest_snapshot": {"sha256": runner.EXPECTED_PRE_SOURCE_CAS_SHA256},
                "dependency_identity": {"composer_lock_sha256": runner.EXPECTED_COMPOSER_LOCK_SHA256},
                "runtime_probe_memory": snapshot,
                "runtime_probe": (snapshot, {"status": "synthetic_read_only_runtime"}),
                "health_snapshot": {"status": "synthetic_normal_health"},
                "active_fpm_connections": [],
            }.items():
                stack.enter_context(mock.patch.object(runner, name, return_value=value))
            stack.enter_context(mock.patch.object(controls, "require_frozen_fpm_opcache", return_value=self.envelope["fpm_opcache"]))
            stack.enter_context(mock.patch.object(controls, "require_configuration_identity", return_value=self.envelope["configuration_sha256"]))
            stack.enter_context(mock.patch.object(runner.shutil, "disk_usage", return_value=SimpleNamespace(total=8 * 1024**3, used=1, free=7 * 1024**3)))
            yield


@unittest.skipUnless(os.geteuid() == 0, "root-owned disposable WSL inventory required")
class ApprovedNginxInventoryTest(unittest.TestCase):
    def inputs(self):
        return {
            "archive": ROOT / "storage/app/private/operations/production-alpha-transparency-source-only-package-20261002/production-alpha-transparency-b02fce32.tar",
            "manifest": EVIDENCE / "APPLICATION_MANIFEST.json",
            "helper": ROOT / "ops/deployment/production_alpha_transparency_runtime_probe.php",
            "log_guard": ROOT / "ops/deployment/laravel_log_guard.py",
            "approval_token": runner.STAGE_APPROVAL_TOKEN,
        }

    def test_exact_approved_inventory_including_letsencrypt_passes_real_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = NginxInventoryFixture(Path(directory))
            self.assertEqual(18, len(fixture.names))
            self.assertIn(SSL_INCLUDE, fixture.names)
            with fixture.verifier_environment():
                result = controls.verify_read_only_nginx()
            self.assertEqual("pass", result["status"])
            self.assertEqual(set(fixture.names), {record["path"] for record in result["files"]})
            self.assertEqual(controls.sha256_bytes(controls.dependency_gate.canonical_bytes(fixture.inventory)), result["approved_include_inventory_sha256"])

    def test_approved_inventory_passes_both_real_phase0_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = NginxInventoryFixture(Path(directory))
            with fixture.phase0_environment():
                guard = runner.preflight_guard(self.inputs()["helper"], [])
                preflight = runner.production_preflight(helper=self.inputs()["helper"], manifest_rows=[], evidence_directory=Path(directory), prefix="phase0")
            for result in (guard, preflight):
                self.assertEqual("pass", result["status"])
                self.assertEqual(18, len(result["controls"]["nginx"]["files"]))
            self.assertFalse(fixture.release_root.exists())

    def test_drift_fails_real_phase0_and_stage_before_release_creation(self):
        cases = {
            "unapproved_nginx_include": "Unexpected nginx include path",
            "unapproved_letsencrypt_include": "Unexpected nginx include path",
            "changed_bytes": "Approved nginx include bytes differ",
            "unsafe_file_mode": "no longer administrator-controlled",
            "unsafe_parent_mode": "no longer administrator-controlled",
            "unsafe_parent_owner": "no longer administrator-controlled",
            "unsafe_resolved_parent_mode": "no longer administrator-controlled",
            "dan_writable": "no longer administrator-controlled",
            "changed_safe_mode": "Approved nginx include metadata differs",
            "changed_symlink_target": "Approved nginx include resolved target differs",
            "unexpected_glob_include": "Current nginx include bytes/set differ",
            "missing_capture": "Accepted nginx evidence is missing or unreadable",
            "changed_capture": "Control file identity differs",
            "unsafe_capture_mode": "not private mode 0600",
            "missing_include": "Approved nginx include is missing or unreadable",
            "changed_services": "Effective service identity changed",
            "changed_socket": "socket",
            "changed_script_filename": "SCRIPT_FILENAME",
        }
        for case, phrase in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                fixture = NginxInventoryFixture(Path(directory))
                with fixture.phase0_environment():
                    if case.startswith("unapproved_"):
                        name = "/etc/nginx/unapproved.conf" if case == "unapproved_nginx_include" else "/etc/letsencrypt/unapproved.conf"
                        fixture.host(name).write_bytes(b"# unapproved\n")
                        fixture.rebuild_capture(extra_names=[name])
                    elif case == "changed_bytes": fixture.host(SSL_INCLUDE).write_bytes(b"# changed\n")
                    elif case == "unsafe_file_mode": fixture.host(SSL_INCLUDE).chmod(0o666)
                    elif case == "unsafe_parent_mode": fixture.host("/etc/letsencrypt").chmod(0o777)
                    elif case == "unsafe_parent_owner": os.chown(fixture.host("/etc/letsencrypt"), 1000, 1000)
                    elif case == "unsafe_resolved_parent_mode": fixture.host("/usr/share/nginx/modules-available").chmod(0o777)
                    elif case == "dan_writable": fixture.writable_paths.add(SSL_INCLUDE)
                    elif case == "changed_safe_mode": fixture.host(SSL_INCLUDE).chmod(0o600)
                    elif case == "changed_symlink_target":
                        alias = fixture.host("/etc/nginx/sites-enabled/buy-dtf")
                        target = fixture.host("/etc/nginx/sites-available/unapproved")
                        target.write_bytes(alias.read_bytes()); alias.unlink(); alias.symlink_to(target)
                    elif case == "unexpected_glob_include": fixture.host("/etc/nginx/sites-enabled/unapproved").write_bytes(b"# extra\n")
                    elif case == "missing_capture": fixture.host(fixture.capture_name).unlink()
                    elif case == "changed_capture": fixture.host(fixture.capture_name).write_bytes(b"# altered evidence\n")
                    elif case == "unsafe_capture_mode": fixture.host(fixture.capture_name).chmod(0o644)
                    elif case == "missing_include": fixture.host(SSL_INCLUDE).unlink()
                    elif case == "changed_services": fixture.services += b"NRestarts=1\n"
                    elif case == "changed_socket":
                        path = fixture.host("/etc/nginx/sites-enabled/buy-dtf")
                        path.write_bytes(path.read_bytes().replace(b"/run/php/php8.2-fpm.sock", b"/run/php/wrong.sock"))
                        fixture.rebuild_capture()
                    elif case == "changed_script_filename":
                        fixture.write("/etc/nginx/fastcgi.conf", b"fastcgi_param SCRIPT_FILENAME /wrong/index.php;\n")
                        fixture.rebuild_capture()
                    with self.assertRaisesRegex(controls.DeploymentError, phrase): controls.verify_read_only_nginx()
                    with self.assertRaisesRegex(runner.DeploymentError, phrase): runner.preflight_guard(self.inputs()["helper"], [])
                    with self.assertRaisesRegex(runner.DeploymentError, phrase): runner.production_preflight(helper=self.inputs()["helper"], manifest_rows=[], evidence_directory=Path(directory), prefix="phase0")
                    with mock.patch.object(runner, "extract_candidate") as extract, mock.patch.object(runner, "atomic_copy") as copy_file:
                        with self.assertRaisesRegex(runner.DeploymentError, phrase): runner.stage_release(**self.inputs())
                        extract.assert_not_called(); copy_file.assert_not_called()
                    self.assertFalse(fixture.release_root.exists())

    def test_missing_duplicate_or_changed_inventory_fails_closed(self):
        for case in ["missing", "too_short", "duplicate", "missing_root"]:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                fixture = NginxInventoryFixture(Path(directory))
                with fixture.verifier_environment():
                    if case == "missing": fixture.envelope["nginx"].pop("current_files")
                    elif case == "too_short": fixture.inventory.pop()
                    elif case == "duplicate": fixture.inventory[-1] = fixture.inventory[0]
                    elif case == "missing_root": fixture.inventory[0]["path"] = "/etc/nginx/unapproved.conf"
                    with self.assertRaises(controls.DeploymentError): controls.verify_read_only_nginx()


if __name__ == "__main__":
    unittest.main(verbosity=2)
