#!/usr/bin/env python3
"""Zeichnet auf, was sich an diesem Server ohne Zugangsdaten aufzeichnen laesst.

    python scripts/record_fixtures.py
    python scripts/record_fixtures.py --check   # nur pruefen, nichts schreiben

WARUM ES DIESES SKRIPT GIBT. Ein handgeschriebener Mock kodiert die Annahme
seines Autors und kann sie deshalb prinzipiell nicht widerlegen: Produktivcode
und Fixture stammen aus demselben Kopf, derselben Stunde, derselben Lektuere der
Doku. Wo beide irren, irren beide gleich, und die Suite bleibt gruen.

DIESER SERVER IST EIN SONDERFALL, und der Sonderfall ist der Grund, warum hier
etwas anderes aufgezeichnet wird als in den Schwester-Repos.

Alle vier Datenquellen verlangen einen Bearer-Token aus dem API-Manager von
opentransportdata.swiss. Ohne Token antwortet keine von ihnen mit Daten
— gemessen und in `upstream_auth_probe.json` festgehalten, statt behauptet.
Eine Antwort-Fixture laesst sich hier also nicht ehrlich aufzeichnen.

Aufzeichnen laesst sich der **Vertrag**: OJP 2.0 ist eine CEN-Norm
(CEN/TS 17118), und das XML-Schema dazu ist oeffentlich. Es sagt, welche
Elemente es gibt, welche Pflicht sind und wo sie stehen duerfen — und damit
genau das, worueber sich Produktivcode und handgeschriebene Fixture einig sein
koennen, ohne dass es stimmt.

WAS HIER **NICHT** PASSIERT: Das Schema selbst wird nicht ins Repo kopiert. Das
Quell-Repository fuehrt keine Lizenzdatei, und die zugrunde liegende Norm ist
kostenpflichtig; 424 KB fremdes XSD in ein MIT-Repo zu legen waere eine
Lizenzentscheidung, die dieses Skript nicht treffen darf. Aufgezeichnet wird
ein **abgeleiteter Index** — Elementnamen, die Strukturen, auf die dieser
Server baut, und die Aufzaehlungen, die er als Werte sendet — zusammen mit
Quell-URL und SHA-256 jeder gelesenen Schema-Datei. Der Index ist damit
nachpruefbar: `--check` laedt dieselben Dateien am festen Tag `v2.0` erneut und
faellt, wenn sich Hash oder Ableitung geaendert haben.

Ohne Aufzeichnungsdatum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht»
nicht mehr zu unterscheiden — die Datei sieht gleich aus.
"""

from __future__ import annotations

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

XS = "http://www.w3.org/2001/XMLSchema"

# Fester Tag, nicht `master`. Ein Branch verschiebt sich, und ein Index gegen
# einen beweglichen Stand ist wieder undatiert — nur unauffaelliger.
OJP_REPO = "https://github.com/VDVde/OJP"
OJP_REF = "v2.0"
OJP_RAW = f"https://raw.githubusercontent.com/VDVde/OJP/{OJP_REF}/OJP"
# Die Wurzeldatei liegt eine Ebene hoeher und traegt `OJP`, `OJPRequest` und
# `OJPResponse` — die drei Elemente, mit denen jede Anfrage anfaengt.
OJP_ROOT_URL = f"https://raw.githubusercontent.com/VDVde/OJP/{OJP_REF}/OJP.xsd"

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
CONTRACT = FIXTURES / "ojp_2_0_contract.json"
PROBE = FIXTURES / "upstream_auth_probe.json"

