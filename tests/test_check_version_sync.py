#!/usr/bin/env python3
"""Tests fuer den ruff-Pin-Abgleich in scripts/check_version_sync.py.

Der Pin steht an drei Stellen: dev-Extra in pyproject, `ruff==` im Workflow und
`rev:` beim ruff-pre-commit-Hook. Ein Check, der die vergleicht, hat vier Wege,
still falsch zu liegen, und jeder davon hat hier einen Test:

  - Er liest einen Kommentar als Fundort. Alle drei Dateien erklaeren ihren
    Pin im Fliesstext, teils woertlich mit «ruff==0.16.1».
  - Er ordnet ein `rev:` dem falschen `repo:` zu und vergleicht die Version
    eines fremden Hooks mit der von ruff.
  - Er haelt `[tool.ruff]` oder `ruff-lsp` fuer eine ruff-Abhaengigkeit.
  - Er meldet «OK», wo er gar nichts verglichen hat — weil nur eine der
    Stellen existiert.

Dazu `--expect`, der Abgleich zwischen Release-Tag und committeter Version.
Er sitzt im Publish-Pfad, laeuft also genau einmal pro Release und nie in der
gewoehnlichen CI — was ihn zum schlechtesten Ort fuer einen ungepruefen Fehler
macht. Zwei Richtungen, beide hier: Er muss bei Abweichung fallen, und er darf
ohne das Flag gar nichts tun.

Nur Standardbibliothek, kein Netz.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_version_sync as cvs  # noqa: E402

WORKFLOW = """\
name: test
jobs:
  lint:
    steps:
      - name: Install pinned ruff
        run: pip install ruff=={version}
"""

PRECOMMIT = """\
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v{version}
    hooks:
      - id: ruff-check
"""


PYPROJECT = """\
[project]
name = "demo"
version = "1.0.0"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff{spec}",
]

