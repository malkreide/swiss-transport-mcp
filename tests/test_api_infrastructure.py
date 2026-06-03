"""Unit tests for the shared infrastructure: RateLimiter and SimpleCache.

Pure logic, no network. Time-dependent behaviour is driven via monkeypatched
clocks so the tests are deterministic and fast.
"""


import pytest

from swiss_transport_mcp import api_infrastructure
from swiss_transport_mcp.api_infrastructure import (
    APIConfig,
    RateLimiter,
    SimpleCache,
    create_transport_client,
)

# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

def test_rate_limiter_allows_up_to_limit():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    assert rl.can_proceed() is True
    rl.record()
    assert rl.can_proceed() is True
    rl.record()
    assert rl.can_proceed() is False


def test_rate_limiter_wait_time_zero_when_free():
    rl = RateLimiter(max_requests=1, window_seconds=60)
    assert rl.wait_time() == 0.0


def test_rate_limiter_window_expiry(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(api_infrastructure.time, "monotonic", lambda: clock["t"])

    rl = RateLimiter(max_requests=1, window_seconds=10)
    rl.record()
    assert rl.can_proceed() is False
    # Advance past the window — old timestamp should be cleaned out.
    clock["t"] += 11
    assert rl.can_proceed() is True
    assert rl.wait_time() == 0.0


def test_rate_limiter_wait_time_positive_when_blocked(monkeypatch):
    clock = {"t": 0.0}
    monkeypatch.setattr(api_infrastructure.time, "monotonic", lambda: clock["t"])
    rl = RateLimiter(max_requests=1, window_seconds=10)
    rl.record()
    clock["t"] += 3
    # Oldest at t=0, window 10 → next allowed at t=10, now=3 → ~7s.
    assert rl.wait_time() == pytest.approx(7.0, abs=0.001)


# ---------------------------------------------------------------------------
# SimpleCache
# ---------------------------------------------------------------------------

def test_cache_hit_and_miss():
    cache = SimpleCache()
    assert cache.get("siri", {"q": "x"}) is None
    cache.set("siri", {"q": "x"}, {"data": 1}, ttl=60)
    assert cache.get("siri", {"q": "x"}) == {"data": 1}


def test_cache_key_is_param_sensitive():
    cache = SimpleCache()
    cache.set("siri", {"q": "a"}, "A", ttl=60)
    assert cache.get("siri", {"q": "b"}) is None
    assert cache.get("siri", {"q": "a"}) == "A"


def test_cache_param_order_independent():
    cache = SimpleCache()
    cache.set("p", {"a": 1, "b": 2}, "v", ttl=60)
    # Same params, different insertion order → same key (sort_keys=True).
    assert cache.get("p", {"b": 2, "a": 1}) == "v"


def test_cache_expiry(monkeypatch):
    clock = {"t": 100.0}
    monkeypatch.setattr(api_infrastructure.time, "monotonic", lambda: clock["t"])
    cache = SimpleCache()
    cache.set("p", {"k": 1}, "v", ttl=5)
    assert cache.get("p", {"k": 1}) == "v"
    clock["t"] += 6
    assert cache.get("p", {"k": 1}) is None


def test_cache_clear():
    cache = SimpleCache()
    cache.set("p", {"k": 1}, "v", ttl=60)
    cache.clear()
    assert cache.get("p", {"k": 1}) is None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def test_factory_registers_only_keyed_apis():
    client = create_transport_client(siri_sx_key="k1", formation_key="k2")
    assert "siri_sx" in client._configs
    assert "formation" in client._configs
    # No key provided → API not registered (graceful, no crash).
    assert "occupancy" not in client._configs
    assert "ojp_fare" not in client._configs


def test_factory_uses_https_endpoints():
    client = create_transport_client(
        siri_sx_key="k", occupancy_key="k", formation_key="k", ojp_fare_key="k"
    )
    for cfg in client._configs.values():
        assert isinstance(cfg, APIConfig)
        assert cfg.base_url.startswith("https://"), cfg.base_url
