"""Ein Ortsname wird zu einer Haltestellen-Kennung, bevor er in eine Anfrage geht.

WARUM. OJP 2.0 kennt keinen Ortsverweis, der nur aus einem Namen besteht: Ein
`PlaceRef` traegt eines von sechs echten Referenzelementen (`PlaceRefGroup`),
und freier Text gehoert nicht dazu. Der Server schickte trotzdem
`<LocationName>` — die Schreibweise aus OJP 1.0, in 2.0 abgeschafft. Die
Anfrage ging raus, die Quelle antwortete, und das Werkzeug meldete «No trips
found from 'Zürich HB' to 'Bern'»: ein Ausfall, der wie eine Antwort aussieht.

Der Vertrag dazu ist aufgezeichnet und wird in `test_ojp_contract.py`
gehalten. Hier steht das Verhalten, das daraus folgt.

Die XML-Antworten unten sind **ausgedacht**, nicht aufgezeichnet — die Quelle
verlangt einen Token, den CI nicht hat (`fixtures/upstream_auth_probe.json`).
Sie stehen als Reiz da, nicht als Beleg: Geprueft wird, was der Server
*sendet*, und das ist unabhaengig davon, ob die Antwort echt ist.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from swiss_transport_mcp import ojp_client, server
from swiss_transport_mcp.api_client import OJP_V2_URL
from swiss_transport_mcp.ojp_client import OJP, SIRI


def _one_place(stop_id: str = "8503000", name: str = "Zürich HB") -> str:
    return f"""<OJP xmlns="{OJP}" xmlns:siri="{SIRI}" version="2.0"><OJPResponse>
      <siri:ServiceDelivery><OJPLocationInformationDelivery><PlaceResult>
      <Place><StopPlace><StopPlaceRef>{stop_id}</StopPlaceRef>
      <StopPlaceName><Text>{name}</Text></StopPlaceName></StopPlace>
      <Name><Text>{name}</Text></Name>
      <GeoPosition><siri:Longitude>8.5417</siri:Longitude>
      <siri:Latitude>47.3769</siri:Latitude></GeoPosition></Place>
      <Complete>true</Complete></PlaceResult>
      </OJPLocationInformationDelivery></siri:ServiceDelivery></OJPResponse></OJP>"""


EMPTY = f'<OJP xmlns="{OJP}" xmlns:siri="{SIRI}" version="2.0"></OJP>'


@respx.mock
async def test_a_stop_id_costs_no_lookup(monkeypatch):
    """Eine Kennung ist schon eine Kennung — kein zusaetzlicher Aufruf."""
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    route = respx.post(OJP_V2_URL).mock(return_value=httpx.Response(200, text=_one_place()))

    assert await server._resolve_place("8503000") == ("8503000", "8503000")
    assert not route.called, "Aufloesung fuer eine Kennung angefragt — unnoetige Runde"


@respx.mock
async def test_a_quay_id_costs_no_lookup_either(monkeypatch):
    """Eine Haltekanten-Kennung ist auch eine Kennung.

    `8503000:0:31` ist kein Name. Wer sie als Namen behandelt, sucht nach einem
    Ort, der so heisst, findet keinen und meldet «No stop found» fuer eine
    Kennung, die die Suche selbst gerade ausgegeben hat.
    """
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    route = respx.post(OJP_V2_URL).mock(return_value=httpx.Response(200, text=EMPTY))

    assert await server._resolve_place("8503000:0:31") == ("8503000:0:31", "8503000:0:31")
    assert not route.called, "Haltekanten-Kennung als Name nachgeschlagen"


@respx.mock
async def test_a_name_becomes_the_id_of_its_best_match(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    respx.post(OJP_V2_URL).mock(
        return_value=httpx.Response(200, text=_one_place("8507000", "Bern"))
    )

    assert await server._resolve_place("Bern") == ("8507000", "Bern")


@respx.mock
async def test_an_unknown_name_says_so_instead_of_answering_emptily(monkeypatch):
    """«Diesen Ort finde ich nicht» ist eine andere Aussage als «keine Verbindung».

    Der alte Weg lieferte die zweite fuer den ersten Fall.
    """
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    respx.post(OJP_V2_URL).mock(return_value=httpx.Response(200, text=EMPTY))

    with pytest.raises(server.PlaceNotResolved) as excinfo:
        await server._resolve_place("Nirgendwo")
    assert "Nirgendwo" in str(excinfo.value)
    assert "transport_search_stop" in str(excinfo.value)


@respx.mock
async def test_a_name_leaves_the_process_as_a_reference_not_as_text(monkeypatch):
    """Die eigentliche Zusicherung: Was rausgeht, ist ein Verweis.

    Geprueft wird der gesendete Rumpf, nicht das Ergebnis — ein Ergebnis kann
    aus vielen Gruenden leer sein, der Rumpf nur aus einem.
    """
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    sent: list[str] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        sent.append(request.content.decode("utf-8"))
        return httpx.Response(200, text=_one_place("8507000", "Bern"))

    respx.post(OJP_V2_URL).mock(side_effect=_capture)

    stop_id, _ = await server._resolve_place("Bern")
    trip = ojp_client.build_trip_request(origin_ref="8503000", destination_ref=stop_id)

    assert "<StopPlaceRef>8507000</StopPlaceRef>" in trip
    assert "LocationName" not in trip, "OJP-1.0-Schreibweise wieder im Rumpf"
    # Die Aufloesungsanfrage selbst sucht per Name — das ist der eine Ort, an
    # dem OJP 2.0 freien Text vorsieht (`InitialInput/Name`).
    assert sent and "<Name>Bern</Name>" in sent[0]


class _Ctx:
    """Gerade so viel Context, wie die Werkzeuge benutzen."""

    async def info(self, *_args, **_kwargs) -> None:
        return None


@respx.mock
async def test_the_trip_tool_actually_resolves_before_it_asks(monkeypatch):
    """Die Zusicherung am Werkzeug, nicht am Hilfsmittel.

    `_resolve_place` einzeln zu pruefen sagt nichts darueber, ob
    `transport_trip_plan` es aufruft. Genau dort sass der Fehler: Das Werkzeug
    reichte den Namen unveraendert an den Rumpfbauer weiter.
    """
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    sent: list[str] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("utf-8")
        sent.append(body)
        if "OJPTripRequest" in body:
            return httpx.Response(200, text=EMPTY)
        return httpx.Response(200, text=_one_place("8507000", "Bern"))

    respx.post(OJP_V2_URL).mock(side_effect=_capture)

    await server.transport_trip_plan(
        server.TripPlanInput(origin="Zürich HB", destination="Bern"), _Ctx()
    )

    trip_bodies = [b for b in sent if "OJPTripRequest" in b]
    assert trip_bodies, "keine Reiseanfrage abgesetzt"
    assert "LocationName" not in trip_bodies[0]
    assert "<StopPlaceRef>8507000</StopPlaceRef>" in trip_bodies[0]


@respx.mock
async def test_an_unresolvable_origin_is_reported_as_such(monkeypatch):
    """Der Unterschied, auf den es ankommt, muss beim Aufrufer ankommen."""
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    respx.post(OJP_V2_URL).mock(return_value=httpx.Response(200, text=EMPTY))

    result = await server.transport_trip_plan(
        server.TripPlanInput(origin="Nirgendwo", destination="Bern"), _Ctx()
    )

    assert result.message and "Nirgendwo" in result.message
    assert "No trips found" not in result.message, (
        "unaufloesbarer Ort als «keine Verbindung» gemeldet — genau die "
        "Verwechslung, gegen die das hier angeht"
    )
