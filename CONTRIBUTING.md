# Contributing

Work happens in loops, as described in [LOOP.md](LOOP.md): one mission, built, checked,
documented and reported. Read [VISION.md](VISION.md) first; it changes only with the owner.
[HOW-IT-WORKS.md](HOW-IT-WORKS.md) shows how the checks, the GitHub workflows and the release
path fit together, and who does what.

## Setup

```sh
uv sync
uv run pre-commit install
```

## Before you commit

The pre-commit hooks run the formatter, the linter, the type checker and a secret scan on staged
files. The same checks, plus the tests, run on GitHub at every push and pull request
([CI](.github/workflows/ci.yml)), next to a security analysis
([CodeQL](.github/workflows/codeql.yml)):

```sh
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run pytest -m e2e
```

New code has zero warnings and comes with tests. A change to a calculation needs a test that
checks it against arithmetic done by hand from the filing.

## Rules that are specific to this project

- **No number in a template.** Templates call `n("id")`. A figure is a fact in `data/facts/` or a
  calculation in `calc.py`, with its source.
- **No figure typed by hand** into the FILED dataset. Change `extract.py` and re-run it.
- **No price typed by hand.** Market values come from `market.py`, built from what the quote
  service answered. Tests replay recorded answers; the one file with invented prices says so.
- **No secret, contact address or internal access detail** in the repository, the devlog or the
  page. The repository is public.
- **English** for everything a reader of the site or of the repository sees.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`, with the
types `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `build`, `perf`, `style`.

```
feat(value): show the share count behind each valuation
fix(extract): keep page headers out of quotes
```

Versions follow [SemVer](https://semver.org/); every release has an entry in
[CHANGELOG.md](CHANGELOG.md).

## Branches and review

`main` is always releasable. Work on a short branch, open a pull request, and merge when the
checks pass and someone has reviewed it. During a loop run by the owner with a coding agent,
small commits may go straight to `main`; the loop's report is then the review record.

### Recommended branch protection for `main`

Set by the repository owner in GitHub settings (this project never changes them itself):

- Require a pull request before merging, with at least one approval.
- Require status checks to pass: `Format, lint, types, tests`, `Secret scan`, and the CodeQL jobs.
- Require branches to be up to date before merging.
- Block force pushes and deletions.
- Enable secret scanning with push protection, and Dependabot alerts.
