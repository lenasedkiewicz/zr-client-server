---
id: 008
title: Merge master into feature/admin (merge vs rebase)
commit: "Merge branch 'master' into feature/admin"
step: none — integration of Steps 8–13 (feature/admin) with Step 14 (master)
date: 2026-10-21
tags: [git, merge, rebase, conflicts, pull-request, workflow]
---

# Merge master into feature/admin (merge vs rebase)

## What we did
PR #1 (`feature/admin` → `master`) showed `mergeable: CONFLICTING`. The two branches had
split at `3eafafb`: the feature branch added 7 commits (register, login, TLS, owner-only
users file, lockout, admin on first start), and master added 3 (git-ignore the TLS key and
users file, version `0.1.0-alpha`, the NDJSON concept note). We merged `origin/master` into
`feature/admin` and resolved four conflicted files. After that the PR merges cleanly, and
the feature branch reports `0.1.0-alpha` in `info`.

Two of the conflicts weren't really about text. Both branches had handed out the **same
numbers**:
- **Dev journal:** both had an entry `001`. Master's entry, dated 10-19, is later than the
  feature's 001–006, so it became `007-alpha-version-in-info.md` (with a new `id:`), listed
  in date order in `docs/dev-journal/README.md`.
- **PLAN.md:** both had added a "Step 8". The feature's Steps 8–13 stayed, and master's
  versioning step became **Step 14**. Its references in journal 007 and concept 001 were
  updated to match.

The rest was combining both sides. `tests/test_server.py:3` now imports `json`, `os` and
`re`, and `test_version_is_semver` sits next to the feature's
`test_help_logged_in_lists_all_commands`. In `docs/commands.md`, the feature's more complete
reference is the base, and from master's version we kept only what was new
(`git branch --show-current`, the `git diff <commit> -- <path>` form, the `sed -i`
delimiter/BSD notes). `config.py` and the concept notes merged without conflicts.

## How it fits
- **Plan:** no new step. This integrates the work so PR #1 can land on `master`. The next
  feature work (`promote`, admin-only `stop`, from Step 13's "Next") starts from a branch
  that already follows the versioning rules in Step 14.
- **Practice:** *merge vs rebase.* Both bring master's changes into the feature branch:
  - `git merge origin/master` adds **one merge commit** with two parents and leaves the
    existing commits as they are. History shows what really happened, including when master
    was brought in. It is safe on a pushed branch: a plain `git push` only adds commits.
  - `git rebase origin/master` **replays** the 7 feature commits on top of master as new
    commits with new hashes. The result is a straight line, but the branch was already
    pushed and has an open PR, so it would need `git push --force` and would break anyone
    who had pulled it. You could also end up resolving similar conflicts once per replayed
    commit instead of once in total.
  - The usual rule (Pro Git): rebase your *local, unpushed* commits to tidy them, and never
    rebase what others may have built on. We'd choose rebase for a private branch, or if
    the team requires a linear history, ideally before the first push.
  - *Numbering collisions:* IDs handed out separately on two branches (journal entries, plan
    steps, database migrations, ADRs) don't cause file-level conflicts in git. Here the two
    `001-*.md` files had different names, so git happily kept both. Only a person checking
    the meaning catches that. Teams avoid it with timestamps or a central counter, or by
    keeping branches short-lived.

## Commands used
- `git fetch --all --prune` — update `origin/master` and `origin/feature/admin` before comparing
- `git branch -a` — see local and remote-tracking branches
- `gh pr view 1 --json headRefName,baseRefName,mergeable,title` — confirm PR #1's branches and that it was `CONFLICTING`
- `git status -sb` — check the branch and whether it was in sync with its upstream
- `git log --oneline master..origin/master` (and the other directions) — list the commits only one side has
- `git merge-base origin/master origin/feature/admin` — find where the branches split (`3eafafb`)
- `git merge-tree --write-tree --name-only …` — tried to preview conflicts; this git version doesn't support `--write-tree` (exit 129), so we merged directly instead
- `git checkout feature/admin` — switch to the PR branch
- `git merge origin/master --no-edit` — start the merge; it stopped on 4 conflicts
- `git status --short` — list `UU` (conflicted) and `A ` (added) files
- `git diff` — show the conflicts in combined format
- `awk '/^<<<<<<< /{p=1} p{print NR": "$0} /^>>>>>>> /{p=0}' <file>` — print only the conflict regions with line numbers
- `grep -n '^<<<<<<<\|^=======\|^>>>>>>>' PLAN.md` — locate conflict markers
- `sed -n 100,112p PLAN.md` — read the context around the PLAN conflict
- `git ls-tree --name-only origin/feature/admin docs/concepts/` — check which concept notes the feature branch had
- `python - <<'EOF' … EOF` and `python <file>` — scripted conflict resolution that keeps each file's CRLF line endings
- `git mv docs/dev-journal/001-alpha-version-in-info.md docs/dev-journal/007-alpha-version-in-info.md` — renumber master's journal entry
- `sed -i 's/^id: 001$/id: 007/; s/Step 8/Step 14/g' <file>` — update the entry's id and step references
- `grep -rn '1\.0\.0\|0\.1\.0-alpha' --include=*.md --include=*.py .` — check that every version mention agrees
- `grep -rln '^<<<<<<<\|^>>>>>>>' . --include=*.md --include=*.py` — make sure no markers are left
- `file docs/commands.md PLAN.md tests/test_server.py` — confirm the line endings were kept
- `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR)"` — 40 tests, OK (1 skipped on Windows)
- `git add …` / `git commit` — record the merge commit
- `git push origin feature/admin` — update PR #1

## Read more
- [Git Branching — Rebasing](https://git-scm.com/book/en/v2/Git-Branching-Rebasing) — Pro Git (official) · "The Perils of Rebasing" and "Rebase vs. Merge": never rebase commits that exist outside your repository
- [git-merge documentation](https://git-scm.com/docs/git-merge) — git-scm (official) · "How conflicts are presented" (markers, `diff3`/`zdiff3`) and `--abort`
- [The Ultimate Guide to Git Merge and Git Rebase](https://www.freecodecamp.org/news/the-ultimate-guide-to-git-merge-and-git-rebase/) — freeCodeCamp · beginner-friendly diagrams of a merge commit vs a rebased branch
- [Resolving a merge conflict using the command line](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/addressing-merge-conflicts/resolving-a-merge-conflict-using-the-command-line) — GitHub Docs · the edit → `git add` → `git commit` loop we used to unblock the PR

## Quiz

### Revise
1. What does a merge commit have that an ordinary commit doesn't?
   <details><summary>Answer</summary>

   Two (or more) parents: the tip of the current branch and the tip of the merged branch.
   That's how history records that the two lines of work were joined.
   </details>
2. In a conflicted file, which side is between `<<<<<<< HEAD` and `=======` when you run
   `git merge origin/master` while on `feature/admin`?
   a) master's version b) feature/admin's version c) the common ancestor d) the merged result
   <details><summary>Answer</summary>

   b) `HEAD` is the checked-out branch, `feature/admin`. Master's version is between
   `=======` and `>>>>>>> origin/master`. (During a rebase this flips: `HEAD` is the branch
   being rebased onto.)
   </details>
