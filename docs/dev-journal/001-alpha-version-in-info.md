---
id: 001
title: Report an alpha SemVer version in info
commit: "feat: report alpha version 0.1.0-alpha in info"
step: 8 — versioning
date: 2026-10-19
tags: [python, versioning, semver, regex, unittest, single-source-of-truth]
---

# Report an alpha SemVer version in info

## What we did

`info` already returned `SERVER_VERSION` from `config.py`, but its value was `1.0.0`. That
promises a stable API, which isn't true while the protocol is still evolving. We moved it to
`0.1.0-alpha` (`config.py:8`). Under Semantic Versioning, `0.x` means initial development,
`.1` means the first feature set, and `-alpha` marks an unstable pre-release. The server code
didn't change: `cmd_info` reads the constant, so `info` now replies
`{"version": "0.1.0-alpha", "created": "2026-10-01"}`.

We also added `test_version_is_semver` (`tests/test_server.py:53`). It checks the constant
against the official SemVer 2.0.0 regex (`tests/test_server.py:14`), so a malformed version
such as `0.1-alpha` or `01.0.0` fails the test suite instead of reaching clients. `PLAN.md`
gets a new Step 8 with the bumping rules, and Step 4's `info` example now shows the new value.

## How it fits

- **Plan:** delivers Step 8 (versioning). It gives later work a rule to follow: when
  `feature/admin` lands with new commands, that's a `MINOR` bump (`0.2.0-alpha`).
- **Practice:**
  - *Single source of truth.* One constant holds the version, and both the server and the
    tests import it, so they can't disagree.
  - *A version is a contract.* `MAJOR`/`MINOR`/`PATCH` tells a client whether upgrading is
    safe.
  - *Test the invariant, not the value.* `test_info` checks that `info` echoes the constant,
    and the new test checks the constant's *format*. Neither needs editing when the version
    is bumped.
  - *When not to do it this way:* in a published package, the version would sit in
    `pyproject.toml` (PEP 440 spelling, `0.1.0a0`) or be derived from git tags. Hard-coding
    it is fine here because nothing is packaged.

## Commands used

- `git branch --show-current`: confirm the change is going onto `master`.
- `sed -i 's/.../.../' config.py`, `sed -i '...' PLAN.md`: replace the version string in place.
- `git diff --stat`: check that only the intended files changed.
- `python - <<'EOF' ... EOF`: run a short Python script from a heredoc to insert the test
  and Step 8.
- `git diff tests PLAN.md | head -70`: review the inserted lines.
- `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR)"`: run the
  suite and show only the summary (7 tests, OK).
- `grep -n "Official" tests/test_server.py`: check the shortened comment.
- `python -c "..."`: sanity-check that the regex accepts `0.1.0-alpha` and `0.1.0-alpha.2`
  and rejects `0.1-alpha`, `01.0.0` and `1.0.0-`.
- `cat docs/concepts/README.md docs/dev-journal/README.md`: read the index format.
- `git add ...`, `git commit -m ... -m ...`: commit (see [git add](../commands.md#git-add-stage-changes-for-the-next-commit)).

## Read more

- [Semantic Versioning 2.0.0](https://semver.org/): semver.org (official spec) · rules for
  `0.y.z`, pre-release precedence (`1.0.0-alpha < 1.0.0`) and the FAQ regex our test uses.
- [A quick intro to Semantic Versioning](https://www.freecodecamp.org/news/semantic-versioning-1fd6f57749f7/):
  freeCodeCamp · what each of the three numbers tells a user.
- [PEP 440 – Version Identification and Dependency Specification](https://peps.python.org/pep-0440/):
  peps.python.org · Python packaging's spelling of pre-releases (`a`, `b`, `rc`).
- [Regular expression HOWTO](https://docs.python.org/3/howto/regex.html): docs.python.org ·
  why regexes go in raw strings (`r"..."`), "the backslash plague".
- [unittest — assertRegex](https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertRegex):
  docs.python.org · `assertRegex` uses `re.search`, so the anchors `^`/`$` in the pattern matter.
- [Concept 001: Semantic Versioning](../concepts/001-semantic-versioning.md): the concept note
  for this chunk.

## Quiz

### Revise

1. What does each part of `0.1.0-alpha` mean?
   <details><summary>Answer</summary>

   `0` = major version zero, initial development with no stability promise. `1` = minor,
   the first feature set. `0` = patch, no bug-fix releases yet. `-alpha` = a pre-release
   identifier marking the build as unstable.
   </details>

2. Which is greater: `1.0.0-alpha` or `1.0.0`? a) `1.0.0-alpha` b) `1.0.0` c) they are equal
   d) it depends on the build date
   <details><summary>Answer</summary>

   b) A pre-release has lower precedence than the associated normal release.
   </details>

3. You add a new `time` command and old clients keep working. Starting from `0.1.0`, what's
   the next version?
   <details><summary>Answer</summary>

   `0.2.0`. A backward-compatible feature bumps `MINOR` and resets `PATCH` to 0.
   </details>

4. Why is the regex written as `r"^(0|[1-9]\d*)..."` and not `"^(0|[1-9]\d*)..."`?
   <details><summary>Answer</summary>

   In a normal string literal, `\d` is an invalid escape. Python leaves it as is but emits a
   `SyntaxWarning`, which will become an error. A raw string passes backslashes to `re`
   untouched.
   </details>

5. Spot the bug: `self.assertRegex(SERVER_VERSION, r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")`
   <details><summary>Answer</summary>

   It has no `^` and `$` anchors, and `assertRegex` uses `re.search`, so the pattern can
   match anywhere in the string. `"v01.0.0-??"` would pass because `1.0.0` appears inside it.
   </details>

### Defend the decision

1. Why did you change the version from `1.0.0` to `0.1.0-alpha`? Isn't that going backwards?
   <details><summary>Model answer</summary>

   `1.0.0` tells clients the protocol is stable and breaking changes will bump `MAJOR`. That
   promise was false: `feature/admin` changes the transport (TLS) and adds authentication.
   `0.x` honestly says anything may change, and `-alpha` adds that it's an unstable
   pre-release. Nothing had been released to anyone, so resetting cost nothing. After a real
   release, you would never move the version backwards.
   </details>

2. Why keep the version as a constant in `config.py` and not derive it from git tags or
   `pyproject.toml`?
   <details><summary>Model answer</summary>

   The app is a stdlib-only script that isn't packaged or installed, so there's no build step
   to inject a version. One constant imported by the server and the tests is the simplest
   single source of truth. Its downside is that it's easy to forget to bump, and the format
   test only partly covers that. For a published package, I'd move it to `pyproject.toml` in
   PEP 440 form or derive it from tags, so releases and versions can't drift apart.
   </details>

3. Why test the version's *format* with a regex instead of asserting `== "0.1.0-alpha"`?
   <details><summary>Model answer</summary>

   An equality check would just repeat the constant and need editing on every bump, without
   catching anything useful. The real requirement is "the server always reports a valid
   SemVer string", so the test checks that rule and stays valid across releases. We used
   the official regex instead of writing our own, so edge cases such as leading zeros
   (`01.0.0`) and empty pre-release identifiers (`1.0.0-`) are handled the way the spec
   defines them. `test_info` separately covers that `info` returns the constant.
   </details>
