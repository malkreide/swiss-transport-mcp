"""
SIRI-SX Störungsmeldungen – Das Frühwarnsystem deines MCP-Servers.

Metapher: Stell dir SIRI-SX vor wie die Durchsagen am Bahnhof.
Ohne sie weiss Claude zwar den Fahrplan, aber nicht, dass 
der Zug gerade 20 Minuten Verspätung hat oder ausfällt.

API-Details:
- Endpoint: GET https://api.opentransportdata.swiss/la/siri-sx
- Format: XML (SIRI-SX / VDV 736 Standard)
- Auth: Bearer Token im Header
- Inhalt: Alle aktiven Störungen im Schweizer ÖV
- Sprachen: DE, FR, IT, EN
- Rate Limit: 2 Abfragen/Minute (Sliding Window)

Die XML-Antwort ist riesig (alle Störungen der Schweiz!).
Deshalb parsen wir gezielt und liefern nur relevante Infos ans LLM.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
from .api_infrastructure import TransportAPIClient, APIError

# SIRI-SX Namespaces – die XML-Struktur nutzt mehrere Namensräume
NS = {
    "siri": "http://www.siri.org.uk/siri",
}


async def get_disruptions(
    client: TransportAPIClient,
    filter_text: Optional[str] = None,
    language: str = "DE",
    max_results: int = 20,
) -> str:
    """
    Holt aktuelle Störungsmeldungen aus SIRI-SX.
    
    Args:
        client: Der konfigurierte API-Client
        filter_text: Optionaler Suchbegriff (z.B. "Zürich", "S-Bahn", "IC 1")
        language: Sprache der Meldungen (DE, FR, IT, EN)
        max_results: Maximale Anzahl Ergebnisse (verhindert Kontext-Overflow)
    
    Returns:
        Formatierter Text mit allen relevanten Störungen.
        
    Warum Text statt JSON? Weil ein LLM natürlichen Text besser versteht
    als verschachtelte JSON-Strukturen. Das ist der Trick: 
    Wir wandeln maschinenlesbare Daten in menschenlesbaren Kontext um.
    """
    try:
        xml_text = await client.get("siri_sx")
    except APIError as e:
        return f"⚠️ Störungsmeldungen konnten nicht abgerufen werden: {e}"

    return _parse_siri_sx(xml_text, filter_text, language, max_results)


def _parse_siri_sx(
    xml_text: str,
    filter_text: Optional[str],
    language: str,
    max_results: int,
) -> str:
    """
    Parst die SIRI-SX XML-Antwort und extrahiert strukturierte Störungsmeldungen.
    
    Die XML-Struktur ist:
    Siri > ServiceDelivery > SituationExchangeDelivery > Situations 
    > PtSituationElement (eine pro Störung)
    
    Jedes PtSituationElement enthält:
    - CreationTime: Wann wurde die Störung erstellt?
    - ValidityPeriod: Von wann bis wann gilt sie?
    - Severity: Wie schwerwiegend? (slight, normal, severe, noImpact)
    - Summary: Kurztitel (mehrsprachig)
    - Description: Detailtext (mehrsprachig)
    - PublishingActions: Anzeigeaktionen mit passengerInformation
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return "⚠️ SIRI-SX Antwort konnte nicht geparst werden (ungültiges XML)."

    # Situationen finden – mit und ohne Namespace
    situations = root.findall(".//siri:PtSituationElement", NS)
    if not situations:
        # Fallback ohne Namespace (manche Endpoints liefern ohne Prefix)
        situations = root.findall(".//{http://www.siri.org.uk/siri}PtSituationElement")
    if not situations:
        # Noch ein Fallback: direkt suchen
        situations = root.findall(".//PtSituationElement")

    if not situations:
        return "✅ Aktuell keine Störungsmeldungen im Schweizer ÖV."

    disruptions = []
    lang_tag = language.lower()  # "de", "fr", "it", "en"

    for sit in situations:
        disruption = _extract_disruption(sit, lang_tag)
        if disruption is None:
            continue

        # Textfilter anwenden
        if filter_text:
            search = filter_text.lower()
            searchable = f"{disruption['title']} {disruption['description']} {disruption['affected']}".lower()
            if search not in searchable:
                continue

        disruptions.append(disruption)

    if not disruptions:
        if filter_text:
            return f"✅ Keine Störungen gefunden, die '{filter_text}' betreffen."
        return "✅ Aktuell keine Störungsmeldungen im Schweizer ÖV."

    # Nach Schweregrad sortieren: severe > normal > slight
    severity_order = {"severe": 0, "normal": 1, "slight": 2, "noImpact": 3, "unknown": 4}
    disruptions.sort(key=lambda d: severity_order.get(d["severity"], 4))

    # Auf max_results begrenzen
    disruptions = disruptions[:max_results]

    # Formatieren
    lines = [f"🚨 {len(disruptions)} aktive Störung(en) im Schweizer ÖV:\n"]
    for i, d in enumerate(disruptions, 1):
        severity_icon = {"severe": "🔴", "normal": "🟡", "slight": "🟢", "noImpact": "⚪"}.get(d["severity"], "⚪")
        lines.append(f"--- Störung {i} ---")
        lines.append(f"{severity_icon} Schweregrad: {d['severity']}")
        lines.append(f"📋 {d['title']}")
        if d["description"]:
            # Beschreibung kürzen, wenn zu lang (LLM-Kontext schonen)
            desc = d["description"][:500]
            if len(d["description"]) > 500:
                desc += "... (gekürzt)"
            lines.append(f"📝 {desc}")
        if d["affected"]:
            lines.append(f"🚆 Betrifft: {d['affected']}")
        if d["valid_from"] or d["valid_to"]:
            period = f"⏰ Gültig: {d['valid_from'] or '?'} bis {d['valid_to'] or 'unbekannt'}"
            lines.append(period)
        lines.append("")

    return "\n".join(lines)


