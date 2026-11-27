# Architectural decision record (ADR) 001: Coupon marks and sweep shape

## Status

Accepted: 2026-11-16. The coupon derives five marks from concordat's three
verdicts, runs concordat in process at a pinned commit, publishes one detail
page per repository, and runs on GitHub-hosted runners.

Amended by ADR-0002 (2026-11-27): the published coupon sweeps with concordat's
current main, and the catalogue shows an unknown rule instead of refusing it.
See [Amendments](#amendments).

## Date

2026-11-16.

## Context and problem statement

The estate needs a public page that shows, for every active repository and
every functioning concordat rule, whether the repository complies, breaches, is
exempt, or could not be judged. The page is public, so it must never name a
private repository, and it must not mislead: a wall of red marks that are
really reader limits would teach the audience to ignore it.

Concordat's rule runner reports only `compliant`, `noncompliant` and
`indeterminate`. It does not say that a rule is about something the repository
does not have, and it does not say that a shipped exemption applied.

## Decision drivers

- Public output: no private names, no tokens, no CDN.
- Honest marks: a mark that nobody proved must not look like a breach.
- GitHub's REST quota is shared estate-wide, so the sweep must clone with git
  and keep API calls to pin and certification lookups.
- One developer and robots: no approval rituals, and a scheduled job that
  needs no attention.

## Options considered

### Option A: shell out to `concordat artefact rule run`

The public command-line contract is stable, but every rule invocation pays
interpreter start-up (about one second), and the Whitaker certification answers
cannot be shared between repositories, which cost about 17 REST calls per Rust
repository in measurement.

### Option B: import concordat as a library, pinned to a commit

Start-up is paid once per worker process, one certifier is shared by every
repository the process sweeps, and the page can print the exact concordat
commit. The cost is a dependency on concordat's rule-runner modules, which are
not a published API; the pin to one commit contains that risk.

| Topic           | Option A     | Option B                |
| --------------- | ------------ | ----------------------- |
| Start-up cost   | Per rule     | Per worker process      |
| REST calls      | About 17 per | Shared; a few per sweep |
|                 | Rust repo    |                         |
| Coupling        | CLI contract | Pinned internal modules |
| Reproducibility | Version only | Exact commit            |

_Table 1: Trade-offs between shelling out and importing concordat._

## Decision outcome

Option B. Concordat is a git dependency at a full commit SHA. The catalogue
module declares where each package sits on the coupon and refuses a package it
does not know, so a new rule fails the build instead of vanishing from the page.

### The five marks

- **Compliant:** a clean verdict. Drawn as a quiet tick, never a cross: to a
  reader a cross means failure, and it is the most common mark.
- **Non-compliant:** at least one finding that is not an unproven fact. Drawn
  as the finding count in red, underlined.
- **Indeterminate:** only unproven findings. A finding is unproven when
  concordat marks it indeterminate, or when its message names a reader limit
  (for example "cannot be proven" or "unresolved Make variables"). Concordat
  reports some of these as non-compliant; the dashboard does not print them red.
- **Exempt:** a clean verdict and a shipped exemption (the package's
  `parameters.defaults.exemptions`) naming the repository. The wording is
  "exemption on record": the runner does not say whether the exemption was
  needed.
- **Not applicable:** a clean verdict on a repository that lacks the trait the
  rule is about (Rust, Python, or uv use). A finding always wins over a missing
  trait.

### Publication

The sweep fetches each public, active, non-fork repository with a shallow git
fetch and sets `origin` to the GitHub URL, because concordat keys exemptions on
the origin slug. The page is a single coupon plus `repos/<name>.html` for the
finding text, so the coupon stays small. A scheduled GitHub Actions workflow on
GitHub-hosted runners builds the site and deploys it with GitHub Pages.

## Known risks and limitations

- The reader-limit phrases are a maintained list; a new phrasing in concordat
  reads as a breach until it is added to `UNPROVEN_MARKERS`.
- Trait detection is heuristic (file names and a text search for `uv`).
- A repository-scoped Actions token cannot see private repositories, so their
  count comes from the `PRIVATE_REPOSITORY_COUNT` repository variable or is
  omitted.
- Whitaker certification and pin lookups use the Actions token's REST budget; a
  lookup that fails marks the affected cells indeterminate with the reason.

## Amendments

### 2026-11-27: ADR 002

The decision above (a git dependency at one commit, and a catalogue that
refuses an unknown package) is kept as history. It now describes the floor for
tests and local builds only. The published coupon sweeps with concordat's
current main, and an unknown package becomes a `NEW RULES` column with a
warning; see [ADR 002](adr-0002-sweep-with-concordat-main.md).
