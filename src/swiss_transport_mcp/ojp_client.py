"""OJP (Open Journey Planner) XML client for opentransportdata.swiss.

Handles XML template loading, request building, and response parsing
for the OJP 2.0 API.

OJP 2.0 namespace: default ns is http://www.vdv.de/ojp,
SIRI elements use the siri: prefix.
"""

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# OJP 2.0 XML namespaces
OJP = "http://www.vdv.de/ojp"
SIRI = "http://www.siri.org.uk/siri"

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "xml_templates"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ---------------------------------------------------------------------------
# Namespace-aware XPath helpers
# ---------------------------------------------------------------------------

def _qn(tag: str) -> str:
    """Qualify a tag name with namespace.
    'siri:Longitude' → '{http://...siri}Longitude'
    'StopPlaceRef'   → '{http://...ojp}StopPlaceRef'
    """
    if tag.startswith("siri:"):
        return f"{{{SIRI}}}{tag[5:]}"
    return f"{{{OJP}}}{tag}"


def _xpath(path: str) -> str:
    """Convert a simple path to namespace-qualified XPath.
    './/StopPlaceRef'       → './/{...ojp}StopPlaceRef'
    './/siri:Longitude'     → './/{...siri}Longitude'
    './/Service/Mode/PtMode' → './/{...}Service/{...}Mode/{...}PtMode'
    """
    def replace_tag(m):
        tag = m.group(0)
        if tag in (".", "..", ""):
            return tag
        return _qn(tag)

    # Replace each tag-like segment (word chars and colons between slashes)
    return re.sub(r'[a-zA-Z_:][\w:]*', replace_tag, path)


def _find(el: ET.Element, path: str) -> ET.Element | None:
    """Find element using shorthand path with auto namespace qualification."""
    return el.find(_xpath(path))


def _findall_iter(el: ET.Element, tag: str) -> list[ET.Element]:
    """Find all elements with tag (OJP namespace) via iter."""
    return list(el.iter(_qn(tag)))


def _text(el: ET.Element, path: str) -> str | None:
    """Get text content of a nested element."""
    found = _find(el, path)
    return found.text if found is not None and found.text else None


# ---------------------------------------------------------------------------
# Request builders
# ---------------------------------------------------------------------------

def build_location_request(query: str, limit: int = 10) -> str:
    template = _load_template("location_request.xml")
    return template.format(timestamp=_now_iso(), query=_escape_xml(query), limit=limit)


def build_location_coord_request(latitude: float, longitude: float, limit: int = 10) -> str:
    template = _load_template("location_coord_request.xml")
    return template.format(timestamp=_now_iso(), latitude=latitude, longitude=longitude, limit=limit)


def build_stop_event_request(
    stop_ref: str, stop_name: str = "", dep_arr_time: str | None = None,
    limit: int = 10, event_type: str = "departure",
) -> str:
    template = _load_template("stop_event_request.xml")
    return template.format(
        timestamp=_now_iso(), place_ref=_build_place_ref(stop_ref),
        stop_name=_escape_xml(stop_name or stop_ref),
        dep_arr_time=dep_arr_time or _now_iso(), limit=limit, event_type=event_type,
    )


def build_trip_request(
    origin_ref: str, destination_ref: str, origin_name: str = "",
    destination_name: str = "", dep_time: str | None = None, limit: int = 5,
) -> str:
    template = _load_template("trip_request.xml")
    return template.format(
        timestamp=_now_iso(),
        origin_ref=_build_place_ref(origin_ref),
        origin_name=_escape_xml(origin_name or origin_ref),
        destination_ref=_build_place_ref(destination_ref),
        destination_name=_escape_xml(destination_name or destination_ref),
        dep_time=dep_time or _now_iso(), limit=limit,
    )


def _build_place_ref(ref: str) -> str:
    """StopPlaceRef for numeric IDs, LocationName for text."""
    if ref.isdigit():
        return f"<StopPlaceRef>{ref}</StopPlaceRef>"
    else:
        return f"<LocationName><Text>{_escape_xml(ref)}</Text></LocationName>"


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------