# Die Schema-Dateien des OJP-Namensraums. `OJP_All.xsd` listet sie; die Liste
# steht hier trotzdem ausgeschrieben, damit eine stillschweigend verschwundene
# Datei auffaellt statt einfach zu fehlen.
SCHEMA_FILES = (
    "OJP_All.xsd",
    "OJP_Availability.xsd",
    "OJP_Common.xsd",
    "OJP_FacilitySupport.xsd",
    "OJP_Fare.xsd",
    "OJP_FareSupport.xsd",
    "OJP_JourneySupport.xsd",
    "OJP_Lines.xsd",
    "OJP_Locations.xsd",
    "OJP_ModesSupport.xsd",
    "OJP_PlaceSupport.xsd",
    "OJP_Requests.xsd",
    "OJP_RequestSupport.xsd",
    "OJP_SituationSupport.xsd",
    "OJP_Status.xsd",
    "OJP_StopEvents.xsd",
    "OJP_TripInfo.xsd",
    "OJP_Trips.xsd",
    "OJP_Utility.xsd",
)

# Die Strukturen, auf die dieser Server baut. Alles andere aus dem Schema
# aufzunehmen waere ein Vollabzug durch die Hintertuer.
WANTED_TYPES = (
    "PlaceRefStructure",
    "PlaceStructure",
    "PlaceResultStructure",
    "PlaceContextStructure",
    "StopPlaceStructure",
    "StopPointStructure",
    "TopographicPlaceStructure",
    "PointOfInterestStructure",
    "AddressStructure",
    "ContinuousLegStructure",
    "LegBoardStructure",
    "LegAlightStructure",
    "InitialLocationInputStructure",
    "PlaceParamStructure",
    "TripParamStructure",
    "StopEventParamStructure",
)
WANTED_GROUPS = (
    "PlaceRefGroup",
    "StopPlaceGroup",
    "StopPointGroup",
    "LocationInformationRequestGroup",
    "StopEventRequestGroup",
    "TripRequestGroup",
    "PlaceDataFilterGroup",
    "PlacePolicyGroup",
    "PlaceSortingGroup",
    "TripDataFilterGroup",
    "TripMobilityFilterGroup",
    "TripPolicyGroup",
    "TripContentFilterGroup",
    "StopEventDataFilterGroup",
    "StopEventPolicyGroup",
    "StopEventContentFilterGroup",
)
WANTED_ENUMS = (
    "PlaceTypeEnumeration",
    "StopEventTypeEnumeration",
    "UseRealtimeDataEnumeration",
)

# Die vier Datenquellen. Alle vier verlangen einen Token; die Sonde haelt fest,
# WAS sie ohne ihn antworten, statt es zu behaupten.
UPSTREAMS = (
    ("ojp", "GET", "https://api.opentransportdata.swiss/ojp20"),
    ("ckan", "GET", "https://api.opentransportdata.swiss/ckan-api/package_search?rows=1"),
    ("siri_sx", "GET", "https://api.opentransportdata.swiss/la/siri-sx"),
    ("formation", "GET", "https://api.opentransportdata.swiss/formation/v2/formations_full"),
)


def _children(node: ET.Element, in_choice: bool = False) -> list[dict[str, Any]]:
    """Die Kindelemente einer Struktur, so wie das Schema sie fuehrt.

    Bewusst **nicht** aufgeloest: Ein `<xs:group ref="...">` bleibt als Verweis
    stehen. Wer hier aufloeste, schriebe seine eigene Lesart in den Index und
    koennte sie danach nicht mehr widerlegen — dasselbe Muster wie beim
    handgeschriebenen Mock, eine Ebene hoeher.
    """
    out: list[dict[str, Any]] = []
    for child in node:
        tag = child.tag.removeprefix(f"{{{XS}}}")
        if tag in ("sequence", "complexContent", "extension", "all"):
            out += _children(child, in_choice)
        elif tag == "choice":
            out += _children(child, True)
        elif tag == "annotation":
            continue
        elif tag == "element":
            entry: dict[str, Any] = {
                "min": int(child.get("minOccurs", "1")),
                "choice": in_choice,
            }
            if child.get("name"):
                entry["name"] = child.get("name")
                if child.get("type"):
                    entry["type"] = child.get("type")
            else:
                entry["ref"] = child.get("ref")
            out.append(entry)
        elif tag == "group":
            out.append(
                {
                    "group_ref": child.get("ref"),
                    "min": int(child.get("minOccurs", "1")),
                    "choice": in_choice,
                }
            )
    return out


