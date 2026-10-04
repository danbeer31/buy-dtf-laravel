#!/usr/bin/env python3
"""Source-mutation regressions for the unchanged reviewed v4 gate primitive."""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import production_alpha_gate_controls as controls
import production_alpha_transparency_deploy as runner
import laravel_dependency_gate as gate
import test_laravel_dependency_gate as gate_tests

class SourceGateControlsTest(unittest.TestCase):
    def frozen(self):
        return copy.deepcopy(controls.frozen_envelope()['fpm_opcache'])

    def test_reviewed_controls_and_live_dependency_baseline_are_bound(self):
        envelope=controls.frozen_envelope()
        self.assertEqual('12.69.1',envelope['laravel_version'])
        self.assertEqual(7,envelope['fpm_opcache']['policy']['minimum_wait_seconds'])
        for name,digest in runner.CONTROL_FILES.items():
            self.assertEqual(digest,runner.sha256_file(Path(runner.__file__).with_name(name)))
        self.assertEqual(10,len(controls.CANDIDATE_VENDOR_EXECUTABLE_PATHS))
        self.assertEqual(envelope['vendor']['executable_allowlist_sha256'],controls.executable_allowlist_sha256())

    def fixture(self,directory):
        app=Path(directory)/'app';app.mkdir();(app/'public').mkdir()
        front=app/'public/index.php';front.write_bytes(b'<?php echo "original";')
        backup=Path(directory)/'front-controller-before.php';backup.write_bytes(front.read_bytes());os.chmod(backup,0o600)
        state={'state_directory':directory,'source_install_started':False,'fpm_opcache':self.frozen(),'release_receipt_sha256':'b'*64,'front_controller_backup':str(backup),'front_controller_backup_sha256':controls.sha256_file(backup),'front_controller_transitions':[]}
        state_path=Path(directory)/'state.json';controls.write_state(state_path,state)
        return app,front,state,state_path

    def checkpoint(self,state,path):
        with mock.patch.object(controls,'probe_fpm_opcache',return_value=self.frozen()):
            controls.record_fpm_opcache_before_mutation(state,path)
        state['source_install_started']=True;controls.write_state(path,state)

    def test_pre_mutation_timeout_refuses_installation_without_overwriting_original(self):
        with tempfile.TemporaryDirectory() as directory:
            app,front,state,path=self.fixture(directory);before=front.read_bytes()
            with mock.patch.object(controls,'APP_ROOT',app),mock.patch.object(controls,'FRONT_CONTROLLER',front),mock.patch.object(controls,'probe_fpm_opcache',side_effect=controls.FpmProbeUnavailable('timeout')):
                with self.assertRaises(controls.FpmProbeUnavailable):controls.gate_context(state,path)
            self.assertEqual(before,front.read_bytes())

    def test_post_mutation_timeout_with_original_uses_exact_receipt_bound_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            app,front,state,path=self.fixture(directory);self.checkpoint(state,path)
            with mock.patch.object(controls,'APP_ROOT',app),mock.patch.object(controls,'FRONT_CONTROLLER',front),mock.patch.object(controls,'EXPECTED_FRONT_CONTROLLER_SHA256',controls.sha256_file(front)),mock.patch.object(gate,'file_identity',return_value={'sha256':controls.sha256_file(front),'metadata':gate.reviewed_front_controller_metadata()}),mock.patch.object(controls,'probe_fpm_opcache',side_effect=controls.FpmProbeUnavailable('timeout')):
                context=controls.post_mutation_emergency_gate_context(state,path)
            self.assertEqual(7,context.opcache_policy['minimum_wait_seconds'])
            self.assertEqual('exact_original_gate_install_with_frozen_policy',state['post_mutation_emergency_fpm_fallbacks'][0]['status'])
            self.assertEqual(state,json.loads(path.read_text()))

    def test_missing_malformed_or_tampered_frozen_checkpoint_is_rejected(self):
        for case in ['missing','bad_probe','bad_policy','receipt_hash','receipt_mode','checkpoint']:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as directory:
                app,front,state,path=self.fixture(directory);self.checkpoint(state,path)
                if case=='missing':state.pop('fpm_opcache')
                elif case=='bad_probe':state['fpm_opcache']['probe']['sapi']='cli'
                elif case=='bad_policy':state['fpm_opcache']['policy']['minimum_wait_seconds']=0
                elif case=='receipt_hash':state['fpm_opcache_before_mutation_receipt']['sha256']='0'*64
                elif case=='receipt_mode':os.chmod(Path(state['fpm_opcache_before_mutation_receipt']['path']),0o644)
                elif case=='checkpoint':state['fpm_opcache_before_mutation']['exact_match']=False
                with self.assertRaises(controls.DeploymentError):controls.validate_post_mutation_frozen_fpm_opcache(state,path)

    def test_valid_reachable_but_changed_fpm_settings_do_not_use_timeout_fallback(self):
        current=self.frozen();changed=copy.deepcopy(current);changed['probe']['directives']['opcache.revalidate_freq']['normalized']=20
        with mock.patch.object(controls,'probe_fpm_opcache',return_value=changed):
            with self.assertRaises(controls.DeploymentError):controls.require_frozen_fpm_opcache(current)

    def test_frozen_validation_has_explicit_errors_under_python_optimization(self):
        import inspect
        self.assertNotIn('assert ',inspect.getsource(controls.validate_frozen_fpm_opcache_record))
        with self.assertRaises(controls.DeploymentError):controls.validate_frozen_fpm_opcache_record(None)

    def test_source_marker_is_the_only_emergency_mutation_boundary(self):
        self.assertFalse(controls.mutation_has_started({'dependency_mutation_started':True}))
        self.assertTrue(controls.mutation_has_started({'source_install_started':True}))
        with tempfile.TemporaryDirectory() as directory:
            _,_,state,path=self.fixture(directory)
            with self.assertRaises(controls.DeploymentError):controls.validate_post_mutation_frozen_fpm_opcache(state,path)

    def test_nginx_root_socket_and_script_filename_mismatch_are_rejected(self):
        config='''events {} http { server { listen 443 ssl; server_name buy-dtf.com; root /var/www/buy-dtf/public; location / { try_files $uri $uri/ /index.php?$query_string; } location ~ \\.php$ { fastcgi_pass unix:/run/php/php8.2-fpm.sock; fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name; } } }'''
        with tempfile.TemporaryDirectory() as directory:
            expected_root=Path(directory);(expected_root/'index.php').write_text('<?php')
            config=config.replace('/var/www/buy-dtf/public',directory)
            expected=controls.environment_controls.identify_nginx_document_root(config,expected_document_root=expected_root)
            self.assertEqual(str(expected_root/'index.php'),expected['php_index_route']['resolved_script_filename'])
            for bad in [config.replace('/run/php/php8.2-fpm.sock','/run/php/wrong.sock'),config.replace('$document_root$fastcgi_script_name','/wrong/index.php'),config.replace(directory,'/wrong/root')]:
                with self.subTest(config=bad),self.assertRaises(controls.environment_controls.EnvironmentControlError):controls.environment_controls.identify_nginx_document_root(bad,expected_document_root=expected_root)

    def test_rollback_containment_uses_offline_emergency_policy_before_source_restore(self):
        import inspect
        code=inspect.getsource(runner.rollback_operation)
        self.assertLess(code.index('establish_rollback_containment('),code.index('restore_sources('))
        self.assertNotIn('dependency_gate.dependency_mutation_has_started',inspect.getsource(runner.establish_rollback_containment))
        self.assertIn('mutation_started=mutation_has_started',inspect.getsource(runner.establish_rollback_containment))

    def test_recovery_decision_does_not_require_live_fpm(self):
        import inspect
        self.assertNotIn('probe_fpm_opcache',inspect.getsource(runner.front_controller_recovery_required))


    def test_candidate_and_opcache_fpm_probes_cannot_inherit_ini_override_environment(self):
        import inspect
        self.assertNotIn('dict(os.environ)',inspect.getsource(runner.candidate_fpm_probe))
        self.assertIn('fpm_fastcgi_environment',inspect.getsource(runner.candidate_fpm_probe))
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'probe.php';script.write_text('<?php')
            with mock.patch.dict(os.environ,{'PHP_VALUE':'opcache.enable=0','PHP_ADMIN_VALUE':'opcache.validate_timestamps=0'}):
                environment=controls.fpm_fastcgi_environment(script,'/probe.php')
            self.assertNotIn('PHP_VALUE',environment);self.assertNotIn('PHP_ADMIN_VALUE',environment)

    def test_shared_primitive_rehearses_interrupted_wait_and_post_mutation_http_failure(self):
        # Accepted complete unit tests execute the shared primitive, with the
        # same predicate interface passed by the source runner.
        for name in ['test_interrupted_emergency_containment_wait_restarts_full_wait','test_post_mutation_public_failure_retains_gate_and_permits_rollback','test_wait_is_shared_by_install_reassert_containment_restore_and_recovery']:
            result=unittest.TestResult();gate_tests.LaravelDependencyGateUnitTest(name).run(result)
            self.assertTrue(result.wasSuccessful(),result.errors+result.failures)

if __name__=='__main__':unittest.main(verbosity=2)