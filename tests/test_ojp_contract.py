"""Die Anfragen und Parser gegen den aufgezeichneten OJP-2.0-Vertrag halten.

WARUM ES DIESE DATEI GIBT. Jeder andere Test in diesem Repo prueft gegen eine
handgeschriebene Fixture, und die Fixture ist aus derselben Annahme geschrieben
wie der Code. Wo beide irren, irren beide gleich. Die vier Datenquellen
verlangen einen Token, den CI nicht hat — eine echte Antwort kann hier also
nicht widersprechen.

Der Vertrag kann es. OJP 2.0 ist eine CEN-Norm mit oeffentlichem XML-Schema; es
sagt, welche Elemente es gibt und welche Pflicht sind. `ojp_2_0_contract.json`
ist der daraus abgeleitete Index, aufgezeichnet und datiert (PROVENANCE.md).

Die Pruefungen hier sind deshalb bewusst gegen den **Index** geschrieben und
nicht gegen ausgeschriebene Erwartungen: Ein Test, der `"Name"` als Literal
enthaelt, sagt nur, dass zwei Stellen im Repo dasselbe raten.

WAS SIE NICHT KOENNEN: Sie pruefen gegen die Norm, nicht gegen die
Implementierung von opentransportdata.swiss. Ein Feld, das die Norm erlaubt und
die Quelle nie schickt, faellt hier nicht auf — dafuer braucht es einen Token
und die Live-Suite.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from swiss_transport_mcp import ojp_client
from swiss_transport_mcp.ojp_client import OJP, SIRI, _build_place_ref
from tests.fixture_data import (
    allowed_children,
    choice_refs,
    ojp_elements,
    required_children,
    upstream_auth_probe,
)

TEMPLATES = sorted((ojp_client.TEMPLATE_DIR).glob("*.xml"))

# Die Platzhalter der Vorlagen mit etwas fuellen, das als XML durchgeht. Die
# Werte sind egal — geprueft werden Elementnamen und Struktur, nicht Inhalte.
_FILLER = {
    "timestamp": "2026-08-07T00:00:00Z",
    "query": "Zuerich HB",
    "limit": "5",
    "latitude": "47.3769",
    "longitude": "8.5417",
    "place_ref": "<StopPlaceRef>8503000</StopPlaceRef>",
    "origin_ref": "<StopPlaceRef>8503000</StopPlaceRef>",
    "destination_ref": "<StopPlaceRef>8507000</StopPlaceRef>",
    "stop_name": "Zuerich HB",
    "origin_name": "Zuerich HB",
    "destination_name": "Bern",
    "dep_arr_time": "2026-08-07T00:00:00Z",
    "dep_time": "2026-08-07T00:00:00Z",
    "event_type": "departure",
}


def _rendered(path) -> ET.Element:
    return ET.fromstring(path.read_text(encoding="utf-8").format(**_FILLER))


def _ojp_tags(node: ET.Element) -> set[str]:
    """Alle Elementnamen im OJP-Namensraum unterhalb (und inklusive) `node`."""
    return {
        el.tag.removeprefix(f"{{{OJP}}}") for el in node.iter() if el.tag.startswith(f"{{{OJP}}}")
    }


assert TEMPLATES, "keine Anfrage-Vorlagen gefunden — der Test pruefte sonst nichts"


# ---------------------------------------------------------------------------
# Die Anfragen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_request_template_uses_only_real_ojp_elements(template):
    """Kein Element in einer Anfrage, das OJP 2.0 nicht kennt.

    Ein erfundenes Element ist kein Syntaxfehler: Die Anfrage geht raus, die
    Quelle antwortet, und was fehlt, fehlt still.
    """
    unknown = _ojp_tags(_rendered(template)) - ojp_elements()
    assert not unknown, (
        f"{template.name} sendet Elemente, die es in OJP 2.0 nicht gibt: {sorted(unknown)}"
    )


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_place_ref_carries_its_mandatory_children(template):
    """Jedes `PlaceRef` traegt, was der Vertrag als Pflicht fuehrt.

    Die Pflichtliste kommt aus dem aufgezeichneten `PlaceRefGroup`, nicht aus
    diesem Test — sonst pruefte er die eigene Annahme.
    """
    mandatory = required_children("PlaceRefGroup")
    assert mandatory, "PlaceRefGroup fuehrt keine Pflichtkinder — Index pruefen"

    refs = list(_rendered(template).iter(f"{{{OJP}}}PlaceRef"))
    if not refs:
        pytest.skip(f"{template.name} enthaelt kein PlaceRef")

    for ref in refs:
        present = {child.tag.removeprefix(f"{{{OJP}}}") for child in ref}
        missing = [name for name in mandatory if name not in present]
        assert not missing, (
            f"{template.name}: PlaceRef ohne Pflichtkind {missing}; vorhanden: {sorted(present)}"
        )


# Welcher Parameterblock zu welcher Anfrage gehoert. Die Zuordnung steht im
# Schema (`OJPTripRequest` -> `Params` vom Typ `TripParamStructure`); hier
# stehen nur die Namen, die Inhalte kommen aus dem aufgezeichneten Vertrag.
PARAM_BLOCKS = {
    "trip_request.xml": ("Params", "TripParamStructure"),
    "stop_event_request.xml": ("Params", "StopEventParamStructure"),
    "location_request.xml": ("Restrictions", "PlaceParamStructure"),
    "location_coord_request.xml": ("Restrictions", "PlaceParamStructure"),
}


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_request_parameters_are_parameters_the_schema_knows(template):
    """Jeder gesendete Parameter steht in der Struktur, die ihn tragen soll.

    Ein Parameter mit falschem Namen ist die leiseste Art, etwas nicht zu
    bekommen: Die Anfrage geht durch, und was angefordert werden sollte, wurde
    nie angefordert.
    """
    block, structure = PARAM_BLOCKS[template.name]
    permitted = allowed_children(structure)
    assert permitted, f"{structure} fuehrt keine Kinder — Index pruefen"

    nodes = list(_rendered(template).iter(f"{{{OJP}}}{block}"))
    assert nodes, f"{template.name} enthaelt kein <{block}> — Vorlage geaendert?"

    for node in nodes:
        sent = [child.tag.removeprefix(f"{{{OJP}}}") for child in node]
        unknown = [name for name in sent if name not in permitted]
        assert not unknown, (
            f"{template.name}: <{block}> sendet {unknown}, die {structure} nicht kennt. "
            f"Erlaubt: {permitted}"
        )
        # `xs:sequence` ist geordnet. Die richtigen Elemente in der falschen
        # Reihenfolge sind ebenso ungueltig wie die falschen Elemente — nur
        # sieht man es beim Lesen nicht.
        order = [permitted.index(name) for name in sent]
        assert order == sorted(order), (
            f"{template.name}: <{block}> sendet {sent} — das Schema ordnet sie "
            f"{[n for n in permitted if n in sent]}"
        )


def test_place_ref_builder_emits_an_allowed_reference():
    """`_build_place_ref` darf nur Verweise bauen, die der Vertrag zulaesst."""
    allowed = choice_refs("PlaceRefGroup")
    built = _build_place_ref("8503000")
    tag = re.match(r"<(\w+)", built).group(1)
    assert tag in allowed, (
        f"_build_place_ref baut <{tag}>, erlaubt sind in PlaceRefGroup: {sorted(allowed)}"
    )


def test_place_ref_builder_refuses_a_name_it_cannot_reference():
    """Ein Name ist in OJP 2.0 kein Verweis — und darf keiner vorgetaeuscht werden.

    `PlaceRefGroup` verlangt eine Auswahl aus echten Referenzelementen. Ein
    freier Text gehoert nicht dazu; es gibt in OJP 2.0 keine Form «finde den
    Ort, der so heisst» innerhalb eines `PlaceRef`. Wer hier trotzdem etwas
    baut, erzeugt eine Anfrage, auf die die Quelle mit einer leeren Liste
    antwortet — ein Ausfall, der wie eine Antwort aussieht.
    """
    with pytest.raises(ValueError) as excinfo:
        _build_place_ref("Zürich HB")
    assert "transport_search_stop" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Die Parser
# ---------------------------------------------------------------------------


def test_parsers_look_for_elements_that_exist():
    """Kein Parser sucht nach einem Element, das OJP 2.0 nicht kennt.

    Ein Pfad ins Leere wirft nichts. Er liefert `None`, das Feld bleibt weg,
    und die Antwort sieht vollstaendig aus.
    """
    source = (ojp_client.__file__ and open(ojp_client.__file__, encoding="utf-8").read()) or ""
    # Die Pfade, die `_text`/`_find`/`_findall_iter` bekommen: Namen ohne
    # `siri:`-Praefix; der SIRI-Namensraum steht nicht im Index.
    looked_up = {
        part
        for path in re.findall(r'"(\.//[^"]+)"', source)
        for part in path.removeprefix(".//").split("/")
        # `{...}`-Stellen sind f-String-Platzhalter: Der Name steht erst zur
        # Laufzeit fest und ist an seiner Einsetzstelle geprueft.
        if part and not part.startswith("siri:") and "{" not in part
    }
    unknown = looked_up - ojp_elements()
    assert not unknown, (
        f"ojp_client sucht nach Elementen, die es in OJP 2.0 nicht gibt: {sorted(unknown)}"
    )


def test_location_parser_reads_the_name_every_place_carries():
    """Ein Ort ohne `StopPlaceName` ist trotzdem ein Ort.

    `PlaceStructure` fuehrt `Name` als Pflichtfeld — fuer jede der fuenf
    Ortsarten. Nur eine davon (`StopPlace`) hat zusaetzlich einen eigenen
    `StopPlaceName`. Wer allein auf den liest, verwirft Haltekanten, Adressen,
    Ortschaften und POIs stillschweigend und meldet «nichts gefunden».

    Die Probe wird aus dem Vertrag gebaut: `StopPointGroup` sagt, wie eine
    Haltekante heisst, `PlaceStructure` sagt, dass `Name` daneben Pflicht ist.
    """
    assert "Name" in required_children("PlaceStructure")
    stop_point_name = required_children("StopPointGroup")
    assert stop_point_name, "StopPointGroup fuehrt keinen Pflichtnamen — Index pruefen"

    xml = f"""<OJP xmlns="{OJP}" xmlns:siri="{SIRI}" version="2.0"><OJPResponse>
      <siri:ServiceDelivery><OJPLocationInformationDelivery><PlaceResult>
        <Place>
          <StopPoint>
            <siri:StopPointRef>8503000:0:31</siri:StopPointRef>
            <{stop_point_name[0]}><Text>Zürich HB, Gleis 31</Text></{stop_point_name[0]}>
          </StopPoint>
          <Name><Text>Zürich HB, Gleis 31</Text></Name>
          <GeoPosition><siri:Longitude>8.5417</siri:Longitude>
            <siri:Latitude>47.3769</siri:Latitude></GeoPosition>
          <Mode><PtMode>rail</PtMode></Mode>
        </Place>
        <Complete>true</Complete>
        <Probability>0.9</Probability>
      </PlaceResult></OJPLocationInformationDelivery></siri:ServiceDelivery>
    </OJPResponse></OJP>"""

    locations = ojp_client.parse_location_response(xml)
    assert locations, "Haltekante verworfen — die Antwort saehe aus wie «nichts gefunden»"
    assert locations[0]["name"] == "Zürich HB, Gleis 31"
    assert locations[0]["stop_id"] == "8503000:0:31", "StopPointRef nicht als Kennung gelesen"


# ---------------------------------------------------------------------------
# Warum hier kein echter Payload liegt
# ---------------------------------------------------------------------------


def test_upstreams_still_need_a_token():
    """Die Begruendung der ganzen Fixture-Lage, als Zusicherung.

    Antworten die Quellen eines Tages ohne Token, ist der abgeleitete Vertrag
    nicht mehr das Beste, was sich aufzeichnen laesst — dann gehoeren echte
    Antworten her. Dieser Test haelt fest, dass das noch nicht so ist, und
    nennt beim Fallen den Grund.
    """
    probes = upstream_auth_probe()["probes"]
    assert len(probes) == 4, "vier Datenquellen erwartet"
    open_sources = [p["name"] for p in probes if str(p["status"]).startswith("2")]
    assert not open_sources, (
        f"Diese Quellen antworten inzwischen ohne Token: {open_sources}. "
        "Dann echte Antwort-Fixtures aufzeichnen statt nur den Vertrag."
    )
