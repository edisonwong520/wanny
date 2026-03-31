import json
from datetime import datetime
from types import SimpleNamespace

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import Account
from memory.models import UserProfile
from memory.review import parse_review_hours, should_run_review_now
from memory.services import (
    MemoryService,
    PROFILE_SOURCE_MANUAL,
    PROFILE_SOURCE_REVIEW,
    build_profile_update,
)


class ProfileMergeLogicTests(SimpleTestCase):
    def test_review_update_preserves_manual_value_and_records_latest_suggestion(self):
        existing = SimpleNamespace(
            category="Environment",
            value="26",
            confidence=1.0,
            source=PROFILE_SOURCE_MANUAL,
            is_user_edited=True,
            last_confirmed=datetime(2026, 3, 30, 10, 0, 0),
            last_review_value="",
            last_review_confidence=None,
            last_review_at=None,
        )

        defaults = build_profile_update(
            existing,
            {
                "category": "Environment",
                "value": "24",
                "confidence": 0.82,
            },
            source=PROFILE_SOURCE_REVIEW,
            now=datetime(2026, 3, 30, 12, 0, 0),
        )

        self.assertEqual(defaults["value"], "26")
        self.assertEqual(defaults["source"], PROFILE_SOURCE_MANUAL)
        self.assertTrue(defaults["is_user_edited"])
        self.assertEqual(defaults["last_review_value"], "24")
        self.assertEqual(defaults["last_review_confidence"], 0.82)

    def test_parse_review_hours_supports_twice_daily_schedule(self):
        self.assertEqual(parse_review_hours("0,12"), [0, 12])
        self.assertEqual(parse_review_hours(None, "3"), [3])
        self.assertEqual(parse_review_hours("bad,25"), [0, 12])

    def test_should_run_review_now_only_allows_target_hour_window_once(self):
        self.assertTrue(
            should_run_review_now(datetime(2026, 3, 30, 0, 0, 0), [0, 12], None)
        )
        self.assertTrue(
            should_run_review_now(datetime(2026, 3, 30, 12, 4, 59), [0, 12], None)
        )
        self.assertFalse(
            should_run_review_now(datetime(2026, 3, 30, 12, 5, 0), [0, 12], None)
        )
        self.assertFalse(
            should_run_review_now(datetime(2026, 3, 30, 12, 0, 0), [0, 12], "2026-03-30-12")
        )


class UserProfileFeatureTests(TestCase):
    def setUp(self):
        self.client_url = reverse("memory:profiles")
        self.account = Account.objects.create(
            email="memory-test@example.com",
            name="Memory Test",
            password="pwd",
        )
        self.auth_headers = {"HTTP_X_WANNY_EMAIL": self.account.email}

    def test_manual_profile_api_marks_profile_as_user_edited(self):
        response = self.client.post(
            self.client_url,
            data=json.dumps(
                {
                    "category": "Environment",
                    "key": "preferred_temp",
                    "value": "26",
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        profile = UserProfile.objects.get(account=self.account, key="preferred_temp")
        self.assertEqual(profile.value, "26")
        self.assertEqual(profile.source, UserProfile.SourceChoices.MANUAL)
        self.assertTrue(profile.is_user_edited)
        self.assertEqual(profile.confidence, 1.0)
        self.assertIsNotNone(profile.last_confirmed)

    def test_review_update_keeps_user_value_when_conflicting(self):
        async_to_sync(MemoryService.upsert_manual_profile)(
            account=self.account,
            key="preferred_temp",
            value="26",
            category="Environment",
        )

        async_to_sync(MemoryService.apply_review_profile_update)(
            self.account,
            {
                "category": "Environment",
                "key": "preferred_temp",
                "value": "24",
                "confidence": 0.81,
            },
        )

        profile = UserProfile.objects.get(account=self.account, key="preferred_temp")
        self.assertEqual(profile.value, "26")
        self.assertEqual(profile.source, UserProfile.SourceChoices.MANUAL)
        self.assertTrue(profile.is_user_edited)
        self.assertEqual(profile.last_review_value, "24")
        self.assertEqual(profile.last_review_confidence, 0.81)
        self.assertIsNotNone(profile.last_review_at)

    def test_review_update_creates_profile_for_new_user(self):
        other_account = Account.objects.create(
            email="memory-new@example.com",
            name="Memory New",
            password="pwd",
        )
        async_to_sync(MemoryService.apply_review_profile_update)(
            other_account,
            {
                "category": "Habit",
                "key": "bedtime_routine",
                "value": "23:30",
                "confidence": 0.74,
            },
        )

        profile = UserProfile.objects.get(account=other_account, key="bedtime_routine")
        self.assertEqual(profile.value, "23:30")
        self.assertEqual(profile.source, UserProfile.SourceChoices.REVIEW)
        self.assertFalse(profile.is_user_edited)
        self.assertEqual(profile.confidence, 0.74)

    def test_get_profiles_api_returns_profiles(self):
        async_to_sync(MemoryService.upsert_manual_profile)(
            account=self.account,
            key="preferred_temp",
            value="26",
            category="Environment",
        )

        response = self.client.get(self.client_url, **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(len(payload["profiles"]), 1)
        self.assertEqual(payload["profiles"][0]["key"], "preferred_temp")
