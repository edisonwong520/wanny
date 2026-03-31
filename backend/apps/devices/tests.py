import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Account
from providers.models import PlatformAuth
from .models import DeviceDashboardState
from .services import DeviceDashboardService


class DeviceDashboardServiceTest(TestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="device-test@example.com",
            name="Device Test",
            password="pwd",
        )

    def test_get_dashboard_queues_bootstrap_when_empty(self):
        payload = DeviceDashboardService.get_dashboard(self.account)

        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["snapshot"]["has_snapshot"])
        self.assertTrue(payload["snapshot"]["pending_refresh"])
        self.assertEqual(payload["snapshot"]["rooms"], [])
        self.assertEqual(payload["snapshot"]["devices"], [])

        state = DeviceDashboardState.objects.get(account=self.account, key=DeviceDashboardService.state_key)
        self.assertEqual(state.requested_trigger, "bootstrap")
        self.assertIsNotNone(state.refresh_requested_at)
        self.assertIsNone(state.refreshed_at)

    def test_run_pending_refresh_persists_snapshot_and_clears_pending(self):
        DeviceDashboardService.request_refresh(self.account, trigger="manual")

        refreshed = DeviceDashboardService.run_pending_refresh(self.account, sync_interval_seconds=300)

        self.assertTrue(refreshed)
        payload = DeviceDashboardService.get_dashboard(self.account)
        self.assertTrue(payload["snapshot"]["has_snapshot"])
        self.assertFalse(payload["snapshot"]["pending_refresh"])
        self.assertGreater(len(payload["snapshot"]["rooms"]), 0)
        self.assertGreater(len(payload["snapshot"]["devices"]), 0)

        state = DeviceDashboardState.objects.get(account=self.account, key=DeviceDashboardService.state_key)
        self.assertEqual(state.last_trigger, "manual")
        self.assertEqual(state.requested_trigger, "")
        self.assertIsNone(state.refresh_requested_at)
        self.assertIsNotNone(state.refreshed_at)

    def test_get_dashboard_with_non_device_provider_auth_still_bootstraps(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="wechat",
            auth_payload={"token": "wx-token"},
            is_active=True,
        )

        payload = DeviceDashboardService.get_dashboard(self.account)

        self.assertFalse(payload["snapshot"]["has_snapshot"])
        self.assertTrue(payload["snapshot"]["pending_refresh"])

    def test_refresh_uses_home_assistant_snapshot_when_authorized(self):
        PlatformAuth.objects.create(
            account=self.account,
            platform_name="home_assistant",
            auth_payload={
                "base_url": "http://ha.local:8123",
                "access_token": "ha-token",
                "instance_name": "My Home",
            },
            is_active=True,
        )

        with patch(
            "devices.services.DeviceDashboardService._build_home_assistant_snapshot",
            return_value={
                "source": "home_assistant",
                "rooms": [
                    {
                        "id": "home_assistant:default",
                        "name": "My Home",
                        "climate": "",
                        "summary": "来自 Home Assistant 实例: My Home",
                        "sort_order": 10,
                    }
                ],
                "devices": [
                    {
                        "id": "home_assistant:light.living_room",
                        "room_id": "home_assistant:default",
                        "name": "客厅灯",
                        "category": "灯光",
                        "status": "attention",
                        "telemetry": "on",
                        "note": "Entity: light.living_room | Domain: light",
                        "capabilities": ["light"],
                        "last_seen": None,
                        "sort_order": 10,
                    }
                ],
                "anomalies": [],
                "rules": [],
            },
        ):
            payload = DeviceDashboardService.refresh(self.account, trigger="test")

        self.assertEqual(payload["snapshot"]["source"], "home_assistant")
        self.assertEqual(payload["snapshot"]["devices"][0]["name"], "客厅灯")

    def test_syncdevicesnapshot_command_refreshes_target_account(self):
        call_command("syncdevicesnapshot", "--email", self.account.email)

        state = DeviceDashboardState.objects.get(account=self.account, key=DeviceDashboardService.state_key)
        self.assertEqual(state.last_trigger, "command")
        self.assertIsNotNone(state.refreshed_at)

    def test_runworker_processes_each_account(self):
        other_account = Account.objects.create(
            email="device-other@example.com",
            name="Other Device Test",
            password="pwd",
        )
        class LoopExit(Exception):
            pass

        call_order = []

        def fake_run_pending_refresh(*, account, sync_interval_seconds):
            call_order.append((account.email, sync_interval_seconds))
            return False

        with patch.dict(os.environ, {"DEVICE_SYNC_INTERVAL": "300"}, clear=False), patch(
            "devices.management.commands.runworker.Account.objects.all",
            return_value=[self.account, other_account],
        ), patch(
            "django.db.close_old_connections",
            return_value=None,
        ), patch(
            "devices.management.commands.runworker.DeviceDashboardService.run_pending_refresh",
            side_effect=fake_run_pending_refresh,
        ) as run_pending_refresh, patch(
            "devices.management.commands.runworker.time.sleep",
            side_effect=LoopExit,
        ):
            with self.assertRaises(LoopExit):
                call_command("runworker")

        self.assertEqual(run_pending_refresh.call_count, 2)
        self.assertEqual(
            call_order,
            [
                (self.account.email, 300),
                (other_account.email, 300),
            ],
        )


class DeviceDashboardApiTest(TestCase):
    def setUp(self):
        self.account = Account.objects.create(
            email="device-api@example.com",
            name="Device Api Test",
            password="pwd",
        )
        self.dashboard_url = reverse("devices:dashboard")
        self.refresh_url = reverse("devices:dashboard_refresh")

    def test_dashboard_endpoint_returns_pending_snapshot_when_worker_has_not_run(self):
        response = self.client.get(self.dashboard_url, HTTP_X_WANNY_EMAIL=self.account.email)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["snapshot"]["has_snapshot"])
        self.assertTrue(payload["snapshot"]["pending_refresh"])

    def test_dashboard_endpoint_returns_persisted_snapshot(self):
        DeviceDashboardService.refresh(self.account, trigger="test")

        response = self.client.get(self.dashboard_url, HTTP_X_WANNY_EMAIL=self.account.email)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["snapshot"]["has_snapshot"])
        self.assertEqual(payload["snapshot"]["rooms"][0]["name"], "客厅")
        self.assertGreater(len(payload["snapshot"]["anomalies"]), 0)
        self.assertGreater(len(payload["snapshot"]["rules"]), 0)

    def test_refresh_endpoint_queues_worker_refresh(self):
        response = self.client.post(self.refresh_url, HTTP_X_WANNY_EMAIL=self.account.email)

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "accepted")
        self.assertTrue(payload["snapshot"]["pending_refresh"])

        state = DeviceDashboardState.objects.get(account=self.account, key=DeviceDashboardService.state_key)
        self.assertEqual(state.requested_trigger, "api")
        self.assertIsNotNone(state.refresh_requested_at)