def parse_location_response(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    locations = []

    for place_result in _findall_iter(root, "PlaceResult"):
        loc: dict[str, Any] = {}

        stop_ref = _text(place_result, ".//StopPlaceRef")
        if stop_ref:
            loc["stop_id"] = stop_ref

        name = _text(place_result, ".//StopPlaceName/Text")
        if name:
            loc["name"] = name

        lon = _text(place_result, ".//siri:Longitude")
        lat = _text(place_result, ".//siri:Latitude")
        if lon and lat:
            loc["longitude"] = float(lon)
            loc["latitude"] = float(lat)

        prob = _text(place_result, ".//Probability")
        if prob:
            loc["match_quality"] = float(prob)

        modes = []
        for mode_el in _findall_iter(place_result, "PtMode"):
            if mode_el.text and mode_el.text not in modes:
                modes.append(mode_el.text)
        if modes:
            loc["transport_modes"] = modes

        if loc.get("name"):
            locations.append(loc)

    return locations


def parse_stop_event_response(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    events = []

    for result in _findall_iter(root, "StopEventResult"):
        ev: dict[str, Any] = {}

        ev_line = _text(result, ".//Service/PublishedServiceName/Text")
        if ev_line:
            ev["line"] = ev_line

        public_code = _text(result, ".//Service/PublicCode")
        if public_code and public_code != ev_line:
            ev["service_code"] = public_code

        mode = _text(result, ".//Service/Mode/PtMode")
        if mode:
            ev["mode"] = mode

        dest = _text(result, ".//Service/DestinationText/Text")
        if dest:
            ev["destination"] = dest

        origin = _text(result, ".//Service/OriginText/Text")
        if origin:
            ev["origin"] = origin

        train_num = _text(result, ".//Service/TrainNumber")
        if train_num:
            ev["train_number"] = train_num

        # Departure/arrival from ThisCall
        call_at = _find(result, ".//ThisCall/CallAtStop")
        if call_at is not None:
            for svc_type in ("ServiceDeparture", "ServiceArrival"):
                tt = _text(call_at, f".//{svc_type}/TimetabledTime")
                if tt:
                    ev["scheduled_time"] = tt
                    est = _text(call_at, f".//{svc_type}/EstimatedTime")
                    if est:
                        ev["realtime_time"] = est
                    break

            platform = _text(call_at, ".//PlannedQuay/Text")
            est_plat = _text(call_at, ".//EstimatedQuay/Text")
            if est_plat:
                ev["platform"] = est_plat
                if platform and platform != est_plat:
                    ev["planned_platform"] = platform
                    ev["platform_changed"] = True
            elif platform:
                ev["platform"] = platform

        # Delay
        if ev.get("scheduled_time") and ev.get("realtime_time"):
            try:
                sched = datetime.fromisoformat(ev["scheduled_time"].replace("Z", "+00:00"))
                real = datetime.fromisoformat(ev["realtime_time"].replace("Z", "+00:00"))
                ev["delay_minutes"] = round((real - sched).total_seconds() / 60)
            except (ValueError, TypeError):
                pass

        if ev.get("line") or ev.get("destination"):
            events.append(ev)

    return events


def parse_trip_response(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    trips = []

    for trip_result in _findall_iter(root, "TripResult"):
        trip: dict[str, Any] = {"legs": []}

        # OJP 2.0: details may be inside <Trip> wrapper
        trip_el = _find(trip_result, ".//Trip")
        src = trip_el if trip_el is not None else trip_result

        trip_id = _text(src, ".//Id")
        if trip_id:
            trip["trip_id"] = trip_id

        duration = _text(src, ".//Duration")
        if duration:
            trip["duration"] = _parse_duration(duration)

        transfers = _text(src, ".//Transfers")
        if transfers:
            trip["transfers"] = int(transfers)

        start_time = _text(src, ".//StartTime")
        end_time = _text(src, ".//EndTime")
        if start_time:
            trip["start_time"] = start_time
        if end_time:
            trip["end_time"] = end_time

        distance = _text(src, ".//Distance")
        if distance:
            trip["distance_meters"] = int(distance)

        for leg_el in _findall_iter(src, "Leg"):
            leg_data = _parse_leg(leg_el)
            if leg_data:
                trip["legs"].append(leg_data)

        if trip.get("legs"):
            trips.append(trip)

    return trips


def _parse_leg(leg_el: ET.Element) -> dict[str, Any] | None:
    leg: dict[str, Any] = {}

    leg_id = _text(leg_el, ".//Id")
    if leg_id:
        leg["leg_id"] = leg_id

    duration = _text(leg_el, ".//Duration")
    if duration:
        leg["duration"] = _parse_duration(duration)

    # Timed Leg (public transport)
    timed = _find(leg_el, ".//TimedLeg")
    if timed is not None:
        leg["type"] = "timed"

        board = _find(timed, ".//LegBoard")
        if board is not None:
            n = _text(board, ".//StopPointName/Text")
            if n:
                leg["from"] = n
            dep = _text(board, ".//ServiceDeparture/TimetabledTime")
            if dep:
                leg["departure"] = dep
            est_dep = _text(board, ".//ServiceDeparture/EstimatedTime")
            if est_dep:
                leg["departure_realtime"] = est_dep
            plat = _text(board, ".//PlannedQuay/Text")
            if plat:
                leg["platform_from"] = plat

        alight = _find(timed, ".//LegAlight")
        if alight is not None:
            n = _text(alight, ".//StopPointName/Text")
            if n:
                leg["to"] = n
            arr = _text(alight, ".//ServiceArrival/TimetabledTime")
            if arr:
                leg["arrival"] = arr
            est_arr = _text(alight, ".//ServiceArrival/EstimatedTime")
            if est_arr:
                leg["arrival_realtime"] = est_arr
            plat = _text(alight, ".//PlannedQuay/Text")
            if plat:
                leg["platform_to"] = plat

        service = _find(timed, ".//Service")
        if service is not None:
            line = _text(service, ".//PublishedServiceName/Text")
            if line:
                leg["line"] = line
            mode = _text(service, ".//Mode/PtMode")
            if mode:
                leg["mode"] = mode
            dest = _text(service, ".//DestinationText/Text")
            if dest:
                leg["direction"] = dest

        return leg

    # Continuous Leg (walking)
    continuous = _find(leg_el, ".//ContinuousLeg")
    if continuous is not None:
        leg["type"] = "walk"
        for endpoint, key in [("LegStart", "from"), ("LegEnd", "to")]:
            ep = _find(continuous, f".//{endpoint}")
            if ep is not None:
                n = _text(ep, ".//StopPointName/Text") or _text(ep, ".//LocationName/Text")
                if n:
                    leg[key] = n
        return leg

    # Transfer Leg
    transfer = _find(leg_el, ".//TransferLeg")
    if transfer is not None:
        leg["type"] = "transfer"
        return leg

    return None


def _parse_duration(iso_duration: str) -> str:
    try:
        text = iso_duration.replace("PT", "").replace("P", "")
        hours = minutes = seconds = 0
        if "H" in text:
            parts = text.split("H")
            hours = int(parts[0])
            text = parts[1]
        if "M" in text:
            parts = text.split("M")
            minutes = int(parts[0])
            text = parts[1] if len(parts) > 1 else ""
        if "S" in text:
            seconds = int(text.replace("S", "").split(".")[0] or "0")
        if hours and minutes:
            return f"{hours}h {minutes}min"
        elif hours:
            return f"{hours}h"
        elif minutes:
            return f"{minutes}min"
        elif seconds:
            return f"{seconds}s"
        return iso_duration
    except (ValueError, IndexError):
        return iso_duration


def parse_error_response(xml_text: str) -> str | None:
    try:
        root = ET.fromstring(xml_text)
        for ns, tag in [(OJP, "ErrorCondition"), (SIRI, "ErrorCondition"), (OJP, "ServiceNotAvailableError")]:
            for error in root.iter(f"{{{ns}}}{tag}"):
                for desc_tag in ["Description", f"{{{SIRI}}}Description", f"{{{OJP}}}Description"]:
                    desc = error.find(desc_tag)
                    if desc is not None and desc.text:
                        return desc.text
    except ET.ParseError:
        return f"Failed to parse XML: {xml_text[:200]}"
    return None
