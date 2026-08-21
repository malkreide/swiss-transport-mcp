"""Retry-Politik gegenüber opentransportdata.swiss (ARCH-014).

Vier Fragen: Was wird wiederholt, wie schnell, wie lange, und hält der Deckel,
den die Konstante behauptet.

Dieser Server hat vier Aufrufstellen in zwei Modulen — die Politik sitzt in
einem gemeinsamen Kern, die Tests prüfen den Kern *und* jede Anbindung.
"""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from swiss_transport_mcp import api_client, retry
from swiss_transport_mcp.api_infrastructure import (
    APIConfig,
    APIError,
    RateLimiter,
    TransportAPIClient,
)

CKAN_URL = "https://api.opentransportdata.swiss/ckan-api/package_list"
OJP_URL = "https://api.opentransportdata.swiss/ojp20"

# Wanduhr-Zahlen fuer den Deadline-Test weiter unten, weit genug auseinander,
# dass Scheduler-Jitter das Ergebnis nicht mehr kippen kann. Gemessen auf 3.11
# ueber 15 Laeufe des Test-Rumpfs selbst, durch pytest, damit jede Fixture
# steht: 0.122-0.141s gegen ein Budget von 0.05s. Rund 0.077s davon waren
# Aufbau — mehr als das Budget — der Test mass also ueberwiegend Aufbau und
# nicht Deadline. Die alte Schranke von 0.5s liess 0.373s absoluten Spielraum,
# und CI-Jitter ist absolut, nicht proportional: In swiss-efv-mcp machte ein
# belasteter Runner am 21.08.2026 aus 0.105s ganze 0.55s und riss dieselbe
# Zusicherung. Ein groesseres Budget verkuerzt diesen Stillstand nicht, es
# macht ihn klein *gegenueber* dem, was gemessen wird.
_BUDGET = 0.5
_CUT_BY = 2.5
_SLOW_RESPONSE = 8.0


@pytest.fixture(autouse=True)
def _api_keys(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "test-key")


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(status, headers=headers)


def _status_error(status: int, retry_after: str | None = None) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError("boom", request=None, response=_resp(status, retry_after))


def _ok_ckan() -> httpx.Response:
    return httpx.Response(200, json={"success": True, "result": {"ok": 1}})


# --- Was wird wiederholt ----------------------------------------------------


@respx.mock
async def test_ckan_retries_a_503_then_succeeds():
    route = respx.get(CKAN_URL).mock(side_effect=[httpx.Response(503), _ok_ckan()])
    assert await api_client.ckan_request("package_list") == {"ok": 1}
    assert route.call_count == 2


@respx.mock
async def test_ckan_retries_a_connect_error():
    route = respx.get(CKAN_URL).mock(side_effect=[httpx.ConnectError(""), _ok_ckan()])
    await api_client.ckan_request("package_list")
    assert route.call_count == 2


@respx.mock
async def test_ckan_404_fails_fast():
    """Ein 4xx ist eine Aussage über die Anfrage, nicht über den Moment."""
    route = respx.get(CKAN_URL).mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        await api_client.ckan_request("package_list")
    assert route.call_count == 1


@respx.mock
async def test_ckan_403_keeps_the_subscription_hint_and_is_not_retried():
    """Ein fehlendes Abo wird beim vierten Versuch nicht zum vorhandenen.

    Der Hinweis auf das CKAN-Produkt im API-Manager ist das, was den Fehler
    behebbar macht — er darf nicht hinter einem generischen HTTPStatusError
    verschwinden, nur weil ein Retry dazwischenkam.
    """
    route = respx.get(CKAN_URL).mock(return_value=httpx.Response(403))
    with pytest.raises(ValueError, match="subscription"):
        await api_client.ckan_request("package_list")
    assert route.call_count == 1


@respx.mock
async def test_ckan_429_is_retried_although_it_is_a_4xx():
    route = respx.get(CKAN_URL).mock(side_effect=[httpx.Response(429), _ok_ckan()])
    await api_client.ckan_request("package_list")
    assert route.call_count == 2


@respx.mock
async def test_ckan_attempts_are_bounded():
    route = respx.get(CKAN_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        await api_client.ckan_request("package_list")
    assert route.call_count == retry.ATTEMPTS


@respx.mock
async def test_ojp_retries_a_503_then_succeeds():
    route = respx.post(OJP_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, text="<ojp/>")]
    )
    assert await api_client.ojp_request("<req/>") == "<ojp/>"
    assert route.call_count == 2


@respx.mock
async def test_a_malformed_ckan_payload_is_not_retried():
    """``success: false`` ist eine Antwort, kein Ausfall — sie wiederholt sich."""
    route = respx.get(CKAN_URL).mock(
        return_value=httpx.Response(200, json={"success": False, "error": {"message": "nope"}})
    )
    with pytest.raises(ValueError, match="nope"):
        await api_client.ckan_request("package_list")
    assert route.call_count == 1