def _extract_disruption(element: ET.Element, lang: str) -> Optional[dict]:
    """Extrahiert eine einzelne Störung aus einem PtSituationElement."""
    
    def find_text(parent, tag, ns=NS):
        """Findet Text in einem Element, mit mehreren Fallback-Strategien."""
        # Mit Namespace
        el = parent.find(f"siri:{tag}", ns)
        if el is not None and el.text:
            return el.text.strip()
        # Ohne Namespace
        el = parent.find(tag)
        if el is not None and el.text:
            return el.text.strip()
        # Mit vollem Namespace
        el = parent.find(f"{{http://www.siri.org.uk/siri}}{tag}")
        if el is not None and el.text:
            return el.text.strip()
        return ""

    def find_multilang(parent, tag):
        """
        Findet mehrsprachigen Text. 
        SIRI-SX hat oft: <Summary xml:lang="de">Text</Summary>
        oder <Summary><DefaultedTextStructure xml:lang="de">Text</...></Summary>
        """
        # Direkter Ansatz: Tag mit xml:lang Attribut
        for el in parent.iter():
            if el.tag.endswith(tag) or tag in el.tag:
                if el.get("{http://www.w3.org/XML/1998/namespace}lang", "").lower() == lang:
                    return el.text.strip() if el.text else ""
        # Fallback: Erster Text, den wir finden
        return find_text(parent, tag)

    # Hauptinformationen extrahieren
    title = find_multilang(element, "Summary") or find_text(element, "Summary")
    description = find_multilang(element, "Description") or find_text(element, "Description")
    severity = find_text(element, "Severity") or "unknown"

    # Zeitraum
    valid_from = find_text(element, "StartTime")
    valid_to = find_text(element, "EndTime")

    # Betroffene Linien/Strecken aus PublishingActions extrahieren
    affected_parts = []

    # PublishingActions > PassengerInformationAction > TextualContent
    for action in element.iter():
        tag_name = action.tag.split("}")[-1] if "}" in action.tag else action.tag
        if tag_name == "PublishingAction":
            for child in action.iter():
                child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if child_tag in ("LineRef", "StopPointRef", "OperatorRef"):
                    if child.text:
                        affected_parts.append(child.text.strip())

    # Auch aus Affects-Block
    for affects in element.iter():
        tag_name = affects.tag.split("}")[-1] if "}" in affects.tag else affects.tag
        if tag_name in ("LineRef", "StopPointRef", "PublishedLineName"):
            if affects.text:
                affected_parts.append(affects.text.strip())

    if not title and not description:
        return None

    return {
        "title": title,
        "description": description,
        "severity": severity.lower(),
        "valid_from": _format_datetime(valid_from),
        "valid_to": _format_datetime(valid_to),
        "affected": ", ".join(set(affected_parts)) if affected_parts else "",
    }


def _format_datetime(dt_str: str) -> str:
    """Formatiert ISO-Datetime in lesbares Schweizer Format."""
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return dt_str
