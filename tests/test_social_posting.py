import importlib.util
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("social", Path(__file__).resolve().parents[1] / "scripts" / "social_posting.py")
social = importlib.util.module_from_spec(spec)
spec.loader.exec_module(social)


class MissedSlotsTest(unittest.TestCase):
    def state(self):
        return {"history": [], "pending": None, "campaign": {
            "expires_at": "2026-10-31T09:00:00-04:00",
            "daily_window": ["07:30", "21:30"], "minimum_interval_minutes": 120,
            "schedule": [{"sku": str(i), "scheduled_for": t} for i, t in enumerate([
                "2026-10-25T17:00:00-04:00", "2026-10-26T09:00:00-04:00",
                "2026-10-26T11:00:00-04:00", "2026-10-26T15:00:00-04:00"])]}}

    def test_latest_due_only_and_idempotent(self):
        state = self.state()
        now = datetime.fromisoformat("2026-10-26T13:00:00-04:00")
        self.assertEqual(social.reconcile_missed_slots(state, now), 2)
        self.assertEqual(social.reconcile_missed_slots(state, now), 0)
        with patch.object(social, "eligible_products", return_value=[{"sku": str(i)} for i in range(4)]):
            self.assertEqual(social.campaign_item(state, now, True)["sku"], "2")

    def test_pending_partial_post_is_preserved(self):
        state = self.state()
        state["pending"] = {"sku": "0", "instagram_post_id": "published"}
        self.assertEqual(social.reconcile_missed_slots(state, datetime.fromisoformat("2026-10-26T13:00:00-04:00")), 0)
        self.assertEqual(state["pending"]["instagram_post_id"], "published")

    def test_expired_campaign_marks_all_due(self):
        state = self.state()
        now = datetime.fromisoformat("2026-11-01T13:00:00-04:00")
        self.assertEqual(social.reconcile_missed_slots(state, now), 4)
        self.assertFalse(social.campaign_post_due(state, now))

    def test_yesterday_never_published_today(self):
        state = self.state()
        now = datetime.fromisoformat("2026-10-26T08:00:00-04:00")
        self.assertEqual(social.reconcile_missed_slots(state, now), 1)

    def test_spacing_and_night_window_remain(self):
        state = self.state()
        state["pending"] = {"scheduled_for": "2026-10-26T09:00:00-04:00"}
        state["history"] = [{"completed_at": "2026-10-26T12:00:00-04:00"}]
        self.assertFalse(social.campaign_post_due(state, datetime.fromisoformat("2026-10-26T13:00:00-04:00")))
        self.assertTrue(social.campaign_post_due(state, datetime.fromisoformat("2026-10-26T14:00:00-04:00")))
        self.assertFalse(social.campaign_post_due(state, datetime.fromisoformat("2026-10-26T22:00:00-04:00")))


if __name__ == "__main__":
    unittest.main()