def _derive(sources: dict[str, str]) -> dict[str, Any]:
    """Den Vertragsindex aus den Schema-Texten ableiten."""
    element_names: set[str] = set()
    types: dict[str, Any] = {}
    groups: dict[str, Any] = {}
    enums: dict[str, list[str]] = {}

    all_groups: dict[str, Any] = {}
    for text in sources.values():
        root = ET.fromstring(text)
        for el in root.iter(f"{{{XS}}}element"):
            if el.get("name"):
                element_names.add(el.get("name"))
        for ct in root.iter(f"{{{XS}}}complexType"):
            name = ct.get("name")
            if name in WANTED_TYPES:
                types[name] = _children(ct)
        for gr in root.iter(f"{{{XS}}}group"):
            if gr.get("name"):
                all_groups[gr.get("name")] = _children(gr)
        for st in root.iter(f"{{{XS}}}simpleType"):
            name = st.get("name")
            if name in WANTED_ENUMS:
                enums[name] = [
                    e.get("value") for e in st.iter(f"{{{XS}}}enumeration") if e.get("value")
                ]

    # Die Gruppen transitiv schliessen. WANTED_GROUPS ist eine Saat, keine
    # Liste: Eine Gruppe, die auf eine nicht aufgezeichnete verweist, macht die
    # Kinderliste unvollstaendig, ohne dass man es ihr ansieht — und «erlaubt»
    # hiesse dann «erlaubt, soweit aufgezeichnet».
    pending = list(WANTED_GROUPS) + [
        c["group_ref"] for children in types.values() for c in children if c.get("group_ref")
    ]
    while pending:
        name = pending.pop()
        if name in groups:
            continue
        if name not in all_groups:
            raise SystemExit(
                f"Gruppe {name!r} im Schema nicht gefunden — Aufzeichnung unvollstaendig."
            )
        groups[name] = all_groups[name]
        pending += [c["group_ref"] for c in groups[name] if c.get("group_ref")]

    missing = (
        [f"complexType {n}" for n in WANTED_TYPES if n not in types]
        + [f"group {n}" for n in WANTED_GROUPS if n not in groups]
        + [f"simpleType {n}" for n in WANTED_ENUMS if n not in enums]
    )
    if missing:
        # Eine Struktur, die es nicht mehr gibt, ist selbst der Befund: Der
        # Server baut auf sie. Sie stillschweigend wegzulassen hiesse, einen
        # Test zu erzeugen, der nichts mehr prueft und Erfolg meldet.
        raise SystemExit(
            "Im Schema nicht mehr gefunden: "
            + ", ".join(missing)
            + "\nDer Server baut darauf. Erst klaeren, dann den Index neu schreiben."
        )

    return {
        "element_names": sorted(element_names),
        "types": types,
        "groups": groups,
        "enumerations": enums,
    }


