---
id: 015
title: Run the tests on GitHub Actions (Linux and Windows)
commit: "ci: run the test suite on GitHub Actions (Linux and Windows)"
step: 17 — continuous integration (GitHub Actions)
date: 2026-11-04
tags: [ci, github-actions, tls, certificates, tls-interception, testing, supply-chain]
---

# Run the tests on GitHub Actions (Linux and Windows)

## What we did
Task 3.1 (logging) stopped at its first test run: 66 errors, all
`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. Freshly merged `master`
failed in exactly the same way, so the code wasn't the cause. The client asked to see the
certificate it received, and it wasn't ours. It had the right subject (`CN=localhost`) and
dates, but the issuer was **"Avast Web/Mail Shield Self-signed Root"**. Avast's HTTPS scanning
sits between every TLS client and server on the machine, even on `127.0.0.1`, IPv6 `::1` and
`socket.socketpair()`. It decrypts the traffic and re-encrypts it under a certificate it
signs itself. Avast added its root to the Windows trust store, so browsers accept this. Our
client trusts **only** `tests/certs/test-server.crt` (pinning, step 10), so it refuses, which
is exactly what pinning is for.

The owner chose not to change Avast. Test-only workarounds would break the tests they're
meant to run. Trusting the Avast root would make
`test_client_trusting_other_certificate_rejects_server` fail, because Avast re-signs any
certificate. Turning off verification would stop the TLS tests from testing TLS. So the
tests moved to clean machines instead. `.github/workflows/tests.yml` runs
`python -m unittest discover tests -v` on every push and pull request. It uses a matrix of
`ubuntu-latest` and `windows-latest` × Python `3.10` and `3.14`, which makes four jobs.
`README.md` gets a status badge and explains the antivirus symptom. `PLAN.md` gets Step 17.

## How it fits
- **Plan:** a new Step 17. It unblocks Task 3.1 (`refactor/logging-and-cleanups`, stashed)
  and every later batch of Step 16, because each PR now gets a check that doesn't depend on
  one laptop. It also runs the owner-only file mode test from step 11, which Windows always
  skips, so it finally runs regularly.
- **Practice:**
  - **Continuous integration:** every change is built and tested automatically on a clean
    machine. "Works on my machine" turns into a check that anyone can see. Today shows the
    other side of it too: "fails on my machine" can also be the machine's fault, and CI is
    the neutral second opinion.
  - **Test the extremes, not every combination:** the oldest Python we promise (3.10) and
    the newest (3.14), on both systems the code has OS-specific paths for (`SO_LINGER`
    packing, Ctrl+C on Windows). Python 3.10 reached end of life on 2026-10-01, so raising
    the minimum is now a real decision. It's a separate one, because it changes what the
    README promises.
  - **Supply chain:** a `uses: actions/checkout@v7` tag can be moved by whoever controls
    that repository. A full commit SHA can't, so we pin the SHA and keep the version in a
    comment. `permissions: contents: read` gives the job token the least privilege it
    needs. `timeout-minutes: 10` stops a hung socket test from burning hours.
  - `fail-fast: false`: by default one red job cancels the rest of the matrix. We want to
    know *which* combinations fail (Linux only? 3.10 only?), so all four always finish.
- **When you'd choose differently:** a big matrix (every Python × every OS) for a library
  many people install, or a single job for an app that runs on one known server. Some teams
  run tests in a container image or a pre-merge gate instead of a hosted CI. CI also
  doesn't replace running tests locally: WSL (a separate VM network that Avast doesn't
  see) or an Avast exclusion for `python.exe` are still worth setting up for fast feedback.

## Commands used
- `python -m unittest discover tests` — first run on the logging branch; 66 errors.
  See [python -m unittest](../commands.md#python--m-unittest-run-the-test-suite).
- `git stash -q` / `git stash pop -q` — run the suite on `master` without the change, to
  prove the failure was there before.
  See [git stash](../commands.md#git-stash-put-changes-aside-for-a-moment).
- `python --version` — 3.14.7, newer than the 3.13 the earlier entries used.
- `python -c "import ssl, pprint; pprint.pprint(ssl._ssl._test_decode_cert('tests/certs/test-server.crt')); print(ssl.OPENSSL_VERSION)"`
  — what our certificate says, and that Python bundles OpenSSL 3.5.7.
  `_test_decode_cert` is a private helper, fine for a one-off look and not for code.
- `openssl x509 -in tests/certs/test-server.crt -noout -ext basicConstraints,keyUsage,subjectKeyIdentifier,authorityKeyIdentifier,extendedKeyUsage`
  — the certificate's extensions (`CA:TRUE`, self-signed).
  See [openssl x509](../commands.md#openssl-x509-print-a-certificates-details).
- `openssl verify -x509_strict -CAfile tests/certs/test-server.crt tests/certs/test-server.crt`
  — `OK`: the file itself is fine, so look at what's on the wire.
  See [openssl verify](../commands.md#openssl-verify-check-a-certificate-against-trusted-ones).
- `python "$TEMP/tlsprobe.py"` / `tlsprobe2.py` / `tlsprobe3.py` — throwaway probes in the
  temp folder. The first tried the handshake with each verify flag removed: all failed. The
  second compared the SHA-256 of the certificate the server sent with the file: different.
  The third tried IPv4, IPv6 and `socketpair()`: all intercepted.
  See [python <file>](../commands.md#python-file-run-a-script-file).
- `openssl x509 -in "$TEMP/sent.pem" -noout -subject -issuer -dates -fingerprint` — the
  issuer was Avast.
- `wsl.exe -l -v` — WSL works but has no Linux installed.
  See [wsl.exe](../commands.md#wslexe-run-a-command-in-a-linux-distribution).
- `curl -sS -m 20 -o /dev/null -w "%{http_code}\n" https://api.github.com/...` and
  `git ls-remote --tags https://github.com/actions/checkout.git 'v*'` — both failed with the
  same certificate error (Avast again). The action versions and SHAs came from the GitHub
  API through a browser instead: `actions/checkout` v7.0.1 = `3d3c42e…`,
  `actions/setup-python` v7.1.0 = `6d4fd22…`, each checked twice.
  See [curl](../commands.md#curl-make-an-http-request),
  [git ls-remote](../commands.md#git-ls-remote-list-a-remotes-branches-and-tags).
- `git stash push -m "task 3.1 logging WIP"`, `git checkout master`,
  `git checkout -b ci/github-actions` — park the logging work, branch from `master`.
- `git fetch --quiet origin`, `git pull --ff-only` — bring `master` up to date after PR #3.
- `git add …`, `git commit -F -`, `git push -u origin ci/github-actions` — commit, and the
  first push of the branch, which starts the first CI run.
  See [git push](../commands.md#git-push-upload-commits-to-the-remote).

## Read more
- [Continuous Integration](https://martinfowler.com/articles/continuousIntegration.html) —
  martinfowler.com · the canonical article (rewritten 2023): integrate often, build on a
  clean integration machine, and why "works on my machine" isn't enough.
- [Learn to Use GitHub Actions: a Step-by-Step Guide](https://www.freecodecamp.org/news/learn-to-use-github-actions-step-by-step-guide/)
  — freeCodeCamp · beginner-friendly: workflows, events, jobs, steps and runners, with examples.
- [Running variations of jobs in a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations)
  — GitHub Docs · `strategy.matrix` and the "Handling failures" section on `fail-fast`.
- [Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)
  — GitHub Docs · "Pin references to actions to a commit SHA", and a minimal `GITHUB_TOKEN`
  (read-only contents by default).
- [ssl: Self-signed certificates and CA certificates](https://docs.python.org/3/library/ssl.html#self-signed-certificates)
  — Python docs · how `cafile` decides whom the client trusts, which is why an intercepting
  proxy's certificate is rejected.
- [Status of Python versions](https://devguide.python.org/versions/) — Python Developer's
  Guide · 3.10 end of life 2026-10-01, 3.14 supported until 2030. Use it to pick the CI
  matrix ends.

## Quiz

### Revise
1. What does CI give you that running the tests on your own laptop doesn't?
   <details><summary>Answer</summary>

   Every push and PR is tested automatically, on a clean and reproducible machine, and
   everyone can see the result. Local runs depend on what's installed on one laptop (here an
   antivirus that intercepts TLS), and only happen when someone remembers to run them.
   </details>
2. The client failed with `unable to get local issuer certificate`, yet
   `openssl verify -CAfile tests/certs/test-server.crt tests/certs/test-server.crt` said `OK`.
   What did that tell us, and what was the next check?
   <details><summary>Answer</summary>

   The certificate file was valid, so the problem had to be what was actually on the wire.
   The next check was to connect with verification off, take the peer's certificate
   (`getpeercert(binary_form=True)`) and compare its hash with the file. They differed, and
   the received certificate's issuer was Avast.
   </details>
3. In this matrix, how many jobs run, and what does `fail-fast: false` change?
   ```yaml
   matrix:
     os: [ubuntu-latest, windows-latest]
     python-version: ["3.10", "3.14"]
   ```
   a) 2, nothing  b) 4, a failing job no longer cancels the others  c) 4, failures are ignored
   d) 1, jobs run one after another
   <details><summary>Answer</summary>

   b) 2 × 2 = 4 jobs. With the default `fail-fast: true`, the first failure cancels the rest.
   With `false`, all four finish, so you can see which combinations fail. Failures still turn
   the run red.
   </details>
4. Spot the risk: `- uses: some-user/setup-thing@v2`.
   <details><summary>Answer</summary>

   `v2` is a tag, and its owner (or whoever compromises their account) can move it to
   different code at any time. Your CI would then run that code with your job's token. Pin
   a full 40-character commit SHA and keep `# v2` as a comment.
   </details>
5. Why does an HTTPS-scanning antivirus break our client, when Chrome on the same machine
   works fine?
   <details><summary>Answer</summary>

   The antivirus installs its own root certificate into the Windows trust store, and Chrome
   trusts that store, so the substituted certificate looks valid to Chrome. Our client uses
   `create_default_context(cafile=...)` with only our certificate, so the Avast-signed one
   has no trusted issuer and is rejected.
   </details>

### Defend the decision
1. "Your tests fail locally. Why not just set `verify_mode = CERT_NONE` in the tests, or
   add the Avast root to the test trust store?"
   <details><summary>Model answer</summary>

   Both make the tests stop testing what they claim to test. `CERT_NONE` turns the TLS tests
   into "something encrypted came back". Trusting the Avast root breaks the negative test:
   Avast re-signs *every* certificate, so a client that trusts a different certificate would
   suddenly connect, and the suite would only pass on that one laptop. The failure was
   correct behaviour (pinning caught a man-in-the-middle), so I changed where the tests
   run, not what they check: a CI matrix on clean machines, plus WSL or an antivirus
   exclusion for local runs.
   </details>
2. "Why both Ubuntu and Windows, and why Python 3.10 and 3.14 only?"
   <details><summary>Model answer</summary>

   The code has OS-specific paths: `SO_LINGER` is packed as `"ii"` on POSIX and `"HH"` on
   Windows, and Ctrl+C handling depends on the OS. The file mode test only runs on POSIX.
   For Python I test the extremes: 3.10 is the minimum the README promises, so it catches
   newer syntax used by accident, and 3.14 is current. Versions in between rarely break
   when both ends pass, and four jobs keep CI fast. A widely installed library would test
   every supported version.
   </details>
3. "The project is 'standard library only'. Isn't GitHub Actions with `actions/checkout`
   and `actions/setup-python` a third-party dependency?"
   <details><summary>Model answer</summary>

   It's a dependency of the *development process*, not of the app. Nothing is installed
   into the runtime, and the app and tests still run with plain Python anywhere. The rule
   is about what users need to run the server. Even so, CI code runs with access to the
   repository, so I treat it like a dependency: GitHub's own actions only, pinned to commit
   SHAs, a read-only token, and a timeout.
   </details>
