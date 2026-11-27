# Documentation contents

This page indexes the generated project's documentation. Browse the guides
below.

## Project guides

- [User guide](users-guide.md) explains how to use the generated project and
  its public build and test commands.
- [Developer guide](developers-guide.md) explains the contributor workflow and
  points maintainers to script automation standards.
- [Documentation style guide](documentation-style-guide.md) defines the
  spelling, structure, Markdown, Architecture Decision Record (ADR), Request
  for Comments (RFC), and roadmap conventions used by this documentation set.

## Design

- [Coupon design](design.md) describes the sweep's data flow, the modules, and
  the accessibility and styling approach.
- [ADR 001: Coupon marks and sweep shape](adrs/adr-0001-coupon-marks-and-sweep-shape.md)
  records how the five marks are derived and where the sweep runs.
- [ADR 002: Sweep with concordat main](adrs/adr-0002-sweep-with-concordat-main.md)
  records why the published coupon sweeps with concordat's current main and how
  an unknown rule is handled.

## Engineering practice

- [Complexity antipatterns and refactoring strategies](complexity-antipatterns-and-refactoring-strategies.md)
  explains cognitive complexity, the bumpy-road antipattern, and refactoring
  approaches for maintainable code.
- [Scripting standards](scripting-standards.md) explains the preferred Python
  scripting stack, command execution patterns, and test expectations for helper
  scripts.