3. What does `git log --oneline origin/master..origin/feature/admin` list?
   <details><summary>Answer</summary>

   The commits reachable from `origin/feature/admin` but not from `origin/master`, i.e. the
   PR's own commits (7 here).
   </details>
4. Spot the problem: both branches added `docs/dev-journal/001-….md` with different slugs,
   and `git merge` reported no conflict for those files. Is everything fine?
   <details><summary>Answer</summary>

   No. Git compares file paths, and the paths differ, so it kept both. But the project now
   has two entries with id `001`, and the README conflict was only a symptom. The fix was to
   renumber master's entry to `007`. Git can't catch a clash in meaning like this.
   </details>
5. You're halfway through resolving conflicts and realise you started the merge on the wrong
   branch. What command gets you back, and what does it cost?
   <details><summary>Answer</summary>

   `git merge --abort`. It restores the state before the merge and throws away the conflict
   resolutions made so far (and it may not fully restore uncommitted changes that existed
   before the merge).
   </details>

### Defend the decision
1. "Why did you merge master into the feature branch instead of rebasing it?"
   <details><summary>Model answer</summary>

   The branch was already pushed and had an open PR. A rebase would rewrite all 7 commits
   with new hashes and need a force-push, which breaks anyone who had pulled the branch and
   can confuse the PR's review history. A merge adds one commit and keeps everything else.
   We also resolved the conflicts once instead of possibly once per replayed commit. The
   cost is a non-linear history with an extra merge commit. If the team wanted a linear
   `master`, we could still squash-merge the PR, or rebase while the branch was private.
   </details>
2. "Why renumber master's journal entry and plan step rather than the feature branch's?"
   <details><summary>Model answer</summary>

   Fewer changes and correct chronology. The feature branch had 6 journal entries (10-05 to
   10-16) and 6 plan steps (8–13) with links between them. Master had one of each, dated
   later (10-19). Moving the single later item to the end (`007`, Step 14) keeps the
   numbering in date order and touches 3 references instead of dozens.
   </details>
3. "How would you prevent the same numbering clash next time?"
   <details><summary>Model answer</summary>

   Keep branches short-lived and merge master into them often, so clashes are found while
   they're small. Or use IDs that can't collide, such as a date or timestamp prefix (as many
   database-migration tools do). Or reserve numbers in one place, like the plan, before
   starting the work. Sequential numbers stay readable, but only with a single writer at a
   time.
   </details>
