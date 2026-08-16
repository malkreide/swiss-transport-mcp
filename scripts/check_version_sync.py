"""
Versions-Synchronität prüfen — und sicherstellen, dass in `src/` keine Version
von Hand gepflegt wird.

`pyproject.toml` ist die einzige Quelle der Wahrheit. Verglichen werden alle
Stellen, die dieselbe Nummer wiederholen:

  - `server.json` (MCP-Registry-Manifest): `version` und jedes
    `packages[*].version`
  - die Versions-Badges der READMEs

Hintergrund: `publish.yml` synchronisiert `server.json` beim Veröffentlichen
aus dem Tag-Namen — die *committete* Version wirkt also nie auf das
publizierte Artefakt und fällt deshalb nicht auf, wenn sie veraltet. Die
README-Badges erzwingt überhaupt nichts.

Zweiter Teil: in `src/` darf keine Versionsnummer stehen. Der Laufzeit-Wert
kommt aus den Paket-Metadaten (`importlib.metadata.version()`); ein wieder
eingefügtes Literal wäre der Beginn derselben Drift, die im ganzen Portfolio
falsche User-Agents erzeugt hat.

Dritter Teil: der ruff-Pin steht an zwei Stellen — `ruff==X.Y.Z` in den
Workflows und `rev: vX.Y.Z` beim `ruff-pre-commit`-Repo. Laufen sie
auseinander, meldet lokal und in der CI je eine andere ruff-Version
Abweichungen, die niemand verursacht hat, und der Diff, in dem es auffällt,
hat damit nichts zu tun. Verglichen wird nur, was existiert: Ein Repo ohne
pre-commit-Konfiguration ist kein Fehler, ein Repo mit zwei ungleichen Pins
schon.

Verwendung:
    python scripts/check_version_sync.py     # exit 1 bei Abweichung

Bewusst nur Standardbibliothek — der Check braucht keine Projekt-Installation
und läuft damit auch in schlanken CI-Jobs. Auf Python 3.10 (noch keine
`tomllib`) greift ein Minimal-Parser für die zwei benötigten Felder.
"""

import io
import json
import re
import sys
import tokenize
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 — tomllib kam erst mit 3.11
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
SERVER_JSON = ROOT / "server.json"
SRC = ROOT / "src"

# Shields.io-Badge: ![Version](https://img.shields.io/badge/version-X.Y.Z-blue)
_BADGE = re.compile(r"img\.shields\.io/badge/[Vv]ersion-([^-\s)]+)-")


def code_lines(text: str) -> list[str]:
    """Zeilen ohne Kommentare.

    Kommentare dokumentieren im Portfolio genau die Drift, die dieser Check
    verhindern soll — etwa «the User-Agent in server.py carried
    "bakom-mcp/1.0"». Sie zu melden wäre ein Fehlalarm, der die CI grundlos
    rot färbt. Ausgeschnitten wird per `tokenize`, nicht per `split("#")`:
    ein `#` in einem String-Literal darf die Zeile nicht abschneiden.
    """
    lines = text.splitlines()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                row, col = tok.start
                lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Nicht parsebare Datei: lieber vollständig prüfen als still übergehen.
        return text.splitlines()
    return lines


def norm(token: str) -> str:
    """Kleingeschrieben und ohne Trennzeichen — zum Vergleich von Produkt-Token
    und Dist-Namen.

    Das Produkt-Token im User-Agent ist nicht immer der Dist-Name:
    `swisstopo-mcp` sendet `SwisstopoMCP/0.1`. Ein wörtlicher Vergleich liess
    dort ein hartkodiertes Literal als sauber durchgehen — genau das Versagen,
    gegen das dieser Check existiert.
    """
    return re.sub(r"[^a-z0-9]", "", token.lower())


