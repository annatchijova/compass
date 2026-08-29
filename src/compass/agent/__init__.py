"""Agente ADK de COMPASS.

`root_agent` es el punto de entrada que descubre `google-adk` (por
convención de ADK: un módulo con un `root_agent`). Vive aislado del core:
`compass.api` y el resto del paquete NO importan este módulo, así que
COMPASS sigue corriendo (CLI, API con backend fake, tests) sin tener
`google-adk` instalado. Solo quien usa el agente paga la dependencia.
"""

from .agent import root_agent

__all__ = ["root_agent"]
