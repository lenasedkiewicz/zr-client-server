---
id: 014
title: Make the SemVer check strict (ASCII digits, whole string)
commit: "test: make the SemVer check strict (ASCII digits, whole string)"
step: 16 — address the 2026-10-21 mentoring code review (batch 2, task 2.3)
date: 2026-11-03
tags: [python, regex, re, unicode, semver, unittest, subtest, negative-tests]
---

# Make the SemVer check strict (ASCII digits, whole string)

## What we did

`VersionTest` checked `SERVER_VERSION` against the official SemVer 2.0.0 regex copied from
semver.org. The regex is correct, but Python's `re` reads it in two ways the spec's authors
didn't intend:

- **`\d` matches any Unicode decimal digit** in a `str` pattern (category `Nd`), not just
  `0-9`. So `1٢.0.0` (with ARABIC-INDIC DIGIT TWO) passed. `int("٢")` even returns `2`, so
  nothing downstream would have complained either.
- **`$` matches at the end *or just before a final `\n`***, so `"0.1.0-alpha\n"` passed.
  `assertRegex` uses `search`, which doesn't help.

The fix is in `tests/test_server.py:30-45`. The regex text stays verbatim, so you can still
compare it with the spec. It gets the `re.ASCII` flag (`\d` → `[0-9]`). A new helper,
`is_semver(version)`, uses `SEMVER.fullmatch`, so the whole string must match and a trailing
newline is rejected. A comment above the regex explains both traps.

The tests (`tests/test_server.py:47`) now go through `is_semver`. One table of valid versions
(`0.1.0`, `0.1.0-alpha`, `1.0.0-rc.1`, `1.2.3+build.7`, `10.20.30`) proves the regex isn't
*too* strict. One table of invalid ones (Arabic-Indic digit, trailing newline, leading `v`,
leading zero, missing patch) uses `subTest`, so each failing case is reported by name.

**Test first, and a mistake worth remembering.** The first draft of the tests **passed
against the old regex**, so it proved nothing. There were two reasons:
1. The tests called `SEMVER.fullmatch` themselves. That fixed the newline bug *in the test*,
   not in the check.
2. The Arabic-Indic case was `٠.١.٠`. A zero component must be the literal ASCII `0`, and
   `١` alone must match `[1-9]`. Neither goes through `\d`. Only digits *after* the first one
   (`[1-9]\d*`) reach `\d`, hence `1٢.0.0`.

After routing the tests through a helper that still used `search`, both cases failed. The fix
made them pass. A negative test only counts once you've seen it fail.

## Answers before coding (from the plan)

1. **What do `\d` and `$` match in a `str` pattern by default?** `\d` matches any Unicode
   decimal digit (`[0-9]` plus Arabic-Indic, Devanagari, full-width and other digits). `$`
   matches at the end of the string *and* just before a newline at the end. Checked with
   `python -c`: `re.match(r'^\d$', '١')` → match, and `re.match(r'^1$', '1\n')` → match.
2. **What changes with `re.ASCII` and `re.fullmatch`?** `re.ASCII` (inline `(?a)`) makes `\d`,
   `\w`, `\s` and `\b` ASCII-only, so `\d` becomes `[0-9]`. `fullmatch` succeeds only if the
   pattern consumes the *whole* string, so the `\n` would have to be matched by the pattern,
   and it can't be. `\Z` (Python's "really the end") at the end of the pattern would do the
   same job.
3. **`re.ASCII` or `[0-9]` instead of `\d`?** We chose the flag. It keeps the regex
   byte-for-byte identical to semver.org, so a reviewer can diff it against the spec, and it
   covers every `\d` in one place. Rewriting it as `[0-9]` is just as correct and doesn't
   depend on a flag. That's better if the pattern gets copied into another language or a
   config file where the flag would be lost.
4. **Why does this bite in Python but not in JavaScript?** semver.org says the regex works in
   ECMAScript, PCRE, Python and Go. In JavaScript, `\d` is always `[0-9]` and `$` (without `m`)
   matches only at the very end. "Compatible" means the syntax parses, not that it means the
   same thing.

## How it fits

- **Plan:** Step 16, task 2.3 of [`docs/plans/001-code-review-2026-10-21.md`](../plans/001-code-review-2026-10-21.md).
  This finishes **batch 2 (test foundations)**. Next: open the PR for `test/test-foundations`.
  After the merge, batch 3 (logging instead of `print`) starts from the new `master`.
