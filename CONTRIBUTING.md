# Contributing to appn-linked-data

This project follows the [APPN Coding Standards](https://github.com/aus-plant-phenomics-network/{{STANDARDS_REPO}}/blob/main/APPN-Coding-Standards.md).
That guide is normative; this file covers what is specific to this repository.

## Local setup

```bash
{{setup commands — the same ones in the README Install section}}
{{pre-commit install, if this repo uses pre-commit}}
```

## Branching

Trunk-based, short-lived branches (§3.3):

- `main` is always deployable; direct pushes are blocked.
- Branch names: `feature/<short-description>`, `fix/<short-description>`,
  `chore/<short-description>`.
- Branches live days, not weeks.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <imperative summary, ≤72 chars>

<body: why the change was made, not what changed>

Refs: #1234
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`.

Put closing keywords (`Closes #1234`) in the **pull request description**, not in
individual commits — a squash merge can otherwise close issues unexpectedly.

## Before opening a pull request

Run the same checks CI runs, with one command:

```bash
make check
```

Then work the checklist in §11 of the standards:

- [ ] Formatter and linter run clean
- [ ] Type checks pass
- [ ] Tests added for new behaviour; full suite passes locally
- [ ] No secrets, credentials or data files in the diff
- [ ] Public functions documented
- [ ] README / CHANGELOG updated if behaviour or setup changed
- [ ] Commented-out code and debug statements removed
- [ ] PR description explains what, why, how tested, and rollback

Keep pull requests under ~400 changed lines where practicable. Open a **draft**
PR early to surface direction, and mark it ready once CI is green.

## Review

- One approving reviewer minimum; two for changes to authentication,
  identifiers, persistence guarantees, or anything writing to production data.
- Reviewers do not comment on formatting — that is the formatter's job.
- Ask questions rather than issue commands; prefix optional comments with `nit:`.

## Deviating from the standards

Standards that cannot be followed here are documented, not ignored. Record the
deviation in `docs/decisions/` with the reason and the conditions under which it
should be revisited (§12).
