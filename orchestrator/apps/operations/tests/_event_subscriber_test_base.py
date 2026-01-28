from unittest.mock import patch

from django.test import TestCase, override_settings


@override_settings(
    REDIS_HOST="localhost",
    REDIS_PORT=6379,
)
class EventSubscriberBaseTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._close_patcher = patch("apps.operations.event_subscriber.runtime.close_old_connections")
        cls._close_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._close_patcher.stop()
        super().tearDownClass()

