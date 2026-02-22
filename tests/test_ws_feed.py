import pytest

from hl_paper.ws_feed import parse_all_mids


class TestParseAllMids:
    def test_parse_mids_message(self):
        msg = {
            "channel": "allMids",
            "data": {
                "mids": {
                    "BTC": "50123.5",
                    "ETH": "3001.2",
                    "SOL": "145.67",
                }
            },
        }
        result = parse_all_mids(msg)
        assert result == {
            "BTC": pytest.approx(50123.5),
            "ETH": pytest.approx(3001.2),
            "SOL": pytest.approx(145.67),
        }

    def test_wrong_channel(self):
        msg = {"channel": "trades", "data": {}}
        result = parse_all_mids(msg)
        assert result is None

    def test_missing_data(self):
        msg = {"channel": "allMids"}
        result = parse_all_mids(msg)
        assert result is None

    def test_empty_mids(self):
        msg = {"channel": "allMids", "data": {"mids": {}}}
        result = parse_all_mids(msg)
        assert result == {}
