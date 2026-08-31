"""Cloud Run entry point that ADK's agent loader discovers.

ADK scans the agents directory and imports each subfolder as a top-level
package, expecting a `root_agent`. The real team lives in the installed
`compass` package and uses RELATIVE imports into the deterministic core
(`from .. import domain, engine, ...`), so it must be loaded as
`compass.agent` — it cannot be copied out as a standalone folder. This thin
wrapper re-exports it with an ABSOLUTE import, which resolves because the
`compass` package is pip-installed in the image.
"""

from compass.agent import root_agent

__all__ = ["root_agent"]
