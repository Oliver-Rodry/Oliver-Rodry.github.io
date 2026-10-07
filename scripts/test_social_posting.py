import unittest
from datetime import datetime
from unittest.mock import patch
import social_posting as social

class CampaignWindowTests(unittest.TestCase):
    def state(self):
        return {'campaign': {'expires_at': '2026-10-10T21:31:00-04:00', 'daily_window': ['07:30', '21:30'], 'minimum_interval_minutes': 90}, 'history': []}

    def due(self, state, stamp):
        with patch.object(social, 'campaign_item', return_value={'sku': 'example'}):
            return social.campaign_post_due(state, datetime.fromisoformat(stamp))

    def test_window_and_expiration(self):
        for stamp, expected in [('2026-10-08T07:29:00-04:00', False), ('2026-10-08T07:30:00-04:00', True), ('2026-10-08T21:30:00-04:00', True), ('2026-10-08T21:31:00-04:00', False), ('2026-10-11T08:00:00-04:00', False)]:
            with self.subTest(stamp=stamp):
                self.assertEqual(self.due(self.state(), stamp), expected)

    def test_late_runs_do_not_publish_close_together(self):
        state = self.state()
        state['history'] = [{'completed_at': '2026-10-08T08:15:00-04:00'}]
        self.assertFalse(self.due(state, '2026-10-08T09:00:00-04:00'))
        self.assertTrue(self.due(state, '2026-10-08T09:45:00-04:00'))

    def test_pending_retry_respects_end(self):
        state = self.state()
        state['pending'] = {'scheduled_for': '2026-10-10T21:00:00-04:00'}
        self.assertFalse(self.due(state, '2026-10-11T08:00:00-04:00'))

if __name__ == '__main__':
    unittest.main()