# --- Wie schnell ------------------------------------------------------------


class TestRetryDelay:
    def test_retry_after_seconds_beats_the_curve(self):
        exc = _status_error(503, "13")
        for _ in range(20):
            assert retry.retry_delay(1, exc) >= 13.0

    def test_retry_after_http_date_is_read(self):
        """RFC 9110 erlaubt beide Formen — ein Datum ist keine Ausnahme."""
        from datetime import UTC, datetime, timedelta
        from email.utils import format_datetime

        when = datetime.now(UTC) + timedelta(seconds=12)
        exc = _status_error(503, format_datetime(when, usegmt=True))
        assert 9.0 <= retry.retry_delay(1, exc) <= 16.0

    @pytest.mark.parametrize("bad", ["morgen", "", "-5", "12.5"])
    def test_an_unparseable_retry_after_falls_back_to_the_curve(self, bad):
        """Eine kaputte Kopfzeile darf auf dem Fehlerpfad kein Absturz sein."""
        assert retry.retry_delay(1, _status_error(503, bad)) <= 3.0

    def test_retry_after_on_a_404_is_ignored(self):
        assert retry.retry_delay(1, _status_error(404, "600")) <= 3.0

    def test_the_delay_is_spread(self):
        draws = {retry.retry_delay(1, None) for _ in range(30)}
        assert len(draws) > 1, "Wartezeit ist deterministisch — Jitter fehlt"
        assert all(1.0 <= d <= 3.0 for d in draws)

    def test_retry_after_jitter_never_goes_below_the_hinted_value(self):
        exc = _status_error(429, "5")
        for _ in range(30):
            assert retry.retry_delay(1, exc) >= 5.0

    def test_the_cap_is_a_real_bound_not_a_midpoint(self):
        """MAX_DELAY muss halten, auch wenn der Jitter nach oben ausschlägt.

        Vor dem Jittern zu deckeln liess eine 20-s-Decke auf dem exponentiellen
        Pfad auf 30 s und auf dem ``Retry-After``-Pfad auf 25 s wachsen.
        Gefunden durch ein Codex-Review an ``parlament-mcp#35``.
        """
        exc = _status_error(429, "86400")
        for attempt in range(8):
            for _ in range(20):
                assert retry.retry_delay(attempt, None) <= retry.MAX_DELAY
                assert retry.retry_delay(attempt, exc) <= retry.MAX_DELAY

    def test_an_absurd_retry_after_lands_exactly_on_the_cap(self):
        assert retry.retry_delay(0, _status_error(503, "86400")) == retry.MAX_DELAY


class TestIsRetryable:
    @pytest.mark.parametrize("status", [500, 502, 503, 504, 429])
    def test_transient_statuses_are_retryable(self, status):
        assert retry.is_retryable(_status_error(status))

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
    def test_other_client_errors_are_not(self, status):
        assert not retry.is_retryable(_status_error(status))

    def test_network_errors_are_retryable(self):
        assert retry.is_retryable(httpx.ConnectError(""))
        assert retry.is_retryable(httpx.ReadTimeout(""))

    def test_a_value_error_is_not(self):
        """Egress- und Payload-Fehler ändern sich nicht durch Wiederholung."""
        assert not retry.is_retryable(ValueError("egress blocked"))


# --- Wie lange --------------------------------------------------------------


def test_the_ckan_budget_stays_under_the_mcp_client_default():
    """Der Anker ist gemessen, nicht geschätzt."""
    from mcp.shared._httpx_utils import MCP_DEFAULT_TIMEOUT

    assert retry.TOTAL_BUDGET < MCP_DEFAULT_TIMEOUT


def test_the_ojp_budget_deliberately_exceeds_it():
    """OJP weicht mit Grund ab, nicht aus Versehen.

    ``OJP_TIMEOUT = 45.0`` steht seit je im Repo, weil Trip-Berechnungen länger
    dauern. Ein 25-s-Budget würde legitime Verbindungsabfragen abwürgen, die
    heute durchgehen — der Retry soll Ausfälle überbrücken und nicht
    funktionierende Anfragen kürzen.
    """
    from mcp.shared._httpx_utils import MCP_DEFAULT_TIMEOUT

    assert retry.OJP_BUDGET > MCP_DEFAULT_TIMEOUT
    assert retry.OJP_BUDGET == api_client.OJP_TIMEOUT


@respx.mock
async def test_a_wait_that_outlasts_the_budget_is_not_taken(monkeypatch):
    """Eine Wartezeit, die das Budget überdauert, ist eine für niemanden."""
    monkeypatch.setattr(retry, "MAX_DELAY", 3600.0)  # Deckel als Grund ausschliessen
    route = respx.get(CKAN_URL).mock(return_value=_resp(503, "3600"))
    with pytest.raises(httpx.HTTPStatusError):
        await api_client.ckan_request("package_list")
    assert route.call_count == 1, "nach dem ersten 503 blieb keine Zeit mehr"


