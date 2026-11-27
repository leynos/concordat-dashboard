# Architectural decision record (ADR) 002: Sweep with concordat main

## Status

Accepted: 2026-11-27. The published coupon sweeps with concordat's current main
on every run. The pinned commit remains the floor for tests and local builds. A
rule the catalogue does not know becomes a visible column instead of failing
the run. Amends [ADR 001](adr-0001-coupon-marks-and-sweep-shape.md).

## Date

2026-11-27.

## Context and problem statement

ADR 001 pinned concordat to one commit so that a sweep was reproducible, and
had the catalogue refuse any rule package it did not know. Within two weeks the
pin was stale: the published coupon missed the rules concordat had gained since
(gate-workspace-coverage, nested-cargo-cold-build and pr-run-cancellation), so
it understated the estate's findings. The owner's ruling was that the daily
rebuild must use the latest concordat main. Installing main exposed the second
half of the problem: the refusal would abort the whole run on the first rule
the catalogue had not yet placed.

## Decision drivers

- The page must report against the rules the estate is held to today.
- A broken main must fail the run visibly, never fall back to old rules.
- Tests and local builds must stay reproducible.
- A new rule must reach the page without a dashboard release.

## Options considered

### Option A: bump the pin on a schedule

A bot or a person bumps the SHA. The page lags by the bump interval, and a
missed bump is invisible.

### Option B: `uv lock --upgrade-package concordat` in the workflow

The runner re-resolves the lock on every run. It rewrites `uv.lock` on the
runner, so `uv sync --frozen` and the lock disagree. A local run cannot name an
arbitrary branch or commit either.

### Option C: install the ref over the locked environment

`CONCORDAT_REF` names a git ref. `make concordat-ref` installs it with
`uv pip install --reinstall-package concordat --refresh-package concordat`, and
`sweep` and `render` run with `uv run --no-sync` so the lock cannot undo it.
The lock stays the floor for tests. An unreachable ref fails the build.

## Decision outcome

Option C. The Pages workflow sets `CONCORDAT_REF: main`; the job summary and
the coupon footer record the commit used (`concordat-dashboard concordat`
prints it and exits with status 1 when there is none).

The catalogue changes from refusal to visibility:

- an unknown package becomes a column under the `NEW RULES` block, judged
  against every repository, with an "Unplaced rule" workflow warning;
- a declared package that concordat no longer ships is dropped with an "Absent
  rule" warning, and the packages root is found without depending on any one
  rule; and
- a directory with a `policy` but no `rule.yaml` stops the run, because
  concordat can run it and omitting it would hide a rule.

## Known risks and limitations

- Main can change a rule-runner module the dashboard imports. That fails the run
  and leaves the previous page in place; the pinned tests only catch it when
  the pin is bumped.
- Adding a placement for a new rule, or removing a stale one, is a manual step
  prompted by the warnings.
