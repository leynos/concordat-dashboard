# Coupon design

The coupon is a static page that lays the estate's repositories (numbered rows)
against concordat's rule packages (narrow ruled columns grouped under printed
block headings), in the manner of a 1963 football pools coupon. The decisions
behind the marks and the sweep are in
[ADR 001](adr-001-coupon-marks-and-sweep-shape.md).

## Data flow

The sweep runs in four stages:

1. `estate` lists the owner's repositories once and keeps the public, active,
   non-fork ones. Private repositories are counted and never named.
2. `checkout` fetches each repository's default branch into a fresh git
   repository whose `origin` is the GitHub URL.
3. `runner` runs every rule package in process, and `classify` turns the raw
   findings, the repository's traits and the shipped exemptions into one `Cell`
   per rule.
4. `view` and `render` shape the `Sweep` into the coupon page and one detail
   page per repository.

The sweep is written to `sweep.json` and published beside the pages, so the
rendering can be re-run without sweeping again.

## Modules

| Module      | Responsibility                                             |
| ----------- | ---------------------------------------------------------- |
| `model`     | Frozen value types: `Sweep`, `RepoResult`, `Cell`, `State` |
| `catalogue` | Block and applicability of each rule; exemption index      |
| `estate`    | Repository listing and exclusion counts                    |
| `checkout`  | Default-branch checkout with the right `origin`            |
| `traits`    | Rust, Python and uv detection                              |
| `runner`    | In-process concordat runner with a shared certifier        |
| `classify`  | The five-state decision and the unproven-finding rule      |
| `sweep`     | Orchestration across a process pool                        |
| `serialize` | `sweep.json` reading and writing                           |
| `view`      | Counts, ordering and block grouping for the coupon         |
| `marks`     | Glyph, wording and link for one mark                       |
| `detail`    | The per-repository page view                               |
| `render`    | Jinja environment and site writer                          |
| `cli`       | `sweep` and `render` commands                              |

_Table 1: Modules in `concordat_dashboard`._

## Accessibility

The grid is a real table with a caption, header scopes and a sticky repository
column. Every mark carries text for assistive technology and a `title`, so no
state depends on colour or glyph alone. The pencil annotation in the margin is
decorative and hidden from assistive technology. On narrow screens the number
and head columns drop away and the grid scrolls sideways.

## Styling

Tailwind CSS 4.3.5 is compiled statically with the pinned `@tailwindcss/cli`
(`bun.lock`); the published page loads no script and no remote stylesheet. The
condensed face, Barlow Condensed, is self-hosted from `assets/fonts` under the
SIL Open Font License (see `assets/fonts/OFL.txt`).
