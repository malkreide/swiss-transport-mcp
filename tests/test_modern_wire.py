"""Spec `2026-07-28` am eigenen HTTP-Endpunkt gemessen, nicht aus Konstanten geschlossen.

`tests/test_protocol_version.py` haelt die beiden Revisionen gegen die
SDK-Konstanten und nannte das selbst die schwaechere Form — mit der Begruendung,
dieses Repo baue keine ASGI-App, durch die sich eine Anfrage schicken liesse.
**Das stimmte nicht.** `server._build_http_app` baut genau die App, die `main()`
unter uvicorn stellt, und `tests/test_cors.py` fuhr schon seit Laengerem einen
`TestClient` dagegen. Die Begruendung war also keine Messgrenze, sondern eine
ungepruefte Annahme ueber das eigene Repo; dieses Modul ersetzt sie durch die
Messung, die immer moeglich war.

Was hier faehrt, ist der **Einzelaustausch** der Revision `2026-07-28`: ein
selbsttragendes POST ohne `initialize`, ohne `Mcp-Session-Id` — eine
JSON-RPC-Anfrage hinein, eine Antwort heraus. Der Umschlag steht in
`params._meta` (Protokollrevision + Client-Faehigkeiten), die Wegweiser stehen
als Kopfzeilen daneben (`MCP-Protocol-Version`, `Mcp-Method`, bei
namenstragenden Methoden `Mcp-Name`).

Zwei Dinge, die beim Schreiben Zeit gekostet haben und deshalb hier stehen:

* **Die `base_url` ist nicht kosmetisch.** `_build_http_app` schaltet bei einer
  Loopback-Bindung die DNS-Rebinding-Pruefung scharf (SEC-005). Der
  Vorgabe-Host des `TestClient` heisst `testserver`, steht auf keiner
  Erlaubnisliste, und die App antwortet mit HTTP 421 — bevor irgendetwas
  Protokollartiges passiert. Ein Test, der das nicht beachtet, prueft die
  Host-Pruefung und nennt es Protokoll.
* **Die Aeren mischen sich nicht.** Ein Umschlag, der `2025-11-25` nennt, ist
  kein moderner Request und faellt auf den Legacy-Pfad zurueck, wo ohne
  Handshake die Session fehlt. Das ist unten eine eigene Zusicherung, weil der
  naheliegende Fehlschluss — «neuer Umschlag, alte Nummer, wird schon
  ausgehandelt» — genau hier scheitert.
"""

from __future__ import annotations

import json
import pathlib
import re
from collections.abc import Iterator
from typing import Any

import pytest
from starlette.testclient import TestClient

from swiss_transport_mcp import __homepage__, __version__
from swiss_transport_mcp.server import (
    LIST_CACHE_TTL_MS,
    _build_http_app,
)
from swiss_transport_mcp.tool_integrity import load_pinned_manifest

# Die Revision, gegen die dieses Modul misst. Bewusst als Literal und nicht aus
# `mcp.types.version` importiert: eine Messung gegen `LATEST_MODERN_VERSION`
# waere gruen, egal welche Revision das SDK morgen erreicht, und haette damit
# genau die Aussage verloren, um die es geht. Dass Literal und SDK-Konstante
# uebereinstimmen, prueft `test_protocol_version.py`.
MODERN = "2026-07-28"
HANDSHAKE_CEILING = "2025-11-25"

# Der Umschlag, den jede moderne Anfrage in `params._meta` tragen MUSS.
PROTOCOL_VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"

ORIGIN = "https://claude.ai"
HOST = "127.0.0.1"
PORT = 8080

