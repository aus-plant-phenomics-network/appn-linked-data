# 1. Record architecture decisions

- **Status:** Accepted
- **Date:** {{YYYY-MM-DD}}
- **Deciders:** {{names or roles}}

## Context

Decisions that constrain future work — a database choice, an identifier scheme,
an authentication model, a deliberate deviation from the APPN Coding Standards —
get made in meetings and chat threads, and the reasoning is lost within months.
The next person sees only the outcome and cannot tell whether it was considered
or accidental.

## Decision

We record such decisions as short Architecture Decision Records in
`docs/decisions/`, one page maximum, numbered sequentially and never deleted.

A decision earns an ADR when it is a **one-way door**: expensive to reverse, or
something a future maintainer would otherwise be tempted to "fix" without
knowing why it is the way it is.

Superseded records stay in place with their status changed to
`Superseded by ADR-NNNN`. The history is the point.

## Consequences

- Reviewers can ask "does this need an ADR?" as a routine review question (§11).
- New starters can read the decision history rather than reconstructing it.
- Writing an ADR costs perhaps twenty minutes, which is the whole argument for
  keeping them to one page.