# Irgendein Produkt-Token, gefolgt von einer gepunkteten Zahl. Welches davon
# uns gehört, entscheidet der normalisierte Vergleich mit dem Dist-Namen —
# fremde Token (`Mozilla/5.0`, `httpx/0.27`) fallen so heraus.
_UA = re.compile(r"""([A-Za-z][A-Za-z0-9_.+-]*)/(\d+\.\d[^\s"']*)""")


def own_ua_versions(line: str, dist: str) -> list[str]:
    """Versionen aus den User-Agents, deren Produkt-Token uns gehört.

    Eigene Funktion, damit die Zeile auch bei `line-length = 88` passt: im
    Portfolio stehen 88, 100 und 120 nebeneinander, und `ruff format` zieht
    einen Ausdruck zusammen, sobald er in die jeweilige Breite passt. Eine
    mehrzeilige Comprehension waere damit in der einen Haelfte der Repos
    formatgerecht und in der anderen nicht.
    """
    return [m.group(2) for m in _UA.finditer(line) if norm(m.group(1)) == norm(dist)]


def find_hardcoded(dist: str) -> list[tuple[str, int, str]]:
    """Manuell gepflegte Versionen in `src/`.

    Zwei Formen kommen im Portfolio vor: der User-Agent (`<token>/1.2.3`) und
    die `__version__`-Zuweisung. Die Projekt-URL trägt denselben Namen, aber
    keine Ziffer danach — deshalb verlangt das Muster eine gepunktete Zahl.

    Der Fallback im `except PackageNotFoundError`-Zweig (`0.0.0+source`) ist
    ausdrücklich **kein** Treffer: er behauptet gerade keine Version. Erkannt
    wird er am lokalen Segment nach `+`, nicht an der Zahl davor — `0.0.0`
    allein sieht wie eine echte Version aus.
    """
    hits: list[tuple[str, int, str]] = []
    if not SRC.is_dir():
        return hits

    dunder = re.compile(r"""__version__\s*=\s*["']([^"']+)["']""")

    for path in sorted(SRC.rglob("*.py")):
        for lineno, line in enumerate(code_lines(path.read_text(encoding="utf-8")), start=1):
            values = own_ua_versions(line, dist)
            for m in dunder.finditer(line):
                if re.match(r"\d+\.\d", m.group(1)):
                    values.append(m.group(1))
            if any("+" not in v for v in values):
                hits.append((str(path.relative_to(ROOT)), lineno, line.strip()))
    return hits


def collect_declared(expected: str) -> list[tuple[str, str]]:
    """Alle Stellen, die die Version wiederholen — je (Bezeichnung, Wert)."""
    found: list[tuple[str, str]] = []

    if SERVER_JSON.exists():
        server = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
        found.append(("server.json → version", server.get("version", "")))
        for i, pkg in enumerate(server.get("packages", [])):
            found.append((f"server.json → packages[{i}].version", pkg.get("version", "")))

    for readme in sorted(ROOT.glob("README*.md")):
        for match in _BADGE.finditer(readme.read_text(encoding="utf-8")):
            found.append((f"{readme.name} → Versions-Badge", match.group(1)))

    return found


# `ruff==0.16.1` — auch mitten in einer Sammel-Zeile (`pip install ruff==X foo`).
_RUFF_CI = re.compile(r"""\bruff==([0-9][^\s'"]*)""")

# Der Kopf eines pre-commit-Eintrags. Gesplittet wird daran, damit `rev:` dem
# richtigen `repo:` zugeordnet wird — ein `rev:` irgendwo in der Datei gehört
# sonst genauso gut zu einem anderen Hook.
_PC_REPO = re.compile(r"^\s*-\s*repo:", re.MULTILINE)
_PC_REV = re.compile(r"""^\s*rev:\s*['"]?v?([^\s'"#]+)""", re.MULTILINE)


