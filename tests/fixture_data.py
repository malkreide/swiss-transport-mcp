"""Zugriff auf die aufgezeichneten Fixtures.

Ein fehlender Name ist hier ein Fehler und keine leere Struktur. Ein Loader,
der bei einem Tippfehler `{}` zurueckgibt, erzeugt einen Test, der nichts mehr
prueft und trotzdem Erfolg meldet — die teuerste Sorte gruen.

Herkunft, Datum und Auswahlregel stehen in `fixtures/PROVENANCE.md`.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"


@cache
def _load(name: str) -> Any:
    path = FIXTURES / name
    if not path.exists():
        available = sorted(p.name for p in FIXTURES.glob("*.json"))
        raise FileNotFoundError(
            f"Fixture {name!r} gibt es nicht. Vorhanden: {available}. "
            "Neu aufzeichnen mit `python scripts/record_fixtures.py`."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def ojp_contract() -> dict[str, Any]:
    """Der abgeleitete OJP-2.0-Vertragsindex.

    Kein Vollabzug des Schemas: Der OJP-Namensraum ist vollstaendig erfasst,
    der SIRI-Namensraum nicht. Siehe PROVENANCE.md.
    """
    return _load("ojp_2_0_contract.json")


def upstream_auth_probe() -> dict[str, Any]:
    """Was die vier Datenquellen ohne Bearer-Token antworten — gemessen."""
    return _load("upstream_auth_probe.json")


def ojp_elements() -> set[str]:
    """Alle Elementnamen des OJP-2.0-Namensraums."""
    return set(ojp_contract()["element_names"])


def required_children(structure: str) -> list[str]:
    """Die Pflicht-Kindelemente einer Struktur oder Gruppe, benannt.

    Ohne die aus einer `xs:choice` — dort ist genau eines Pflicht, aber nicht
    ein bestimmtes. Gruppenverweise bleiben unaufgeloest (siehe PROVENANCE.md)
    und tauchen hier deshalb nicht auf.
    """
    return [
        c["name"]
        for c in _node(structure)
        if c.get("min", 1) >= 1 and not c["choice"] and c.get("name")
    ]


def _node(structure: str) -> list[dict[str, Any]]:
    contract = ojp_contract()
    node = contract["groups"].get(structure) or contract["types"].get(structure)
    if node is None:
        raise KeyError(
            f"{structure!r} steht nicht im aufgezeichneten Vertrag. "
            f"Gruppen: {sorted(contract['groups'])}; Typen: {sorted(contract['types'])}."
        )
    return node


def allowed_children(structure: str) -> list[str]:
    """Alle erlaubten Kindelemente, Gruppenverweise aufgeloest, in Schema-Reihenfolge.

    Der Index haelt Gruppenverweise bewusst offen (siehe PROVENANCE.md); die
    Aufloesung passiert hier, wo sie sichtbar ist und nicht in der Aufzeichnung
    verschwindet. Ein Verweis auf eine nicht aufgezeichnete Gruppe ist ein
    Fehler — sonst faellt ein ganzer Zweig stillschweigend weg und die Liste
    saehe vollstaendig aus.
    """
    out: list[str] = []
    for child in _node(structure):
        if child.get("group_ref"):
            out += allowed_children(child["group_ref"])
        elif child.get("name"):
            out.append(child["name"])
        elif child.get("ref"):
            out.append(child["ref"].removeprefix("siri:"))
    return out


def choice_refs(structure: str) -> set[str]:
    """Die Namen der Alternativen einer `xs:choice`, Verweise mitgezaehlt."""
    return {c.get("name") or c.get("ref") for c in _node(structure) if c["choice"]} - {None}
