from datetime import UTC, datetime
from uuid import uuid4

import pytest

from poly_agent.decision import decide
from poly_agent.models import Signal
from poly_agent.polymarket import url_to_slug


def _signal(**ov) -> Signal:
    base = dict(
        id=uuid4(), strategy_id=uuid4(), research_config_id=uuid4(),
        strategy_git_sha="abc", research_config_version=1,
        asset="btc-100k-2026", direction="long", confidence=0.80,
        composite_risk_score=0.7,
        risk_score={"source_credibility": 0.7, "narrative_novelty": 0.6,
                    "timing_precision": 0.7, "evidence_strength": 0.7},
        source_article_ids=[], payload={}, published_at=datetime.now(UTC),
    )
    base.update(ov)
    return Signal.model_validate(base)


def _cfg(**ov) -> dict:
    base = {
        "id": uuid4(), "version": 1,
        "config": {"enabled": True, "min_confidence": 0.65, "max_stake_pct": 0.02,
                   "market_url": "https://polymarket.com/event/btc-100k-2026"},
    }
    base["config"].update(ov)
    return base


def test_long_buys_yes():
    intent, skip = decide(_signal(direction="long"), _cfg(),
                          open_total_stake_usd=0, has_open_on_market=False, halt=False)
    assert skip == ""
    assert intent.side == "YES"


def test_short_buys_no():
    intent, skip = decide(_signal(direction="short"), _cfg(),
                          open_total_stake_usd=0, has_open_on_market=False, halt=False)
    assert skip == ""
    assert intent.side == "NO"


def test_neutral_skips():
    intent, skip = decide(_signal(direction="neutral"), _cfg(),
                          open_total_stake_usd=0, has_open_on_market=False, halt=False)
    assert intent is None and "non-actionable" in skip


def test_halt_blocks():
    intent, skip = decide(_signal(), _cfg(),
                          open_total_stake_usd=0, has_open_on_market=False, halt=True)
    assert intent is None and "halt" in skip


def test_no_config_skips():
    intent, skip = decide(_signal(), None,
                          open_total_stake_usd=0, has_open_on_market=False, halt=False)
    assert intent is None and "no poly config" in skip


def test_disabled_config_skips():
    intent, skip = decide(_signal(), _cfg(enabled=False),
                          open_total_stake_usd=0, has_open_on_market=False, halt=False)
    assert intent is None and "disabled" in skip


def test_low_confidence_skips():
    intent, skip = decide(_signal(confidence=0.50), _cfg(min_confidence=0.65),
                          open_total_stake_usd=0, has_open_on_market=False, halt=False)
    assert intent is None and "confidence" in skip


def test_duplicate_market_blocks():
    intent, skip = decide(_signal(), _cfg(),
                          open_total_stake_usd=0, has_open_on_market=True, halt=False)
    assert intent is None and "already have open" in skip


def test_stake_cap_blocks():
    intent, skip = decide(_signal(), _cfg(),
                          open_total_stake_usd=490, has_open_on_market=False, halt=False)
    # default stake $25, cap $500 → 490 + 25 = 515 > 500
    assert intent is None and "stake cap" in skip


@pytest.mark.parametrize("inp,expected", [
    ("https://polymarket.com/event/btc-100k-2026", "btc-100k-2026"),
    ("https://polymarket.com/market/some-market-slug?utm=x", "some-market-slug"),
    ("btc-100k-2026", "btc-100k-2026"),
    ("", ""),
])
def test_url_to_slug(inp, expected):
    assert url_to_slug(inp) == expected
