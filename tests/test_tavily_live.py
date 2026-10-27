import unittest

from integrations.http_json import HttpFailure
from integrations.tavily import LiveTavily
from keeper_core.adapters import AuthenticationError, InvalidProviderResponse, ProviderUnavailable, RateLimited


class TavilyTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.outcome = {"results": [
            {"url": f"https://example.test/{n}", "title": f"Role {n}", "content": "Details"}
            for n in range(4)
        ]}

        def transport(url, body, headers, timeout):
            self.calls.append((url, body, headers, timeout))
            if isinstance(self.outcome, Exception):
                raise self.outcome
            return self.outcome

        self.searcher = LiveTavily("demo-key", timeout=4, transport=transport)

    def test_bounded_results_and_timeout_configuration(self):
        hits = self.searcher.search("internship", limit=2)
        self.assertEqual([hit.title for hit in hits], ["Role 0", "Role 1"])
        self.assertEqual(hits[0].source, "example.test")
        self.assertEqual(self.calls[0][1]["max_results"], 2)
        self.assertEqual(self.calls[0][3], 4)
        with self.assertRaises(ValueError):
            self.searcher.search("internship", limit=21)

    def test_health_uses_one_bounded_search(self):
        self.searcher.check_health()
        self.assertEqual(self.calls[0][1]["max_results"], 1)

    def test_timeout_and_provider_errors(self):
        for outcome, expected in [(TimeoutError(), ProviderUnavailable),
                                  (HttpFailure(429, {}, 3), RateLimited),
                                  (HttpFailure(401, {}), AuthenticationError),
                                  (HttpFailure(503, {}), ProviderUnavailable)]:
            self.outcome = outcome
            with self.assertRaises(expected):
                self.searcher.search("internship")

    def test_malformed_payload_is_not_empty_success(self):
        self.outcome = {"results": [{"url": "javascript:bad", "title": "Role", "content": "Text"}]}
        with self.assertRaises(InvalidProviderResponse):
            self.searcher.search("internship")


if __name__ == "__main__":
    unittest.main()
