"""Die CKAN-Hülle wird bestätigt, nicht angenommen (FID-006).

Zwei Stellen, zwei verschiedene Wege in dieselbe Stille:

`api_client.ckan_request` schrieb `return data.get("result", {})`. Fällt
`result` weg, bekam jeder der drei Aufrufer ein leeres Objekt — bei
`package_list`, dessen `result` eine **Liste** ist, sogar eines vom falschen
Typ.

`occupancy._fetch_occupancy_data` schrieb
`result.get("result", {}).get("resources", [])`. Die Schleife über die
Ressourcen lief dann nullmal, die Funktion gab `None` zurück, und der Aufrufer
las das als «für diesen Betreiber und Tag gibt es keine Belegungsdaten».

Der Portfolio-Durchlauf am 2026-08-07 fand acht Server, die mit CKAN sprechen;
alle acht prüfen das `success`-Envelope, sieben defaulteten `result` danach.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from swiss_transport_mcp.api_client import (
    CKAN_API_URL,
    UpstreamSchemaError,
    ckan_request,
    ckan_results,
)


def _mock(action: str, payload):
    return respx.get(f"{CKAN_API_URL}/{action}").mock(
        return_value=httpx.Response(200, json=payload)
    )


# --- Der Fund ----------------------------------------------------------------


@respx.mock
async def test_a_missing_result_raises_instead_of_returning_nothing(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    _mock("package_list", {"success": True, "help": "https://…/api/3/"})
    with pytest.raises(UpstreamSchemaError):
        await ckan_request("package_list")


@respx.mock
async def test_the_message_names_the_keys_that_are_actually_there(monkeypatch):
    """Ohne die vorhandenen Schlüssel ist der nächste Schritt Raten."""
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    _mock("package_search", {"success": True, "help": "…", "payload": {}})
    with pytest.raises(UpstreamSchemaError) as excinfo:
        await ckan_request("package_search")
    message = str(excinfo.value)
    assert "'help'" in message and "'payload'" in message, message
    assert "package_search" in message
    assert "keine Leermenge" in message


@respx.mock
async def test_the_old_default_was_the_wrong_type_for_package_list(monkeypatch):
    """`package_list` liefert eine Liste — der Ersatzwert `{}` war ein Objekt.

    Der alte Default erzeugte also zwei Fehler auf einmal: die Leermenge, und
    eine Leermenge vom falschen Typ. Dieser Test hält fest, dass eine echte
    Liste unverändert durchkommt.
    """
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    _mock("package_list", {"success": True, "result": ["a", "b"]})
    assert await ckan_request("package_list") == ["a", "b"]


# --- Die Gegenrichtung -------------------------------------------------------


@respx.mock
async def test_an_empty_list_result_is_still_a_normal_answer(monkeypatch):
    """`result: []` ist eine Aussage der Quelle, kein Strukturfehler.

    Bestätigt wird die **Anwesenheit** von `result`, nicht sein Inhalt — ein
    Wächter, der die echte Leermenge mitfängt, wird abgeschaltet.
    """
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    _mock("package_list", {"success": True, "result": []})
    assert await ckan_request("package_list") == []


@respx.mock
async def test_a_real_ckan_error_stays_a_plain_value_error(monkeypatch):
    """Die Quelle hat geantwortet und Nein gesagt — keine Formänderung."""
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    _mock("package_search", {"success": False, "error": {"message": "bad query"}})
    with pytest.raises(ValueError) as excinfo:
        await ckan_request("package_search")
    assert not isinstance(excinfo.value, UpstreamSchemaError)
    assert "bad query" in str(excinfo.value)


# --- Die zweite Stelle: der Belegungspfad ------------------------------------


class _FakeClient:
    """Gibt genau die CKAN-Hülle zurück, die der Test vorgibt."""

    def __init__(self, envelope):
        self.envelope = envelope

    async def get(self, *args, **kwargs):
        return self.envelope


@respx.mock
async def test_a_broken_envelope_now_reaches_the_direct_url_fallback():
    """Der Verhaltensunterschied, und er ist messbar.

    Vorher: `result.get("result", {}).get("resources", [])` ergab eine leere
    Liste, die Schleife lief nullmal, die Funktion gab `None` zurück — und der
    Direkt-URL-Fallback im `except`-Zweig wurde **nie erreicht**. Eine
    Strukturänderung sah damit aus wie «für diesen Betreiber und Tag gibt es
    keine Belegungsdaten».

    Jetzt fliegt `UpstreamSchemaError`, der `except`-Zweig greift, und die
    direkte URL wird wenigstens versucht. Genau das misst dieser Test.
    """
    from swiss_transport_mcp.occupancy import OCCUPANCY_DATASET, _fetch_occupancy_data

    direct = respx.get(
        f"https://data.opentransportdata.swiss/dataset/{OCCUPANCY_DATASET}"
        "/download/11_2026-02-28.json"
    ).mock(return_value=httpx.Response(200, json={"trains": []}))

    client = _FakeClient({"success": True, "help": "…"})  # Hülle ohne `result`
    out = await _fetch_occupancy_data(client, "11", "2026-02-28")

    assert direct.called, "der Fallback muss den Strukturfehler jetzt bemerken"
    assert out == {"trains": []}


@respx.mock
async def test_a_healthy_envelope_does_not_touch_the_fallback():
    """Die Gegenrichtung: ein gesundes Paket geht den normalen Weg."""
    from swiss_transport_mcp.occupancy import OCCUPANCY_DATASET, _fetch_occupancy_data

    resource_url = "https://data.opentransportdata.swiss/x/11_2026-02-28.json"
    respx.get(resource_url).mock(return_value=httpx.Response(200, json={"trains": ["ok"]}))
    direct = respx.get(
        f"https://data.opentransportdata.swiss/dataset/{OCCUPANCY_DATASET}"
        "/download/11_2026-02-28.json"
    ).mock(return_value=httpx.Response(200, json={"trains": []}))

    client = _FakeClient(
        {
            "success": True,
            "result": {"resources": [{"name": "11_2026-02-28", "url": resource_url}]},
        }
    )
    out = await _fetch_occupancy_data(client, "11", "2026-02-28")

    assert out == {"trains": ["ok"]}
    assert not direct.called, "der Fallback darf im Normalfall nicht anspringen"


# --- Die Ebene unter `result` ------------------------------------------------


class TestCkanResults:
    """Der Rest, den der Fix vom 2026-08-07 offen liess.

    Damals bestaetigte `ckan_request` den `result`-Block und hoerte dort auf.
    Das Katalog-Werkzeug las danach weiter `result.get("results", [])`, und eine
    Strukturaenderung eine Ebene tiefer ergab weiterhin eine leere
    Datensatzliste — dieselbe Antwort wie eine korrekte Suche ohne Treffer.

    Dass ein Fix seine eigene Ebene bestaetigt und die naechste offen laesst,
    ist die haeufigste Form dieses Fehlers: Er wandert nach unten statt zu
    verschwinden.
    """

    def test_a_result_without_results_is_rejected(self):
        with pytest.raises(UpstreamSchemaError) as excinfo:
            ckan_results({"count": 0, "sort": "score desc"})
        message = str(excinfo.value)
        assert "'sort'" in message, message
        assert "keine leere Suche" in message

    def test_a_non_object_result_is_rejected(self):
        with pytest.raises(UpstreamSchemaError) as excinfo:
            ckan_results(["a"])
        assert "list" in str(excinfo.value)

    def test_an_empty_search_still_passes(self):
        assert ckan_results({"count": 0, "results": []}) == []

    def test_a_normal_search_still_passes(self):
        rows = [{"name": "a"}]
        assert ckan_results({"count": 1, "results": rows}) == rows

    def test_the_catalogue_tool_uses_the_helper(self):
        """Der einzige Test hier mit Zaehnen.

        Die vier darueber rufen den Helfer direkt auf; der ist korrekt und
        bleibt gruen, auch wenn er nirgends haengt.
        """
        from pathlib import Path

        source = Path(__file__).parent.parent / "src" / "swiss_transport_mcp" / "server.py"
        body = source.read_text(encoding="utf-8")
        assert "api_client.ckan_results(result)" in body
        assert 'result.get("results", [])' not in body
