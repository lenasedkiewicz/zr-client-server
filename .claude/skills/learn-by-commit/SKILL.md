---
name: learn-by-commit
description: Use for EVERY chunk of coding work in this repository (one chunk = one commit). Explains the change before coding, relates it to plan.md and general practice, then after the change writes a dev-journal entry with verified online resources and a quiz for revision and interview-style defence of decisions.
---

# Learn by commit

The owner of this repo builds it while preparing for junior and mid software engineer interviews. Every commit is also a lesson, and the lessons will later be imported as a learning track. Work in small chunks, where **one chunk is one commit**. Follow the steps below for every chunk, in order. The user approves tool calls manually, so the explanation must come before the code.

## 1. Before coding: the briefing (in chat, before any edit)

Write a short briefing with these three headings:

**a) What we're doing**
- The goal of this chunk in 2–4 sentences.
- The files that will be created or changed, with one line each on why.
- Name any new dependency and say why it was chosen over the obvious alternative.

**b) How it fits**
- *In the plan:* which milestone and item in `plan.md` this chunk delivers. Say what it unblocks next.
- *In general practice:* the engineering principle or pattern behind it. Examples: separation of concerns, pure functions, schema migrations, idempotency, test pyramid, conventional commits. Explain it in plain words, and say when you would *not* do it this way.

**c) Commit**
- The proposed commit message, in Conventional Commits format (`feat:`, `fix:`, `test:`, `chore:`, `docs:`, `refactor:`).

Keep the briefing tight, at roughly one screen. If the chunk turns out to be too big for one logically connected commit, propose splitting it.

## 2. Code

Implement only what the briefing describes. When you make a decision the briefing didn't foresee, say so in one line as you go. Run the relevant tests, lint or typecheck before the commit, and report the result honestly.

## 3. Dev-journal entry (part of the same commit)

Create `docs/dev-journal/NNN-<kebab-slug>.md`. `NNN` is the next free three-digit number. Use this template:

```markdown
---
id: NNN
title: <chunk title>
commit: "<commit message subject>"
milestone: <A|B|C|D> — <plan item>
date: <YYYY-MM-DD>
tags: [<topics, e.g. sqlite, drizzle, migrations, testing>]
---

# <chunk title>

## What we did
<what changed and why, 1–2 short paragraphs; reference key files as `path:line`>

## How it fits
- **Plan:** <milestone, what it unblocks>
- **Practice:** <the principle(s), trade-offs, when you'd choose differently>

## Commands used
- `<command --flags>` — <what it was for in this chunk>
<every command run; explanations live in docs/commands.md>

## Read more
- [<title>](<url>) — <source> · <one line: what to take from it>
<3–6 links>

## Quiz

### Revise
1. <question checking understanding of a concept>
   <details><summary>Answer</summary>

   <answer, 1–4 sentences>
   </details>
<4–6 questions, mixed: multiple choice (list options a–d), short answer, "what does this code do", "spot the bug">

### Defend the decision
1. <interview-style question about a decision made in THIS commit, e.g. "Why an append-only ledger instead of a balance column?">
   <details><summary>Model answer</summary>

   <answer naming the trade-offs and the alternative>
   </details>
<2–4 questions>
```

### Commands used (journal section plus `docs/commands.md`)

Add a `## Commands used` section to the entry, between "How it fits" and "Read more". List every shell command run for this chunk, including setup, debugging and verification, with the exact flags. One line each: `` `command --flags` `` and what it was for here. Then update **`docs/commands.md`**, the cumulative reference:
- Any command or flag **not yet explained** there gets an entry in the right section, using the file's format: syntax, what it does, each flag, a repo example, a PowerShell equivalent where it differs, and `*First used in NNN*`.
- A command already explained but used with a **new flag** gets that flag added to its entry.
- Don't explain anything twice. Link instead, for example `see [mkdir](../commands.md#mkdir-make-a-directory)`.
- Flag destructive commands (`rm -rf`, `git reset --hard`, `--force`) with ⚠️ and say when they're safe.

### Rules for "Read more"
- Prefer high-quality developer sources: freeCodeCamp (news/articles and the curriculum), MDN, official docs (react.dev, nextjs.org, typescriptlang.org, sqlite.org, orm.drizzle.team, vitest.dev, nodejs.org), web.dev, martinfowler.com, kentcdodds.com, roadmap.sh, Refactoring Guru, The Odin Project, conventionalcommits.org.
- Use WebSearch to find each link, then **check it with WebFetch** before including it. Never include a URL you haven't fetched successfully. If none can be verified, say so instead of inventing one.
- Include at least one beginner-friendly link (freeCodeCamp or MDN) and at least one deeper or official link per entry.
- Links must match the concepts in *this* commit, not generic tutorials.

### Rules for the quiz
- Questions must be answerable from this commit's code plus the linked reading.
- "Defend the decision" questions must reference the actual choices in this repo, so the user can talk about the project in an interview.
- Mix difficulty: roughly a third junior-level and the rest mid-level.

## 4. Commit

Stage the code and the journal entry together, then show the user the final commit message for approval. Never push unless asked. After committing, finish with a one-line summary and the path to the journal entry. Do not repeat the quiz in chat.

## Concept notes (questions asked in chat)

When the user asks a concept question such as "what is Drizzle?" or "why X over Y?", whether during a chunk or between chunks, answer in chat first. Then save the answer as a concept note:

- Create `docs/concepts/NNN-<kebab-slug>.md`. `NNN` is the next free three-digit number in `docs/concepts/`, counted separately from the dev-journal numbers. Refer to notes as `concept NNN`.
- Use this frontmatter:
  ```markdown
  ---
  id: NNN
  title: <concept>
  date: <YYYY-MM-DD>
  asked-during: <dev-journal id or commit subject in progress, or "between commits">
  tags: [<topics>]
  ---
  ```
- The body holds the chat explanation, tidied: what it is, where it fits in Quest Ledger, alternatives and trade-offs, and a short "interview answer". End with a **Read more** section that follows the same link rules as the dev-journal: every link is checked with WebFetch.
- Add one line to `docs/concepts/README.md` in the form `- NNN · YYYY-MM-DD · [Title](NNN-slug.md): one-line hook`.
- If the topic already has a note, update that note and its `date` instead of making a new one.
- Commit the note with the current chunk. If no chunk is in progress, use a separate `docs:` commit, which needs no journal entry.
- When a dev-journal entry touches a concept that has a note, link to the note under **Read more**.

## Exceptions

For trivial chunks (a typo, a formatting-only change, a dependency bump), skip the journal and say so in the briefing.
