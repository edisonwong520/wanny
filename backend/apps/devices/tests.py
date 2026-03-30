from django.test import TestCase
from django.urls import reverse

from .models import DeviceDashboardState
from .services import DeviceDashboardService


class DeviceDashboardServiceTest(TestCase):
    def test_get_dashboard_queues_bootstrap_when_empty(self):
        payload = DeviceDashboardService.get_dashboard()

        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["snapshot"]["has_snapshot"])
        self.assertTrue(payload["snapshot"]["pending_refresh"])
        self.assertEqual(payload["snapshot"]["rooms"], [])
        self.assertEqual(payload["snapshot"]["devices"], [])

        state = DeviceDashboardState.objects.get(key=DeviceDashboardService.state_key)
        self.assertEqual(state.requested_trigger, "bootstrap")
        self.assertIsNotNone(state.refresh_requested_at)
        self.assertIsNone(state.refreshed_at)

    def test_run_pending_refresh_persists_snapshot_and_clears_pending(self):
        DeviceDashboardService.request_refresh(trigger="manual")

        refreshed = DeviceDashboardService.run_pending_refresh(sync_interval_seconds=300)

        self.assertTrue(refreshed)
        payload = DeviceDashboardService.get_dashboard()
        self.assertTrue(payload["snapshot"]["has_snapshot"])
        self.assertFalse(payload["snapshot"]["pending_refresh"])
        self.assertGreater(len(payload["snapshot"]["rooms"]), 0)
        self.assertGreater(len(payload["snapshot"]["devices"]), 0)

        state = DeviceDashboardState.objects.get(key=DeviceDashboardService.state_key)
        self.assertEqual(state.last_trigger, "manual")
        self.assertEqual(state.requested_trigger, "")
        self.assertIsNone(state.refresh_requested_at)
        self.assertIsNotNone(state.refreshed_at)


class DeviceDashboardApiTest(TestCase):
    def setUp(self):
        self.dashboard_url = reverse("devices:dashboard")
        self.refresh_url = reverse("devices:dashboard_refresh")

    def test_dashboard_endpoint_returns_pending_snapshot_when_worker_has_not_run(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertFalse(payload["snapshot"]["has_snapshot"])
        self.assertTrue(payload["snapshot"]["pending_refresh"])

    def test_dashboard_endpoint_returns_persisted_snapshot(self):
        DeviceDashboardService.refresh(trigger="test")

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["snapshot"]["has_snapshot"])
        self.assertEqual(payload["snapshot"]["rooms"][0]["name"], "客厅")
        self.assertGreater(len(payload["snapshot"]["anomalies"]), 0)
        self.assertGreater(len(payload["snapshot"]["rules"]), 0)

    def test_refresh_endpoint_queues_worker_refresh(self):
        response = self.client.post(self.refresh_url)

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "accepted")
        self.assertTrue(payload["snapshot"]["pending_refresh"])

        state = DeviceDashboardState.objects.get(key=DeviceDashboardService.state_key)
        self.assertEqual(state.requested_trigger, "api")
        self.assertIsNotNone(state.refresh_requested_at)