def _fetch_schema(client: httpx.Client) -> tuple[dict[str, str], list[dict[str, Any]]]:
    sources: dict[str, str] = {}
    manifest: list[dict[str, Any]] = []
    for name in ("OJP.xsd", *SCHEMA_FILES):
        url = OJP_ROOT_URL if name == "OJP.xsd" else f"{OJP_RAW}/{name}"
        r = client.get(url)
        r.raise_for_status()
        raw = r.content
        sources[name] = raw.decode("utf-8")
        manifest.append(
            {
                "name": name,
                "url": url,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        print(f"ok  {name:<26} {len(raw):>7} B")
    return sources, manifest


def _probe_upstreams(client: httpx.Client) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name, method, url in UPSTREAMS:
        try:
            r = client.request(method, url)
            status: int | str = r.status_code
        except httpx.HTTPError as exc:  # nicht erreichbar ist auch ein Befund
            status = f"unreachable: {type(exc).__name__}"
        results.append({"name": name, "method": method, "url": url, "status": status})
        print(f"--  {name:<12} {method} -> {status}")
    return results


def record(check_only: bool = False) -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).strftime("%Y-%m-%d")

    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        sources, manifest = _fetch_schema(client)
        derived = _derive(sources)
        print()
        probes = _probe_upstreams(client)

    if not any(str(p["status"]).startswith(("401", "403")) for p in probes):
        # Die Begruendung dieses ganzen Skripts ist, dass die Quellen einen
        # Token verlangen. Antworten sie ploetzlich ohne, ist das kein Grund
        # weiterzumachen, sondern der Anlass, echte Antworten aufzuzeichnen.
        raise SystemExit(
            "Keine der vier Quellen antwortet mehr mit 401/403. Dann sind echte "
            "Antwort-Fixtures moeglich und dieses Skript ist die falsche Antwort."
        )

    contract = {
        "schema": "OJP 2.0 (CEN/TS 17118)",
        "source_repo": OJP_REPO,
        "source_ref": OJP_REF,
        "recorded_at": recorded_at,
        "files": manifest,
        **derived,
    }
    probe_doc = {"recorded_at": recorded_at, "probes": probes}

    if check_only:
        return _check(contract, probe_doc)

    CONTRACT.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PROBE.write_text(json.dumps(probe_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_provenance(recorded_at, contract, probe_doc)
    print(f"\nPROVENANCE.md geschrieben, Aufzeichnungsdatum {recorded_at}")
    return 0


def _check(contract: dict[str, Any], probe_doc: dict[str, Any]) -> int:
    """Den abgeleiteten Index gegen die Quelle nachrechnen.

    Das Aufzeichnungsdatum und die Sonde bleiben aussen vor: Datum aendert sich
    per Definition, und die Statuscodes der Quellen sind eine Messung von
    damals, keine Zusicherung fuer heute. Geprueft wird, was der Index
    behauptet: dieselben Dateien, dieselben Hashes, dieselbe Ableitung.
    """
    if not CONTRACT.exists():
        print(f"FEHLER: {CONTRACT.name} fehlt — erst ohne --check laufen lassen.", file=sys.stderr)
        return 1
    stored = json.loads(CONTRACT.read_text(encoding="utf-8"))
    volatile = {"recorded_at"}
    differences = [
        key
        for key in set(stored) | set(contract)
        if key not in volatile and stored.get(key) != contract.get(key)
    ]
    if differences:
        print(
            "FEHLER: Der aufgezeichnete Vertrag stimmt nicht mehr mit "
            f"{OJP_REPO}@{OJP_REF} ueberein.\n  Abweichend: {', '.join(sorted(differences))}\n"
            "  Ein fester Tag sollte sich nicht bewegen — erst klaeren, dann neu aufzeichnen.",
            file=sys.stderr,
        )
        return 1
    print(
        f"\nok  Vertrag stimmt mit {OJP_REPO}@{OJP_REF} ueberein "
        f"({len(contract['files'])} Schema-Dateien, {len(contract['element_names'])} Elemente)"
    )
    print(f"    Aufgezeichnet am {stored['recorded_at']}, geprueft am {probe_doc['recorded_at']}")
    return 0


def _write_provenance(
    recorded_at: str, contract: dict[str, Any], probe_doc: dict[str, Any]
) -> None:
    lines = [
        "# Herkunft der Fixtures",
        "",
        "**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**",
        "",
        f"Aufgezeichnet am **{recorded_at}**.",
        "",
        "Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht",
        "mehr zu unterscheiden — die Datei sieht gleich aus.",
        "",
        "## Was hier NICHT aufgezeichnet ist: Antworten",
        "",
        "Alle vier Datenquellen dieses Servers verlangen einen Bearer-Token aus dem",
        "API-Manager von opentransportdata.swiss. Ohne Token liefert keine von",
        "ihnen Daten. Gemessen am Aufzeichnungstag, festgehalten in",
        "`upstream_auth_probe.json`:",
        "",
        "| Quelle | Methode | Antwort ohne Token |",
        "|---|---|---|",
    ]
    for p in probe_doc["probes"]:
        lines.append(f"| `{p['name']}` | {p['method']} | **{p['status']}** |")
    lines += [
        "",
        "Die Payloads in den Testmodulen sind damit weiterhin **ausgedacht** und",
        "tragen kein Datum. Das ist der Ist-Zustand und keine Nachlaessigkeit",
        "dieses Laufs. Wer einen Token hat, zeichnet echte Antworten auf; das",
        "Skript daneben ist dafuer die Vorlage.",
        "",
        "## Was aufgezeichnet ist: der Vertrag",
        "",
        "OJP 2.0 ist eine CEN-Norm (CEN/TS 17118). Ihr XML-Schema ist oeffentlich",
        "und sagt, welche Elemente es gibt, welche Pflicht sind und wo sie stehen",
        "duerfen — also genau das, worueber sich Produktivcode und",
        "handgeschriebene Fixture einig sein koennen, ohne dass es stimmt.",
        "",
        f"Quelle: `{contract['source_repo']}`, fester Tag **`{contract['source_ref']}`**.",
        "Ein Branch verschiebt sich; ein Index gegen einen beweglichen Stand waere",
        "wieder undatiert, nur unauffaelliger.",
        "",
        "### Das Schema selbst liegt NICHT im Repo",
        "",
        "Das Quell-Repository fuehrt keine Lizenzdatei, und die zugrunde liegende",
        "Norm ist kostenpflichtig. 424 KB fremdes XSD in ein MIT-Repo zu kopieren",
        "waere eine Lizenzentscheidung, die ein Aufzeichnungsskript nicht treffen",
        "darf. `ojp_2_0_contract.json` ist deshalb ein **abgeleiteter Index**:",
        "",
        f"- {len(contract['element_names'])} Elementnamen des OJP-Namensraums",
        f"- {len(contract['types'])} Strukturen und {len(contract['groups'])} Gruppen, "
        "auf die dieser Server baut",
        f"- {len(contract['enumerations'])} Aufzaehlungen, aus denen er Werte sendet",
        "",
        "Gruppenverweise (`<xs:group ref=...>`) bleiben im Index **unaufgeloest**.",
        "Wer sie aufloest, schreibt seine eigene Lesart hinein und kann sie danach",
        "nicht mehr widerlegen — dasselbe Muster wie beim handgeschriebenen Mock,",
        "eine Ebene hoeher.",
        "",
        "Die Ableitung ist nachrechenbar: `python scripts/record_fixtures.py --check`",
        "laedt dieselben Dateien am selben Tag und faellt, wenn Hash oder Ableitung",
        "abweichen.",
        "",
        "**Der OJP-Namensraum ist vollstaendig erfasst, der SIRI-Namensraum nicht.**",
        "Elemente mit `siri:`-Praefix stehen in einem eigenen Schema, das hier nicht",
        "gelesen wird; Pruefungen gegen diesen Index sagen ueber sie nichts.",
        "",
        "### Gelesene Schema-Dateien",
        "",
        "| Datei | Groesse | SHA-256 |",
        "|---|---:|---|",
    ]
    for f in contract["files"]:
        lines.append(f"| `{f['name']}` | {f['bytes']} B | `{f['sha256']}` |")
    lines += [
        "",
        f"`OJP.xsd` unter `{OJP_ROOT_URL}`, alle uebrigen unter `{OJP_RAW}/`.",
        "",
    ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(record(check_only="--check" in sys.argv))
    except httpx.HTTPError as exc:
        print(f"FEHLER: Quelle nicht erreichbar: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
