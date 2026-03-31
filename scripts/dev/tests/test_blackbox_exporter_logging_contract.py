from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]


class BlackboxExporterLoggingContractTests(unittest.TestCase):
    def test_project_blackbox_unit_suppresses_exporter_stderr(self) -> None:
        unit_text = (ROOT / "infrastructure/systemd/blackbox-exporter.service").read_text(encoding="utf-8")

        self.assertIn("StandardError=null", unit_text)

    def test_native_monitoring_sync_installs_blackbox_override_for_known_units(self) -> None:
        sync_text = (ROOT / "scripts/dev/sync-native-monitoring.sh").read_text(encoding="utf-8")

        self.assertIn("blackbox-exporter.override.conf", sync_text)
        self.assertIn('override_dir="/etc/systemd/system/${service_name}.d"', sync_text)
        self.assertIn('override_dest="$override_dir/override.conf"', sync_text)
        self.assertIn('"blackbox-exporter.service"', sync_text)
        self.assertIn('"prometheus-blackbox-exporter.service"', sync_text)


if __name__ == "__main__":
    unittest.main()
