# Contributing

[🇩🇪 Deutsche Version](CONTRIBUTING.de.md)

Thank you for your interest in this project! Contributions are welcome.

## How can I contribute?

**Report bugs:** Create an [Issue](../../issues) with a clear description, reproduction steps, and expected vs. actual output.

**Suggest features:** Describe the use case, ideally with a reference to Swiss public transport context (school routes, field trips, accessibility, etc.).

**Contribute code:**

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Write tests for your changes
5. Run linter: `ruff check src/ tests/`
6. Commit with clear message: `git commit -m "feat: add accessibility data"`
7. Create a Pull Request

## Code Standards

- Python 3.11+, Ruff for linting
- Docstrings in English (for international compatibility)
- Comments and error messages may be in German or English
- All MCP tools must set `readOnlyHint: True` (read-only access)
- Pydantic models for all tool inputs

## API Keys

Integration tests require a free API key from [api-manager.opentransportdata.swiss](https://api-manager.opentransportdata.swiss/). **Never** commit API keys.

## License

MIT – see [LICENSE](LICENSE)

## The live suite: when it runs, and who sees a red result

**Cadence:** Monday 05:19 UTC, plus on demand via *Actions → Live-Tests → Run
workflow*. See [`.github/workflows/live-tests.yml`](.github/workflows/live-tests.yml).

**Who sees it:** a red run opens an issue titled `Live-Tests gegen opentransportdata.swiss rot …`
with the `upstream` label, and comments on the existing one instead of opening a
second. A run that goes green again closes it.

**Three answers, not two.** `scripts/classify_live_run.py` reads the JUnit XML
rather than the exit code and separates `clear` (ran, green), `finding` (ran,
something fell) and `unknown` (did not run — install failed, nothing collected,
everything skipped). An `unknown` never closes an issue: closing would claim a
comparison that never happened.

**Secret:** the live tests need `TRANSPORT_API_KEY`. Without it pytest skips all six and exits 0 — the run then reports `unknown` rather than green, because a secret nobody set is not a green contract with the source, it is no contract at all.

**A red live run does not necessarily mean *our* bug.** It means the contract
with the source has changed, or the source is down. Both belong seen; only the
first belongs fixed. Please read the run before disabling the job — that is how
this check dies, and it is the only one in the repository that can contradict a
wrong assumption about opentransportdata.swiss. Every other test asserts against a fixture, and
the fixture was written from the same assumption as the code.

Not hypothetical: on 2026-07-30 `meteoswiss-mcp`'s first live run in months put
three of six tests on the floor — the endpoint had been retired two days earlier
and nobody had started the suite.

The PR run stays at `-m "not live"`: a foreign 503 must not turn an unrelated
pull request red.