# JSON-RPC-Fehlercodes der Ladder aus `mcp.shared.inbound`, hier als Zahl statt
# als Import: der Test soll die Drahtform festhalten, die ein fremder Client
# sieht, nicht die Benennung im SDK.
INVALID_PARAMS = -32602
HEADER_MISMATCH = -32020
UNSUPPORTED_PROTOCOL_VERSION = -32022


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Die App, die `main()` unter uvicorn stellt — nicht eine Nachbildung.

    Als Kontextmanager, damit der Lifespan laeuft: ohne ihn hat der
    Session-Manager keine Task-Group und jede Anfrage endet in einem
    `RuntimeError` statt in einer Antwort.
    """
    app = _build_http_app("streamable-http", [ORIGIN], host=HOST, port=PORT)
    with TestClient(app, base_url=f"http://{HOST}:{PORT}") as test_client:
        yield test_client


def modern_post(
    client: TestClient,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    version: str = MODERN,
    headers: dict[str, str] | None = None,
    envelope: bool = True,
    request_id: int = 1,
):
    """Ein Einzelaustausch-POST, so wie ein `2026-07-28`-Client ihn absetzt."""
    body_params = dict(params or {})
    if envelope:
        body_params["_meta"] = {
            PROTOCOL_VERSION_KEY: version,
            CLIENT_CAPABILITIES_KEY: {},
        }
    request_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": version,
        "Mcp-Method": method,
    }
    request_headers.update(headers or {})
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": body_params},
        headers=request_headers,
    )


def result_of(response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "error" not in payload, json.dumps(payload)
    return payload["result"]


# ---------------------------------------------------------------------------
# Der Endpunkt bedient die Revision ueberhaupt
# ---------------------------------------------------------------------------


def test_ein_einzelaustausch_beantwortet_tools_list_ohne_handshake(client: TestClient) -> None:
    """Die Kernzusicherung: kein `initialize`, keine Session, trotzdem Antwort.

    Faellt dieser Test, spricht der Server die Revision nicht — alles Weitere
    unten waere dann Fassade.
    """
    result = result_of(modern_post(client, "tools/list"))

    assert result["resultType"] == "complete"
    assert sorted(tool["name"] for tool in result["tools"]) == sorted(load_pinned_manifest())


def test_server_discover_nennt_die_revision_die_es_bedient(client: TestClient) -> None:
    """`server/discover` ersetzt den Handshake als Ort, an dem ein Client fragt,
    womit er es zu tun hat."""
    result = result_of(modern_post(client, "server/discover"))

    assert result["supportedVersions"] == [MODERN]
    assert set(result["capabilities"]) == {"tools", "resources", "prompts"}


def test_ein_werkzeug_laeuft_ueber_den_einzelaustausch(client: TestClient) -> None:
    """Auflisten ist die halbe Miete; gemessen wird auch ein echter Aufruf.

    `check_transport_api_status` braucht keinen API-Schluessel — es berichtet
    gerade ueber deren Fehlen — und ist damit das eine Werkzeug, das ohne
    Netzzugang eine vollstaendige Antwort liefert.
    """
    result = result_of(
        modern_post(
            client,
            "tools/call",
            {"name": "check_transport_api_status", "arguments": {}},
            headers={"Mcp-Name": "check_transport_api_status"},
        )
    )

    assert result["content"], result
    assert "Swiss Transport APIs" in result["content"][0]["text"]


# ---------------------------------------------------------------------------
# Wer antwortet da — `Implementation` auf dem Draht
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["tools/list", "resources/list", "server/discover"])
def test_jede_antwort_nennt_version_und_herkunft_des_servers(
    client: TestClient, method: str
) -> None:
    """Der Befund, der dieses Modul ausgeloest hat.

    `2026-07-28` kennt kein `initialize` und damit keinen einmaligen Ort fuer
    `serverInfo`; die Revision legt die `Implementation` stattdessen in das
    `_meta` **jeder** Antwort. Bis der Konstruktor `version=` bekam, stand dort
    `{"name": "swiss_transport_mcp", "version": ""}` — nicht einmal falsch,
    sondern leer, und das auf jeder Antwort statt einmal pro Verbindung.

    Der `version`-Parameter von `MCPServer` defaultet auf `""` und warnt nicht.
    Nichts im Repo waere rot geworden: `test_cache_hints.py` liest dieselben
    Antworten und sieht `_meta` nicht an.
    """
    info = result_of(modern_post(client, method))["_meta"][SERVER_INFO_KEY]

    assert info["version"] == __version__ != ""
    assert info["name"] == "swiss_transport_mcp"
    assert info["title"] == "Swiss Public Transport"
    assert info["websiteUrl"] == __homepage__


def test_auch_der_alte_handshake_nennt_die_version(client: TestClient) -> None:
    """Gegenprobe zur Zusicherung darueber: der leere String war nie ein
    2026-Problem allein.

    Sie steht hier, damit niemand den Fix fuer eine Eigenheit der modernen Aera
    haelt und ihn beim naechsten Umbau mit ihr zusammen wegnimmt.
    """
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": HANDSHAKE_CEILING,
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "1"},
            },
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200, response.text
    assert f'"version":"{__version__}"' in response.text


# ---------------------------------------------------------------------------
# Frischehinweise (SEP-2549) — ueber den Transport, nicht nur im Prozess
# ---------------------------------------------------------------------------


def test_der_frischehinweis_ueberlebt_den_transport(client: TestClient) -> None:
    """`test_cache_hints.py` misst denselben Hinweis ueber eine In-Prozess-
    `ClientSession`. Das sagt, dass der Handler ihn setzt — nicht, dass er die
    HTTP-Serialisierung erreicht, wo ein Client ihn tatsaechlich liest.
    """
    result = result_of(modern_post(client, "tools/list"))

    assert result["ttlMs"] == LIST_CACHE_TTL_MS
    assert result["cacheScope"] == "public"


def test_ein_werkzeugaufruf_traegt_keinen_frischehinweis(client: TestClient) -> None:
    """Die negative Haelfte: gehinweist sind Verzeichnisse, nicht Ergebnisse.

    Ohne diese Zeile waere der Test darueber auch dann gruen, wenn jemand den
    Hinweis pauschal auf jede Antwort setzte.
    """
    result = result_of(
        modern_post(
            client,
            "tools/call",
            {"name": "check_transport_api_status", "arguments": {}},
            headers={"Mcp-Name": "check_transport_api_status"},
        )
    )

    assert "ttlMs" not in result
    assert "cacheScope" not in result


# ---------------------------------------------------------------------------
# Die Ladder: was der Server ablehnt, und mit welchem Code
# ---------------------------------------------------------------------------


def test_ohne_umschlag_gibt_es_keine_moderne_anfrage(client: TestClient) -> None:
    """Sprosse 1: `params._meta` traegt Revision und Client-Faehigkeiten."""
    response = modern_post(client, "tools/list", envelope=False)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == INVALID_PARAMS


@pytest.mark.parametrize(
    ("headers", "params", "method"),
    [
        pytest.param({"Mcp-Method": "prompts/list"}, None, "tools/list", id="methode"),
        pytest.param(
            {"Mcp-Name": "transport_search_stop"},
            {"name": "check_transport_api_status", "arguments": {}},
            "tools/call",
            id="name",
        ),
    ],
)
def test_ein_wegweiser_der_dem_rumpf_widerspricht_wird_abgelehnt(
    client: TestClient, headers: dict[str, str], params: dict[str, Any] | None, method: str
) -> None:
    """Sprosse 2: die Kopfzeilen sind der Weg, an dem ein Proxy routet.

    Weichen sie vom Rumpf ab, koennte der Proxy eine andere Anfrage sehen als
    der Server — deshalb ist das ein Fehler und keine stille Bevorzugung einer
    der beiden Quellen. Beide namenstragenden Faelle einzeln, weil `Mcp-Name`
    nur fuer einen Teil der Methoden gilt und ein gemeinsamer Test nicht zeigen
    wuerde, welcher der beiden Vergleiche noch greift.
    """
    response = modern_post(client, method, params, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == HEADER_MISMATCH


def test_eine_unbediente_revision_bekommt_die_liste_der_bedienten(client: TestClient) -> None:
    """Sprosse 3 — und die einzige Absage hier, die dem Client weiterhilft.

    Der Fehler fuehrt mit, was der Server kann; ein blosses «nein» zwaenge zum
    Raten. Genau das ist der Unterschied, den `CLAUDE.md` an `lotId` festhaelt:
    eine deterministische Absage muss sagen, was stattdessen ginge.
    """
    response = modern_post(client, "tools/list", version="2099-01-01")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == UNSUPPORTED_PROTOCOL_VERSION
    assert error["data"] == {"supported": [MODERN], "requested": "2099-01-01"}


# ---------------------------------------------------------------------------
# Die Grenze zwischen den beiden Aeren
# ---------------------------------------------------------------------------


def test_ein_moderner_umschlag_mit_alter_revision_ist_keine_moderne_anfrage(
    client: TestClient,
) -> None:
    """Die Aeren handeln nicht miteinander aus, sie schliessen sich aus.

    `2025-11-25` gehoert dem Handshake. In einem Pro-Request-Umschlag macht die
    Nummer die Anfrage nicht modern — sie faellt auf den Legacy-Pfad, der ohne
    `initialize` keine Session kennt. Wer hier eine Aushandlung erwartet,
    debuggt spaeter eine fehlende Session und sucht den Fehler im Umschlag.
    """
    response = modern_post(client, "tools/list", version=HANDSHAKE_CEILING)

    assert response.status_code == 400
    assert "session" in response.json()["error"]["message"].lower()


@pytest.mark.parametrize(
    ("requested", "negotiated"),
    [
        ("2024-11-05", "2024-11-05"),
        (HANDSHAKE_CEILING, HANDSHAKE_CEILING),
        (MODERN, HANDSHAKE_CEILING),
        ("2099-01-01", HANDSHAKE_CEILING),
    ],
)
def test_der_handshake_deckelt_und_verweigert_nicht(
    client: TestClient, requested: str, negotiated: str
) -> None:
    """Was die READMEs ueber die Handshake-Aera behaupten, an derselben App
    gemessen.

    Die dritte Zeile ist die interessante: ein `initialize`, das `2026-07-28`
    verlangt, bekommt **nicht** die moderne Aera, sondern die Decke der alten.
    Die Revision waehlt die Form der ersten Anfrage, nicht die Nummer darin.
    """
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": requested,
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "1"},
            },
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200, response.text
    assert f'"protocolVersion":"{negotiated}"' in response.text


# ---------------------------------------------------------------------------
# SEP-2577: die abgekuendigte Logging-Faehigkeit
# ---------------------------------------------------------------------------

# Die `Context`-Methoden, die das SDK mit
# «The logging capability is deprecated as of 2026-07-28 (SEP-2577)» markiert.
_DEPRECATED_CONTEXT_LOGGING = ("log", "debug", "info", "warning", "error")
_CTX_LOG_CALL = re.compile(r"\bctx\.(?:" + "|".join(_DEPRECATED_CONTEXT_LOGGING) + r")\s*\(")


def test_die_regex_findet_den_aufruf_den_sie_finden_soll() -> None:
    """Positivkontrolle, und sie ist hier keine Formalie.

    Der Test darunter ist eine Abwesenheitszusicherung: Er bleibt gruen, wenn
    der Ausdruck nichts trifft — auch dann, wenn er gar nichts mehr treffen
    KANN, etwa weil jemand das Muster kaputt macht. Ein «nicht gefunden» wird
    erst durch einen gleichzeitigen Fund zur Messung.
    """
    assert _CTX_LOG_CALL.search('        await ctx.info(f"Fetching {x}")')
    assert not _CTX_LOG_CALL.search("logger.info('Fetching %s', x)")


def test_kein_werkzeug_schreibt_mehr_ueber_die_abgekuendigte_logging_faehigkeit() -> None:
    """Zwei Werkzeuge meldeten ihren Fortschritt frueher per `ctx.info`.

    Bei `2026-07-28` kommt das per Vorgabe bei niemandem an: Die Zustellung ist
    ein Opt-in pro Anfrage ueber den reservierten `_meta`-Schluessel
    `io.modelcontextprotocol/logLevel`; ohne ihn liefert
    `allowed_log_levels` eine LEERE Menge und der Eintrag wird verworfen. Eine
    Fortschrittsmeldung, die nur ankommt, wenn der Aufrufer vorher Logs
    bestellt hat, ist kein Betriebslog — sie steht jetzt im stderr-Logger des
    Servers (OBS-003/004).

    Das SDK markiert die Methoden ausserdem als abgekuendigt. Warnungen sind in
    diesem Repo kein Gate, faellt also niemandem auf; diese Zeile schon.
    """
    offenders = [
        f"{path.relative_to(SRC)}:{number}: {line.strip()}"
        for path in sorted(SRC.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _CTX_LOG_CALL.search(line)
    ]

    assert not offenders, "abgekuendigte Logging-Faehigkeit (SEP-2577): " + "; ".join(offenders)