[tool.ruff]
line-length = 100
"""


def make_root(
    tmp: Path,
    workflow: str | None = None,
    precommit: str | None = None,
    pyproject: str | None = None,
) -> Path:
    if workflow is not None:
        wf = tmp / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "test.yml").write_text(workflow, encoding="utf-8")
    if precommit is not None:
        (tmp / ".pre-commit-config.yaml").write_text(precommit, encoding="utf-8")
    if pyproject is not None:
        (tmp / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return tmp


@contextlib.contextmanager
def root(
    workflow: str | None = None,
    precommit: str | None = None,
    pyproject: str | None = None,
):
    with tempfile.TemporaryDirectory() as tmp:
        yield make_root(Path(tmp), workflow, precommit, pyproject)


class RuffPinTest(unittest.TestCase):
    def versions(self, **kwargs) -> list[str]:
        with root(**kwargs) as path:
            return [value for _, value in cvs.ruff_pins(path)]

    def test_beide_stellen_gefunden(self):
        got = self.versions(
            workflow=WORKFLOW.format(version="0.16.1"),
            precommit=PRECOMMIT.format(version="0.16.1"),
        )
        self.assertEqual(got, ["0.16.1", "0.16.1"])

    def test_rev_verliert_das_v(self):
        """`rev: v0.16.1` und `ruff==0.16.1` bezeichnen dieselbe Version.

        Ohne das Abschneiden waeren sie als Zeichenketten ungleich, und der
        Check meldete Drift auf einem Repo, das korrekt gepinnt ist.
        """
        got = self.versions(precommit=PRECOMMIT.format(version="0.16.1"))
        self.assertEqual(got, ["0.16.1"])

    def test_abweichende_pins_bleiben_unterscheidbar(self):
        got = self.versions(
            workflow=WORKFLOW.format(version="0.16.1"),
            precommit=PRECOMMIT.format(version="0.15.8"),
        )
        self.assertEqual(sorted(got), ["0.15.8", "0.16.1"])

    def test_kommentar_im_workflow_ist_kein_fundort(self):
        got = self.versions(
            workflow="# historisch: ruff==0.9.9\n" + WORKFLOW.format(version="0.16.1"),
        )
        self.assertEqual(got, ["0.16.1"])

    def test_auskommentiertes_rev_gilt_nicht(self):
        """Ein stehengelassenes `# rev:` steht vor dem echten und darf nicht gewinnen.

        `_PC_REV` nimmt den ersten Treffer im Block. Dass die auskommentierte
        Zeile nicht zaehlt, leistet hier die Verankerung `^\\s*rev:` — zwischen
        Zeilenanfang und `rev:` darf nur Leerraum stehen, kein `#`. Nicht das
        Ausschneiden der Kommentare: Die Zusicherung haelt auch ohne das,
        gepruefte Wirkung ist die des Ankers.
        """
        text = PRECOMMIT.format(version="0.15.8").replace(
            "    rev: v0.15.8", "    # rev: v0.9.9  (vor dem Bump)\n    rev: v0.15.8"
        )
        got = self.versions(precommit=text)
        self.assertEqual(got, ["0.15.8"])

    def test_fremder_hook_liefert_kein_rev(self):
        """Ein `rev:` gehoert dem `repo:`, unter dem es steht."""
        text = (
            "repos:\n"
            "  - repo: https://github.com/pre-commit/pre-commit-hooks\n"
            "    rev: v9.9.9\n"
            "    hooks:\n"
            "      - id: end-of-file-fixer\n"
        ) + PRECOMMIT.format(version="0.16.1").replace("repos:\n", "")
        got = self.versions(precommit=text)
        self.assertEqual(got, ["0.16.1"])

    def test_ohne_pre_commit_datei_nur_ein_pin(self):
        got = self.versions(workflow=WORKFLOW.format(version="0.16.1"))
        self.assertEqual(got, ["0.16.1"])

    def test_ohne_beide_dateien_kein_pin(self):
        self.assertEqual(self.versions(), [])

    def test_raute_in_anfuehrungszeichen_schneidet_nicht_ab(self):
        """Die Raute steht in einer Zeichenkette, der Pin dahinter — auf derselben Zeile.

        Auf zwei Zeilen verteilt bewiese der Fall nichts: Ein zu frueh
        abgeschnittener Kommentar nimmt dann nur die erste Zeile mit, und der
        Pin waere auch ohne die Anfuehrungszeichen-Behandlung noch da.
        """
        text = 'run: echo "a # b" && pip install ruff==0.16.1\n'
        with root(workflow=text) as path:
            self.assertEqual([v for _, v in cvs.ruff_pins(path)], ["0.16.1"])


class PyprojectSpecTest(unittest.TestCase):
    """Das dev-Extra ist die Stelle, an der `pip install -e ".[dev]"` nachschaut."""

    def specs(self, spec: str) -> tuple[list[str], list[str]]:
        with root(pyproject=PYPROJECT.format(spec=spec)) as path:
            pins, loose = cvs.ruff_specs(path)
        return [v for _, v in pins], [v for _, v in loose]

    def test_exakter_pin_zaehlt_als_pin(self):
        self.assertEqual(self.specs("==0.16.1"), (["0.16.1"], []))

    def test_offener_bereich_ist_lose(self):
        self.assertEqual(self.specs(">=0.4.0"), ([], [">=0.4.0"]))

    def test_ohne_version_ist_lose(self):
        self.assertEqual(self.specs(""), ([], ["(ohne Version)"]))

    def test_bereich_mit_komma_ist_lose(self):
        """`==0.16.1,<0.17` faengt mit `==` an, laesst aber Spielraum.

        Ohne die Komma-Pruefung liefe so ein Bereich als exakter Pin durch —
        und `0.16.1,<0.17` waere die Version, gegen die verglichen wird.
        """
        self.assertEqual(self.specs("==0.16.1,<0.17"), ([], ["==0.16.1,<0.17"]))

    def test_tool_ruff_tabelle_ist_kein_treffer(self):
        """`[tool.ruff]` steht in jeder pyproject und ist keine Abhaengigkeit.

        Die pyproject hier nennt ruff *nur* als Konfigurationstabelle. Faende
        das Muster sie, meldete der Check eine lose ruff-Angabe an jedem Repo
        des Portfolios — und der Ausweg waere, den Check abzuschalten.
        """
        text = "[project]\nname = 'demo'\nversion = '1.0.0'\n\n[tool.ruff]\nline-length = 100\n"
        with root(pyproject=text) as path:
            self.assertEqual(cvs.ruff_specs(path), ([], []))

    def test_anderes_paket_mit_ruff_praefix(self):
        with root(
            pyproject=PYPROJECT.format(spec="==0.16.1").replace(
                '"pytest>=8.0.0"', '"ruff-lsp>=0.0.1"'
            )
        ) as path:
            pins, loose = cvs.ruff_specs(path)
        self.assertEqual(([v for _, v in pins], loose), (["0.16.1"], []))

    def test_kommentar_im_pyproject_ist_kein_fundort(self):
        """Der Pin-Kommentar dieses Repos nennt die Version in Anfuehrungszeichen.

        `bakom-mcp` schreibt sie sogar als `"ruff==0.16.1"` in den Fliesstext.
        Wird der mitgelesen, meldet der Check Einigkeit anhand von Prosa.
        """
        text = PYPROJECT.format(spec=">=0.4.0").replace(
            '    "pytest>=8.0.0",', '    # frueher: "ruff==0.16.1"\n    "pytest>=8.0.0",'
        )
        with root(pyproject=text) as path:
            pins, loose = cvs.ruff_specs(path)
        self.assertEqual((pins, [v for _, v in loose]), ([], [">=0.4.0"]))

    def test_pyproject_pin_zaehlt_beim_abgleich_mit(self):
        got = self.versions_all(
            workflow=WORKFLOW.format(version="0.16.1"),
            pyproject=PYPROJECT.format(spec="==0.15.8"),
        )
        self.assertEqual(sorted(got), ["0.15.8", "0.16.1"])

    def versions_all(self, **kwargs) -> list[str]:
        with root(**kwargs) as path:
            return [v for _, v in cvs.ruff_pins(path)]


class MainTest(unittest.TestCase):
    """main() als Ganzes — der Abgleich entscheidet ueber den Exit-Code."""

    def run_main(self, tmp: Path, argv: list[str] | None = None) -> tuple[int, str]:
        # Nicht ueberschreiben: Faelle, die eine eigene pyproject mitbringen,
        # pruefen genau deren Inhalt.
        path = tmp / "pyproject.toml"
        if not path.exists():
            path.write_text('[project]\nname = "demo"\nversion = "1.0.0"\n', encoding="utf-8")
        old = (cvs.ROOT, cvs.PYPROJECT, cvs.SERVER_JSON, cvs.SRC, cvs.CHANGELOG)
        cvs.ROOT, cvs.PYPROJECT = tmp, tmp / "pyproject.toml"
        cvs.SERVER_JSON, cvs.SRC = tmp / "server.json", tmp / "src"
        # Ohne das liest der Check den CHANGELOG des echten Repos, und jeder
        # Fall haengt daran, was dort gerade offen steht.
        cvs.CHANGELOG = tmp / "CHANGELOG.md"
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                cvs.main(argv or [])
            code = 0
        except SystemExit as exc:
            code = exc.code
        finally:
            cvs.ROOT, cvs.PYPROJECT, cvs.SERVER_JSON, cvs.SRC, cvs.CHANGELOG = old
        return code, out.getvalue() + err.getvalue()

    def test_abweichende_pins_sind_rot(self):
        with root(
            workflow=WORKFLOW.format(version="0.16.1"),
            precommit=PRECOMMIT.format(version="0.15.8"),
        ) as path:
            code, text = self.run_main(path)
        self.assertEqual(code, 1)
        self.assertIn("DRIFT", text)
        self.assertIn("0.15.8", text)

    def test_gleiche_pins_sind_gruen(self):
        with root(
            workflow=WORKFLOW.format(version="0.16.1"),
            precommit=PRECOMMIT.format(version="0.16.1"),
        ) as path:
            code, text = self.run_main(path)
        self.assertEqual(code, 0)
        self.assertIn("0.16.1", text)

    def test_loser_spec_ist_rot(self):
        with root(
            workflow=WORKFLOW.format(version="0.16.1"),
            pyproject=PYPROJECT.format(spec=">=0.4.0"),
        ) as path:
            code, text = self.run_main(path)
        self.assertEqual(code, 1)
        self.assertIn("LOSE", text)

    def test_exakter_pin_im_pyproject_ist_gruen(self):
        with root(
            workflow=WORKFLOW.format(version="0.16.1"),
            pyproject=PYPROJECT.format(spec="==0.16.1"),
        ) as path:
            code, text = self.run_main(path)
        self.assertEqual(code, 0)
        self.assertIn("2 Stellen", text)

    def test_einzelner_pin_wird_nicht_als_vergleich_ausgegeben(self):
        """Gruen, aber sichtbar ohne Gegenstueck.

        Ein blosses «OK» laese sich hier als bestandener Abgleich lesen, und
        genau der hat nicht stattgefunden.
        """
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            code, text = self.run_main(path)
        self.assertEqual(code, 0)
        self.assertIn("nur an einer Stelle", text)


class ExpectTest(unittest.TestCase):
    """`--expect <Tag>`: der Abgleich, der den Publish-Pfad absichert.

    Gebaut wird aus `pyproject.toml`, getaggt wird daneben. Fallen die beiden
    auseinander, baut der Release-Workflow die alte Nummer — und merkt es erst
    an PyPIs Duplikat-Absage, wenn ueberhaupt.
    """

    run_main = MainTest.run_main

    def test_passender_tag_ist_gruen(self):
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            (path / "pyproject.toml").write_text(
                '[project]\nname = "demo"\nversion = "0.5.0"\n', encoding="utf-8"
            )
            code, text = self.run_main(path, ["--expect", "0.5.0"])
        self.assertEqual(code, 0, text)

    def test_abweichender_tag_ist_rot(self):
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            (path / "pyproject.toml").write_text(
                '[project]\nname = "demo"\nversion = "0.4.0"\n', encoding="utf-8"
            )
            code, text = self.run_main(path, ["--expect", "0.5.0"])
        self.assertEqual(code, 1)
        self.assertIn("TAG-DRIFT", text)
        # Beide Nummern muessen in der Absage stehen: «passt nicht» allein
        # laesst offen, welche der beiden Stellen nachzuziehen ist.
        self.assertIn("0.5.0", text)
        self.assertIn("0.4.0", text)

    def test_das_fuehrende_v_des_tags_wird_abgeschnitten(self):
        """Die Tags dieses Repos heissen `v0.5.0`, `pyproject.toml` nie.

        Ohne das Abschneiden waere jeder Release rot — und zwar mit der
        Meldung, die Versionen wichen ab, obwohl sie es nicht tun.
        """
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            (path / "pyproject.toml").write_text(
                '[project]\nname = "demo"\nversion = "0.5.0"\n', encoding="utf-8"
            )
            code, text = self.run_main(path, ["--expect", "v0.5.0"])
        self.assertEqual(code, 0, text)

    def test_ohne_das_flag_vergleicht_er_nichts(self):
        """Die Gegenprobe zur Richtung: Der Abgleich ist opt-in.

        Ohne diese Zeile koennte `--expect` auch dann greifen, wenn niemand es
        uebergibt — und die gewoehnliche CI, die den Check ohne Argument fährt,
        wuerde an einer Tag-Nummer scheitern, die es dort gar nicht gibt.
        """
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            (path / "pyproject.toml").write_text(
                '[project]\nname = "demo"\nversion = "0.4.0"\n', encoding="utf-8"
            )
            code, text = self.run_main(path)
        self.assertEqual(code, 0, text)
        self.assertNotIn("TAG-DRIFT", text)

    def test_dynamische_version_kann_die_zusicherung_nicht_geben(self):
        """Ein «OK» waere hier die Behauptung einer Pruefung, die nicht lief.

        Ohne `version` in `pyproject.toml` gibt es keine committete Nummer zum
        Vergleichen. Der Check ueberspringt sich sonst still gruen — und genau
        dieses Gruen wuerde im Publish-Pfad als bestandener Abgleich gelesen.
        """
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            (path / "pyproject.toml").write_text(
                '[project]\nname = "demo"\ndynamic = ["version"]\n', encoding="utf-8"
            )
            code, text = self.run_main(path, ["--expect", "0.5.0"])
        self.assertEqual(code, 1)
        self.assertIn("NICHT PRUEFBAR", text)


class ChangelogGateTest(unittest.TestCase):
    """`--expect` prueft auch den CHANGELOG — die zweite Haelfte des Gates.

    Zweimal im Portfolio passiert, beide Male gemessen: Ein PR mergt, nachdem
    der Versionsabschnitt geschlossen wurde, aber vor dem Tag. Das Release
    traegt den Eintrag dann als «unveroeffentlicht», obwohl er darin steckt —
    `v0.4.0` mit dem SEC-005-Eintrag, `v0.5.0` mit dem Publish-Pfad-Eintrag.
    Eine Zeile in CONTRIBUTING haette keinen der beiden Faelle verhindert;
    beide entstanden, obwohl die Regel bekannt war.
    """

    run_main = MainTest.run_main

    def tree(self, path: Path, version: str, changelog: str | None) -> None:
        (path / "pyproject.toml").write_text(
            f'[project]\nname = "demo"\nversion = "{version}"\n', encoding="utf-8"
        )
        if changelog is not None:
            (path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")

    def test_geschlossener_abschnitt_und_leeres_unreleased_sind_gruen(self):
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            self.tree(path, "0.5.0", "# Changelog\n\n## [0.5.0] - 2026-09-26\n\n- etwas\n")
            code, text = self.run_main(path, ["--expect", "v0.5.0"])
        self.assertEqual(code, 0, text)

    def test_offener_unreleased_eintrag_ist_rot(self):
        """Der gemessene Fall, in der Form, in der er zweimal auftrat."""
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            self.tree(
                path,
                "0.5.0",
                "# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n"
                "- **Der Publish-Pfad konnte still die falsche Version bauen.**\n\n"
                "## [0.5.0] - 2026-09-26\n\n- etwas\n",
            )
            code, text = self.run_main(path, ["--expect", "v0.5.0"])
        self.assertEqual(code, 1)
        self.assertIn("Unreleased", text)
        # Die offene Zeile muss in der Absage stehen: «nicht leer» allein
        # laesst offen, welcher Eintrag einzusortieren ist.
        self.assertIn("Publish-Pfad", text)

    def test_eine_leere_unreleased_ueberschrift_allein_ist_kein_befund(self):
        """Die Gegenprobe: gemeldet wird Inhalt, nicht die Ueberschrift.

        Ohne diese Zeile koennte das Gate auf `## [Unreleased]` selbst
        anspringen — und jeder Release scheiterte an einem Abschnitt, der
        konventionsgemaess leer dastehen darf. Die Rubrik `### Fixed` zaehlt
        aus demselben Grund nicht als Inhalt.
        """
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            self.tree(
                path,
                "0.5.0",
                "# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n"
                "## [0.5.0] - 2026-09-26\n\n- etwas\n",
            )
            code, text = self.run_main(path, ["--expect", "v0.5.0"])
        self.assertEqual(code, 0, text)

    def test_fehlender_versionsabschnitt_ist_rot(self):
        """Ein Release ohne Eintrag ist die andere Haelfte desselben Fehlers."""
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            self.tree(path, "0.5.0", "# Changelog\n\n## [0.4.0] - 2026-07-30\n\n- alt\n")
            code, text = self.run_main(path, ["--expect", "v0.5.0"])
        self.assertEqual(code, 1)
        self.assertIn("0.5.0", text)

    def test_ohne_changelog_datei_kein_befund(self):
        """Ein Repo ohne CHANGELOG ist kein Fehler, nur eines mit einem
        widerspruechlichen."""
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            self.tree(path, "0.5.0", None)
            code, text = self.run_main(path, ["--expect", "v0.5.0"])
        self.assertEqual(code, 0, text)

    def test_ohne_das_flag_bleibt_der_changelog_ungeprueft(self):
        """Die gewoehnliche CI laeuft ohne `--expect` und darf an einem
        offenen `[Unreleased]` nicht scheitern — dort ist er der Normalfall."""
        with root(workflow=WORKFLOW.format(version="0.16.1")) as path:
            self.tree(
                path,
                "0.5.0",
                "# Changelog\n\n## [Unreleased]\n\n- etwas Offenes\n",
            )
            code, text = self.run_main(path)
        self.assertEqual(code, 0, text)


if __name__ == "__main__":
    unittest.main()
