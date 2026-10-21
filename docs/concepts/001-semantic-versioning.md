---
id: 001
title: Semantic Versioning (SemVer) and pre-release versions
date: 2026-10-19
asked-during: "feat: report alpha version 0.1.0-alpha in info"
tags: [versioning, semver, pre-release, release-management]
---

# Semantic Versioning (SemVer) and pre-release versions

## What it is

Semantic Versioning 2.0.0 gives a version number the form `MAJOR.MINOR.PATCH`, and each part
tells the user of your software something different:

| Part    | Bump it when…                                                  | Example           |
|---------|----------------------------------------------------------------|-------------------|
| `MAJOR` | a change breaks existing clients (e.g. a new JSON reply shape) | `1.4.2` → `2.0.0` |
| `MINOR` | you add a feature and old clients keep working (a new command) | `1.4.2` → `1.5.0` |
| `PATCH` | you fix a bug and the outside behaviour stays the same         | `1.4.2` → `1.4.3` |

Bumping a part resets the parts to its right to zero.

Two more rules matter for a young project:

- **`0.y.z` is initial development.** While `MAJOR` is `0`, "anything MAY change at any time".
  The public API isn't considered stable, so nobody should rely on it yet. You release
  `1.0.0` when you're ready to promise stability.
- **Pre-release versions** add a hyphen and identifiers after the patch number:
  `0.1.0-alpha`, `0.1.0-alpha.2`, `0.1.0-beta`, `0.1.0-rc.1`. A pre-release ranks *lower*
  than the normal release it leads to: `1.0.0-alpha < 1.0.0`. Build metadata can follow
  a `+` (`1.0.0+20261019`) and is ignored when comparing versions.

Common stages: **alpha** means features are incomplete and things will break. **Beta**
means features are complete but bugs are expected. **rc** (release candidate) means it ships
as-is unless a serious bug turns up.

## Where it shows up in zr-client-server

- `config.py:8`: `SERVER_VERSION = "0.1.0-alpha"`, the single source of truth.
- `server.py`: `cmd_info` returns it, so `info` replies
  `{"version": "0.1.0-alpha", "created": "2026-10-01"}`.
- `tests/test_server.py`: `test_version_is_semver` checks the string against the official
  SemVer regex.
- `PLAN.md`, Step 14: the bumping rules for this project.

The version had been `1.0.0`. That claimed a stable API for a protocol that's still changing
(`feature/admin` adds commands and TLS), so it was moved back to `0.1.0-alpha`.

## Alternatives and trade-offs

- **PEP 440** is Python's packaging version scheme, used by pip and PyPI. It spells
  pre-releases as `0.1.0a1`, `0.1.0b2` and `0.1.0rc1`, and normalises `0.1.0-alpha` to
  `0.1.0a0`. If this project ever became an installable package, the version in
  `pyproject.toml` would follow PEP 440.
- **CalVer** (calendar versioning, e.g. `2026.10`) suits products released on a schedule,
  where "how new is it" matters more than "will it break me" (Ubuntu, pip itself).
- **Version from git tags** (`git describe` → `v0.1.0-alpha-3-gabc123`): with this, the
  version can never drift from the history. It needs build tooling to inject the version,
  which is overkill for a two-file stdlib app.

## Interview answer

"I use Semantic Versioning: `MAJOR.MINOR.PATCH`. The number is a contract with clients. A
`MAJOR` bump warns them that something breaks, `MINOR` adds features safely and `PATCH`
only fixes bugs. A project that's still being shaped stays on `0.x`, and a pre-release tag
such as `-alpha` marks a build as unstable. That's why our server reports `0.1.0-alpha`.
The version lives in one constant in `config.py`, and a test checks that it's valid SemVer."

## Read more

- [Semantic Versioning 2.0.0](https://semver.org/): semver.org (official spec) · rules 4
  (`0.y.z`), 9 (pre-release) and 11 (precedence), plus the FAQ regex used in our test.
- [A quick intro to Semantic Versioning](https://www.freecodecamp.org/news/semantic-versioning-1fd6f57749f7/):
  freeCodeCamp · a beginner-friendly explanation of major/minor/patch and why it helps users.
- [PEP 440 – Version Identification and Dependency Specification](https://peps.python.org/pep-0440/):
  peps.python.org · how Python packaging spells alpha/beta/rc and how it normalises SemVer-style input.