def strip_comments(text: str) -> str:
    """`#`-Kommentare entfernen, Zeichenketten in Anführungszeichen ausgenommen.

    Gilt für YAML und TOML gleichermassen — beide kommentieren mit `#` und
    quoten ihre Werte.

    Nötig, weil die Kommentare hier genau die Drift beschreiben, die der Check
    verhindern soll — `.pre-commit-config.yaml` erklärt seinen eigenen Pin mit
    «v0.16.1 == ruff==0.16.1». Ohne dieses Ausschneiden läse der Check den
    Kommentar als weiteren Fundort und meldete Übereinstimmung oder Drift
    anhand von Prosa statt anhand der Konfiguration.
    """
    out = []
    for line in text.splitlines():
        quote = None
        for i, ch in enumerate(line):
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == "#":
                line = line[:i]
                break
        out.append(line)
    return "\n".join(out)


# Eine ruff-Angabe in einer Abhängigkeitsliste: `"ruff==0.16.1"`, `"ruff>=0.4.0"`,
# `"ruff"`. Nach `ruff` (samt optionalen Extras) darf nur ein Vergleichsoperator
# oder das schliessende Anführungszeichen folgen — sonst zählte `"ruff-lsp"` mit.
# Die Anführungszeichen im Muster halten ausserdem `[tool.ruff]` heraus.
_TOML_RUFF = re.compile(r"""["']ruff(?:\[[^\]]*\])?\s*((?:[<>=!~][^"']*)?)["']""")


