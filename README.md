# concordat-dashboard

A static, public compliance dashboard for the leynos estate, laid out like a
1963 football pools coupon: repositories as numbered rows, concordat rules as
narrow ruled columns, and a mark in every cell.

A Python and Jinja generator sweeps every public, active, non-fork repository
against every functioning concordat rule and renders the result with statically
compiled Tailwind CSS. A scheduled GitHub Actions workflow publishes it with
GitHub Pages. See the [users' guide](docs/users-guide.md) to read the coupon
and build it locally, and the [documentation contents](docs/contents.md) for
the design.
