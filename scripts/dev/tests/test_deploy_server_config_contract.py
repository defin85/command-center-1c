from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]


class DeployServerConfigContractTests(unittest.TestCase):
    def test_native_activate_restarts_optional_python_runtimes(self) -> None:
        script_text = (ROOT / "scripts/deploy/native-activate.sh").read_text(encoding="utf-8")

        self.assertIn("cc1c-event-subscriber.service", script_text)
        self.assertIn("cc1c-pool-outbox-dispatcher.service", script_text)

    def test_install_server_deployer_switches_server_to_native_settings(self) -> None:
        script_text = (ROOT / "scripts/deploy/install-server-deployer.sh").read_text(encoding="utf-8")

        self.assertIn("DJANGO_SETTINGS_MODULE=config.settings.native", script_text)
        self.assertNotIn("config.settings.development", script_text)

    def test_install_server_deployer_manages_disk_guard_files(self) -> None:
        script_text = (ROOT / "scripts/deploy/install-server-deployer.sh").read_text(encoding="utf-8")

        self.assertIn("99-cc1c-disk-guard.conf", script_text)
        self.assertIn("logrotate.timer.d/override.conf", script_text)
        self.assertIn("cc1c-logging.xml", script_text)

    def test_native_settings_disable_tls_redirect_but_keep_production_base(self) -> None:
        settings_text = (ROOT / "orchestrator/config/settings/native.py").read_text(encoding="utf-8")

        self.assertIn("from .production import *", settings_text)
        self.assertIn("SECURE_SSL_REDIRECT = False", settings_text)
        self.assertIn("SESSION_COOKIE_SECURE = False", settings_text)
        self.assertIn("CSRF_COOKIE_SECURE = False", settings_text)


if __name__ == "__main__":
    unittest.main()