def ruff_specs(root: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """ruff-Angaben aus pyproject.toml — (exakte Pins, lose Angaben).

    `ruff>=0.4.0` im dev-Extra ist keine Kleinigkeit: `pip install -e ".[dev]"`
    holt damit die jeweils neueste Version, während CI und pre-commit auf einer
    festen stehen. Wer die Gates lokal fährt, prüft dann gegen ein anderes
    Regelwerk als das, an dem der PR scheitert — und sieht Abweichungen an
    Code, den niemand angefasst hat.
    """
    pins: list[tuple[str, str]] = []
    loose: list[tuple[str, str]] = []

    path = root / "pyproject.toml"
    if not path.exists():
        return pins, loose

    for m in _TOML_RUFF.finditer(strip_comments(path.read_text(encoding="utf-8"))):
        spec = m.group(1).strip()
        # Nur `==X` ist ein Pin. `>=`, `~=` und ein Bereich mit Komma lassen
        # der Auflösung Spielraum, und genau der ist hier das Problem.
        if spec.startswith("==") and "," not in spec:
            pins.append(("pyproject.toml → dev-Extra", spec[2:].strip()))
        else:
            loose.append(("pyproject.toml → dev-Extra", spec or "(ohne Version)"))

    return pins, loose


def ruff_pins(root: Path) -> list[tuple[str, str]]:
    """Alle exakten ruff-Pins — je (Bezeichnung, Version), ohne führendes `v`."""
    found: list[tuple[str, str]] = []

    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        for path in sorted(workflows.glob("*.y*ml")):
            text = strip_comments(path.read_text(encoding="utf-8"))
            for m in _RUFF_CI.finditer(text):
                rel = path.relative_to(root)
                found.append((f"{rel.as_posix()} → ruff==", m.group(1)))

    config = root / ".pre-commit-config.yaml"
    if config.exists():
        text = strip_comments(config.read_text(encoding="utf-8"))
        # `[1:]`: vor dem ersten `- repo:` steht nur der Dateikopf.
        for chunk in _PC_REPO.split(text)[1:]:
            head, _, rest = chunk.partition("\n")
            if "ruff-pre-commit" not in head:
                continue
            m = _PC_REV.search(rest)
            if m:
                found.append((".pre-commit-config.yaml → rev", m.group(1)))

    found.extend(ruff_specs(root)[0])
    return found


def read_project() -> dict:
    """`[project]`-Tabelle aus pyproject.toml.

    Ohne `tomllib` (Python 3.10) genügt hier ein Minimal-Parser: gebraucht
    werden nur `name` und `version`, beides einfache Strings direkt unter
    `[project]`. Eine Abhängigkeit auf `tomli` einzuführen, nur damit ein
    Check laufen kann, wäre unverhältnismässig.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(text)["project"]

    section = re.search(r"^\[project\]\s*$(.*?)(?=^\[)", text, re.MULTILINE | re.DOTALL)
    body = section.group(1) if section else text
    out = {}
    for key in ("name", "version"):
        m = re.search(rf'^{key}\s*=\s*"([^"]+)"', body, re.MULTILINE)
        if m:
            out[key] = m.group(1)
    return out


def main() -> None:
    project = read_project()
    dist = project["name"]
    version = project.get("version")

    if version is None:
        # `dynamic = ["version"]`: die Version entsteht beim Bauen, ein
        # Literal in src/ ist dort die Quelle und kein Fehler.
        print("Versions-Sync übersprungen: pyproject.toml nutzt eine dynamische Version.")
        return

    found = collect_declared(version)
    mismatches = [(where, value) for where, value in found if value != version]
    if mismatches:
        print(
            f"DRIFT: pyproject.toml steht auf {version!r}, folgende Stellen weichen ab:",
            file=sys.stderr,
        )
        for where, value in mismatches:
            print(f"  {where} = {value!r}", file=sys.stderr)
        print(
            "\nAlle Stellen im selben Commit bumpen. Hinweis: publish.yml "
            "überschreibt server.json beim Veröffentlichen ohnehin aus dem Tag — "
            "die committete Version bleibt trotzdem die, die Menschen lesen.",
            file=sys.stderr,
        )
        sys.exit(1)

    hardcoded = find_hardcoded(dist)
    if hardcoded:
        print("HARDCODED: Versionsnummer in src/ gefunden:", file=sys.stderr)
        for path, lineno, line in hardcoded:
            print(f"  {path}:{lineno}: {line}", file=sys.stderr)
        print(
            "\nDie Laufzeit-Version kommt aus den Paket-Metadaten "
            "(`__version__`, gespeist aus importlib.metadata). Statt eines "
            "Literals von dort lesen — sonst beginnt dieselbe Drift von vorn.",
            file=sys.stderr,
        )
        sys.exit(1)

    pins = ruff_pins(ROOT)
    loose = ruff_specs(ROOT)[1]
    problems = False

    if len({value for _, value in pins}) > 1:
        problems = True
        print("DRIFT: die ruff-Pins nennen verschiedene Versionen:", file=sys.stderr)
        for where, value in pins:
            print(f"  {where} = {value!r}", file=sys.stderr)
        print(
            "\nAlle Stellen im selben Commit bumpen. Solange sie abweichen, "
            "meldet lokal und in der CI je eine andere ruff-Version Abweichungen, "
            "die niemand verursacht hat.",
            file=sys.stderr,
        )

    if loose:
        problems = True
        print("\nLOSE: ruff ist nicht exakt gepinnt:", file=sys.stderr)
        for where, spec in loose:
            print(f"  {where} = {spec!r}", file=sys.stderr)
        print(
            "\nruff ist ein Gate, kein Hilfsmittel: `ruff==X.Y.Z` schreiben. Mit "
            'einem offenen Bereich holt `pip install -e ".[dev]"` die jeweils '
            "neueste Version, und lokal läuft ein anderes Gate als in der CI.",
            file=sys.stderr,
        )

    if problems:
        sys.exit(1)

    checked = ", ".join(where for where, _ in found) or "keine weiteren Stellen"
    if len(pins) > 1:
        ruff = f"; ruff-Pin einig auf {pins[0][1]} ({len(pins)} Stellen)"
    elif pins:
        # Ein einzelner Pin ist kein Fehler — aber auch kein Abgleich. Sichtbar
        # machen, sonst liest sich «OK» wie ein bestandener Vergleich.
        ruff = f"; ruff-Pin nur an einer Stelle ({pins[0][0]} {pins[0][1]})"
    else:
        ruff = ""
    print(
        f"Versions-Sync OK ({version}; geprüft: {checked}; "
        f"keine hartkodierte Version in src/{ruff})"
    )


if __name__ == "__main__":
    main()
