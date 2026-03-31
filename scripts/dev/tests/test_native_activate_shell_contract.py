from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]


class NativeActivateMonitoringSyncContractTests(unittest.TestCase):
    def test_native_activate_forces_native_monitoring_sync(self) -> None:
        script_text = (ROOT / "scripts/deploy/native-activate.sh").read_text(encoding="utf-8")

        self.assertIn(
            'USE_DOCKER=false CC1C_ENV_FILE="$ENV_FILE" "$RELEASE_DIR/scripts/dev/sync-native-monitoring.sh"',
            script_text,
        )


if __name__ == "__main__":
    unittest.main()
