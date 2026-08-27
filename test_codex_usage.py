import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import codex_usage


class CodexUsageTest(unittest.TestCase):
    def test_reads_latest_rate_limit(self):
        result = codex_usage._parse_rate_limits({
            "timestamp": "2027-01-15T08:00:00Z",
            "payload": {"rate_limits": {
            "primary": {"used_percent": 42, "resets_at": 1_800_000_000},
            "secondary": {"used_percent": 7, "resets_at": 1_800_100_000},
        }}})
        self.assertEqual(result["utilization_5h"], 0.42)
        self.assertEqual(result["utilization_weekly"], 0.07)
        self.assertEqual(result["fetched_at"], datetime(2027, 1, 15, 8, tzinfo=timezone.utc))

    def test_rejects_malformed_usage_records(self):
        valid = {
            "timestamp": "2027-01-15T08:00:00Z",
            "payload": {"rate_limits": {
                "primary": {"used_percent": 42, "resets_at": 1_800_000_000},
                "secondary": {"used_percent": 7, "resets_at": 1_800_100_000},
            }},
        }
        cases = [
            {},
            [],
            None,
            {**valid, "timestamp": "invalid"},
            {**valid, "timestamp": None},
            {**valid, "timestamp": "2027-01-15T08:00:00"},
            {**valid, "payload": {"rate_limits": {
                **valid["payload"]["rate_limits"],
                "primary": {"resets_at": 1_800_000_000},
            }}},
        ]
        for value in (None, "bad", float("nan"), float("inf"), -1, 101):
            record = {**valid, "payload": {"rate_limits": {
                **valid["payload"]["rate_limits"],
                "primary": {"used_percent": value, "resets_at": 1_800_000_000},
            }}}
            cases.append(record)
        for value in (float("nan"), float("inf"), 10**100):
            record = {**valid, "payload": {"rate_limits": {
                **valid["payload"]["rate_limits"],
                "primary": {"used_percent": 42, "resets_at": value},
            }}}
            cases.append(record)
        for record in cases:
            with self.subTest(record=record):
                self.assertIsNone(codex_usage._parse_rate_limits(record))

    def test_returns_empty_when_no_usage_exists(self):
        sessions = Mock()
        sessions.rglob.return_value = []
        with patch.object(codex_usage, "CODEX_SESSIONS", sessions):
            self.assertEqual(codex_usage.get_last_data(), {})

    def test_started_get_last_data_propagates_luna_active_state(self):
        sessions = Mock()
        sessions.rglob.return_value = []
        with (
            patch.object(codex_usage, "CODEX_SESSIONS", sessions),
            patch.object(codex_usage, "_started", True),
            patch.object(codex_usage, "_luna_data", {
                "utilization_luna_reserve": 0.3,
                "resets_at_luna_reserve": None,
                "luna_reserve_active": True,
            }),
        ):
            self.assertTrue(codex_usage.get_last_data()["luna_reserve_active"])

            codex_usage._luna_data["luna_reserve_active"] = False
            self.assertFalse(codex_usage.get_last_data()["luna_reserve_active"])

    def test_reads_luna_reserve_bucket(self):
        result = codex_usage._parse_luna_reserve({
            "rateLimitsByLimitId": {
                "base_model_inference": {
                    "limitName": "gpt-reserve",
                    "primary": {"usedPercent": 13, "resetsAt": 1_800_000_000},
                },
            },
        })
        self.assertEqual(result["utilization_luna_reserve"], 0.13)
        self.assertEqual(result["resets_at_luna_reserve"], datetime.fromtimestamp(1_800_000_000, timezone.utc))

    def test_luna_reserve_active_when_standard_limit_is_blocked(self):
        result = codex_usage._parse_luna_reserve({
            "rateLimits": {
                "rateLimitReachedType": "rate_limit_reached",
                "primary": {"usedPercent": 100},
            },
            "rateLimitsByLimitId": {
                "base_model_inference": {
                    "limitName": "gpt-reserve",
                    "primary": {"usedPercent": 13},
                },
            },
        })
        self.assertTrue(result["luna_reserve_active"])

    def test_luna_reserve_inactive_when_standard_limit_is_available(self):
        result = codex_usage._parse_luna_reserve({
            "rateLimits": {"rateLimitReachedType": None, "primary": {"usedPercent": 20}},
            "rateLimitsByLimitId": {
                "base_model_inference": {
                    "limitName": "gpt-reserve",
                    "primary": {"usedPercent": 13},
                },
            },
        })
        self.assertFalse(result["luna_reserve_active"])

    def test_rejects_invalid_luna_reserve_bucket(self):
        for used_percent in (None, "bad", float("nan"), float("inf"), -1, 101, True):
            with self.subTest(used_percent=used_percent):
                result = codex_usage._parse_luna_reserve({
                    "rateLimitsByLimitId": {
                        "base_model_inference": {
                            "limitName": "gpt-reserve",
                            "primary": {"usedPercent": used_percent},
                        },
                    },
                })
                self.assertIsNone(result)

    def test_luna_failure_keeps_active_state_but_clears_value(self):
        luna_data = {
            "utilization_luna_reserve": 0.23,
            "resets_at_luna_reserve": datetime.now(timezone.utc),
            "luna_reserve_active": True,
        }
        with (
            patch.object(codex_usage, "_luna_data", luna_data),
            patch.object(codex_usage, "_read_app_server_rate_limits", return_value=None),
        ):
            codex_usage._update_luna_reserve()

        self.assertEqual(luna_data["utilization_luna_reserve"], None)
        self.assertEqual(luna_data["resets_at_luna_reserve"], None)
        self.assertTrue(luna_data["luna_reserve_active"])

    def test_luna_failure_clears_inactive_state(self):
        luna_data = {
            "utilization_luna_reserve": 0.23,
            "resets_at_luna_reserve": None,
            "luna_reserve_active": False,
        }
        with (
            patch.object(codex_usage, "_luna_data", luna_data),
            patch.object(codex_usage, "_read_app_server_rate_limits", return_value=None),
        ):
            codex_usage._update_luna_reserve()

        self.assertEqual(luna_data, {})


if __name__ == "__main__":
    unittest.main()
