# CLAUDE.md

## Required workflow

- **Every** code change in this repository goes through the `learn-by-commit` skill
  (`.claude/skills/learn-by-commit/SKILL.md`): invoke it before the first edit, give the
  briefing, wait for approval, then code, journal and commit. No exceptions for "small"
  changes. The skill itself decides when a chunk is trivial enough to skip the journal.
- **Every** concept question the user asks ("what is X?", "why X over Y?") also goes through
  the skill, which saves the answer as a concept note in `docs/concepts/`.

## Project constraints

- Python 3.10+, standard library only (no third-party packages or frameworks).
- Tests: `python -m unittest discover tests`.