- **Practice:**
  - **Negative tests.** A validator is proven by what it rejects as much as by what it
    accepts. Pair each "must reject" case with "must still accept" cases, so a fix can't
    quietly turn into "reject everything".
  - **See the test fail first.** A test written after reading the fix can repeat the fix
    inside itself (here, `fullmatch` in the test) and pass for the wrong reason.
  - **A copied regex has a flavour.** The same text can mean different things in Python,
    JavaScript and PCRE. Unicode-aware classes and the trailing-newline `$` are the classic
    differences. For validation at a trust boundary, prefer whole-string matching
    (`fullmatch` or `\Z`) and explicit character sets.
  - **When you'd do less:** a version string you write yourself, checked only by your own
    test, is low risk. The same regex validating *input* (a client-sent version, a header, a
    username) is where `\d` and `$` turn into real bugs. `users.py:60` already does it
    right: `re.fullmatch` with `USERNAME_PATTERN = r"[A-Za-z0-9_]{3,32}"` (`config.py:16`),
    explicit ASCII classes and whole-string matching.

## Commands used

- `cat PLAN.md`, `ls docs docs/dev-journal docs/concepts`, `git log --oneline -12`, `git branch -a`: find the next task
- `sed -n '/^## How to work/,/^## Batch 4/p' <file>`: print the plan from one heading to another (sed with pattern ranges, like [awk](../commands.md#awk-print-lines-between-two-patterns))
- `grep -rn -i "semver" tests/`, `git status --short`: find the regex and check the tree
- `python -c "import re; print(bool(re.match(r'^\d$', '١')), …)"`: confirm the two traps. The first try printed the digit itself and hit the console's `cp1250` encoding (see [python -c](../commands.md#python--c-run-a-one-line-program))
- `python -m unittest tests.test_server.VersionTest`: run only the version tests (see them fail, then pass)
- `python - <<'PYEOF' … PYEOF`: scripted edits to the test file. They turned `\\u0662` into the real character, see the [python -](../commands.md#python---run-a-script-from-stdin) gotcha
- `sed -n 59p tests/test_server.py | od -c`: show the exact characters of one line ([od -c](../commands.md#od--c-show-the-exact-characters-in-a-file), new)
- `git show HEAD:tests/test_server.py | file -`, `file tests/test_server.py`: check that the file is ASCII again, like before ([file -](../commands.md#file-show-a-files-type-and-line-endings), new flag)
- `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`: full suite, 63 tests OK (1 skipped on Windows)
- `git diff --stat`: check that only the intended lines changed

## Read more

- [re: `\d`, `$`, `re.ASCII`, `re.fullmatch`](https://docs.python.org/3/library/re.html#re.ASCII): Python docs · the exact rules: `\d` is Unicode `Nd` unless `ASCII` is set, and `$` matches "just before the newline at the end of the string"
- [Regular expression HOWTO](https://docs.python.org/3/howto/regex.html): Python docs · gentler intro to flags, and `match` vs `search` (`fullmatch` is in the library page)
- [Input boundary assertion: ^, $](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Input_boundary_assertion): MDN · the JavaScript meaning of `$`, which is what the semver.org regex silently assumes
- [Start and end of string anchors](https://www.regular-expressions.info/anchors.html): regular-expressions.info · how `$`, `\Z` and `\z` differ between flavours ("in Python, `\Z` matches only at the very end")
- [Semantic Versioning 2.0.0, FAQ "Is there a suggested regular expression…"](https://semver.org/) ([PL](https://semver.org/lang/pl/)) · the source of the regex and the flavours it claims to support
- [unittest: distinguishing test iterations using subtests](https://docs.python.org/3/library/unittest.html#distinguishing-test-iterations-using-subtests): Python docs · why one failing case doesn't hide the others
- Related: [concept 001, Semantic Versioning](../concepts/001-semantic-versioning.md)

## Quiz

### Revise

1. In a Python `str` pattern without flags, which of these does `re.fullmatch(r"\d+", s)` accept?
   a) `"42"` b) `"٤٢"` (Arabic-Indic) c) `"42\n"` d) `"４２"` (full-width)
   <details><summary>Answer</summary>

   a, b and d. `\d` matches every Unicode decimal digit, and Arabic-Indic and full-width digits
   are category `Nd`. c fails because `fullmatch` needs the whole string, including the `\n`, to
   be matched.
   </details>

2. `re.search(r"^1\.0\.0$", "1.0.0\n")`: match or `None`? And with `\Z` instead of `$`?
   <details><summary>Answer</summary>

   With `$` it matches, because `$` also matches just before a final newline. With `\Z` it's
   `None`, because in Python `\Z` matches only at the very end of the string.
   </details>

3. What does `re.ASCII` change, and what is its inline form?
   <details><summary>Answer</summary>

   It makes `\d`, `\w`, `\s`, `\b` (and their negations) match only ASCII characters, for
   example `\d` = `[0-9]`. The inline form is `(?a)` at the start of the pattern. It does
   nothing for `bytes` patterns, which are ASCII already.
   </details>

4. Spot the bug: this test passes, but the check in production is still broken. Why?
   ```python
   PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
   def is_version(s): return PATTERN.search(s) is not None
   def test_rejects_newline(self):
       self.assertIsNone(PATTERN.fullmatch("1.0.0\n"))
   ```
   <details><summary>Answer</summary>

   The test calls `fullmatch` itself instead of going through `is_version`, which uses `search`.
   The test repeats the fix instead of testing the real code path. `is_version("1.0.0\n")` still
   returns `True`. Always test through the function production code calls, and watch the test
   fail first.
   </details>

5. Why did the first draft's `٠.١.٠` case pass against the old, buggy regex?
   <details><summary>Answer</summary>

   Each component is `0|[1-9]\d*`. `٠` isn't the literal ASCII `0`, and `١` isn't in `[1-9]`, so
   the regex rejected it before `\d` ever ran. Only digits after the first one go through `\d`,
   so the case has to look like `1٢.0.0`.
   </details>

6. What does `subTest` give you over a plain `for` loop of assertions?
   <details><summary>Answer</summary>

   With a plain loop, the first failing assertion stops the test, and the report doesn't say
   which value failed. With `subTest(reason)`, each failing case is reported with its label,
   and the loop continues, so you see every failure in one run.
   </details>

### Defend the decision

1. "The regex is the official one from semver.org. Why wasn't it already correct?"
   <details><summary>Model answer</summary>

   semver.org lists it as compatible with ECMAScript, PCRE, Python and Go, but "compatible"
   only means it parses. In JavaScript, `\d` is ASCII and `$` is the true end of input. In
   Python, a `str` pattern makes `\d` Unicode-aware and `$` tolerant of a trailing newline. So
   the same text accepted `1٢.0.0` and `"0.1.0-alpha\n"`. We kept the text verbatim, so it can
   be checked against the spec, and fixed the meaning with `re.ASCII` plus `fullmatch`.
   </details>

2. "Why `re.ASCII` instead of replacing every `\d` with `[0-9]`?"
   <details><summary>Model answer</summary>

   The flag fixes every `\d` in one place and keeps the pattern identical to the published one,
   so a reviewer can diff it. Rewriting as `[0-9]` is just as correct and self-contained, which
   matters if the pattern is copied somewhere the flag won't follow, like another language or
   a JSON config. For a regex we own and might copy, I'd pick `[0-9]`. For a copied standard,
   keeping it verbatim wins.
   </details>

3. "It's only a test for a constant you control. Why bother?"
   <details><summary>Model answer</summary>

   The reviewer flagged it, and the cost was a few lines. More importantly, `info` exposes the
   version to clients, and the same pattern habits (`\d`, `$`, `search`) appear in input
   validation, where they're real bugs: a username regex with `$` would accept `"alice\n"`.
   The username check in `users.py` already uses `fullmatch` and `[A-Za-z0-9_]`, so now both
   regexes in the repo follow the same rule.
   </details>

4. "How do you know the new tests actually test something?"
   <details><summary>Model answer</summary>

   I watched them fail. The first draft passed against the old regex, because the tests called
   `fullmatch` themselves and the Unicode case never reached `\d`. After routing them through
   `is_semver` (still using `search`), the newline and Arabic-Indic cases failed. Then the fix
   made them pass. A test you haven't seen fail might be testing nothing.
   </details>
