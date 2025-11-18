"""
AG2/AutoGen Agents - DEPRECATED

MIGRATION STATUS: ⚠️ LEGACY CODE
Sistema migrado para LangGraph Multi-Agent System

Estes agentes foram substituídos pelo sistema LangGraph localizado em:
/backend/app/langgraph_agents/

AGENTS DEPRECADOS:
1. CaptainAgent (orchestrator.py) - REMOVIDO
   → Substituído por: LangGraph StateGraph orchestration

2. DocAgent (docagent.py) - REMOVIDO
   → Substituído por: DocumentAgent (LangGraph)

3. ClinicalRulesAgent (clinical.py) - REMOVIDO
   → Substituído por: ClinicalAgent (LangGraph)

4. Safety Guardrails (safety_guardrails.py) - MOVIDO
   → Substituído por: SafetyAgent (LangGraph)

5. Human-in-the-Loop (human_in_the_loop.py) - MOVIDO
   → Substituído por: HITLAgent (LangGraph)

6. Reflection Agent (reflection_agent.py) - MOVIDO
   → Substituído por: ReflectionAgent (LangGraph)

EXCEÇÃO:
- VisionAgent (vision.py) - Ainda em uso no endpoint /api/v1/vision/analyze
  → Pendente migração para LangGraph

MOTIVO DA MIGRAÇÃO:
- LangGraph oferece StateGraph declarativo e observabilidade superior
- Checkpointing nativo com PostgreSQL
- Padrões agênticos mais claros (Reflection, HITL, Safety, RAG)
- Melhor integração com patterns do "Agentic Design Patterns" (Antonio Gulli)

Para mais informações, consulte:
/docs/MIGRATION_AG2_TO_LANGGRAPH.md

Data de migração: 2025-11-18
"""

__all__ = []