@respx.mock
async def test_a_slow_response_is_cut_by_the_wall_clock_deadline(monkeypatch, real_sleep):
    """Das Budget muss binden, auch wenn das httpx-Timeout nie feuert.

    httpx wendet sein Timeout pro Operation an und das Read-Timeout beginnt mit
    jedem Chunk von vorn — eine langsam tröpfelnde Antwort kann das Budget also
    überdauern, ohne dass ein einzelner Read abläuft.

    Bewusst mit der *echten* ``asyncio.sleep``: Eine Zusicherung über echte Zeit
    kann eine Uhr, die nur beim Schlafen vorrückt, nicht widerlegen — genau
    dieser blinde Fleck liess den Fehler in den Geschwister-Servern durch.

    Die Spannen sind absichtlich weit — die Messung dahinter steht bei
    ``_BUDGET`` oben. Der einmalige Prozessstart faellt vor der Uhr an. Den
    Client baut ``ckan_request`` selbst, er laesst sich also nicht aus dem
    Fenster nehmen: Gemessen werden 0.575s gegen ein Budget von 0.5s, die
    restlichen rund 0.075s sind dieser Bau. Das sind noch 13% des Fensters
    statt 60% wie vorher.
    """
    # Aufwaermen auf dem unangetasteten Standardbudget, bevor es unten verengt
    # wird: zahlt den einmaligen Prozessstart ausserhalb des gemessenen
    # Fensters. ``ckan_request`` cacht nichts, der gemessene Aufruf geht also
    # weiterhin wirklich hinaus.
    route = respx.get(CKAN_URL).mock(return_value=_ok_ckan())
    await api_client.ckan_request("package_list")

    monkeypatch.setattr(retry, "TOTAL_BUDGET", _BUDGET)

    async def _slow(request):
        await real_sleep(_SLOW_RESPONSE)
        return _ok_ckan()

    route.mock(side_effect=_slow)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await api_client.ckan_request("package_list")
    elapsed = time.monotonic() - started

    # Absichtlich zweiseitig. Die obere Schranke ist die Zusicherung: Eine
    # Antwort, die _SLOW_RESPONSE gebraucht haette, wurde geschnitten. Die
    # untere sagt, dass der Schnitt vom Budget kam und nicht davon, dass etwas
    # sofort scheiterte — eine falsch gerechnete Deadline segelt durch eine
    # obere Schranke allein hindurch.
    assert elapsed >= _BUDGET / 2, f"zu frueh geschnitten fuer das Budget: {elapsed:.3f}s"
    assert elapsed < _CUT_BY, f"Deadline hat nicht geschnitten: {elapsed:.2f}s"


# --- Anbindung an TransportAPIClient ----------------------------------------


def _client_with(api_name: str = "test", max_requests: int = 100) -> TransportAPIClient:
    client = TransportAPIClient()
    client.register_api(
        APIConfig(
            name=api_name,
            base_url="https://api.opentransportdata.swiss/ckan-api",
            api_key="k",
            rate_limit=RateLimiter(max_requests=max_requests, window_seconds=60.0),
            cache_ttl=0.0,
        )
    )
    return client


@respx.mock
async def test_infrastructure_client_retries_a_503():
    route = respx.get(url__startswith="https://api.opentransportdata.swiss/ckan-api").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )
    client = _client_with()
    assert await client.get("test", use_cache=False) == {"ok": True}
    assert route.call_count == 2
    await client.close()


@respx.mock
async def test_every_retry_is_counted_by_the_rate_limiter():
    """Ein Retry ist eine weitere Abfrage bei der Quelle.

    Zählte nur der erste Versuch, meldete der Limiter weniger Verbrauch, als er
    zugelassen hat — und ausgerechnet ein Server, der wegen Überlast 503
    sendet, bekäme ungezählte Wiederholungen.
    """
    respx.get(url__startswith="https://api.opentransportdata.swiss/ckan-api").mock(
        return_value=httpx.Response(503)
    )
    client = _client_with()
    limiter = client._configs["test"].rate_limit
    with pytest.raises(APIError):
        await client.get("test", use_cache=False)
    assert len(limiter._timestamps) == retry.ATTEMPTS
    await client.close()


@respx.mock
async def test_an_exhausted_budget_surfaces_as_an_api_error(monkeypatch, real_sleep):
    """Das Budget wirft den builtin ``TimeoutError``.

    Ohne ihn in der Fehlerabbildung entkäme ein aufgebrauchtes Budget der
    Übersetzung ganz und käme roh beim Tool an.
    """
    monkeypatch.setattr(retry, "TOTAL_BUDGET", 0.05)

    async def _slow(request):
        await real_sleep(1.0)
        return httpx.Response(200, json={})

    respx.get(url__startswith="https://api.opentransportdata.swiss/ckan-api").mock(
        side_effect=_slow
    )
    client = _client_with()
    with pytest.raises(APIError, match="Zeitbudget"):
        await client.get("test", use_cache=False)
    await client.close()
