"""
MedSafe API Routers

SKILL: @api-design-principles - Clean router organization
SKILL: @fastapi-templates - Modular router structure

Routers disponíveis:
- health: Health checks e métricas
- langgraph: LangGraph Multi-Agent System (v2)

NOTA: Não importar módulos automaticamente para evitar import circular.
Use imports explícitos: from backend.app.routers import health
"""

# Não fazer imports automáticos - causa problemas com circular imports
__all__ = ["health", "langgraph"]
