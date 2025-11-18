"""
MedSafe API - Sistema de Contraindicação de Medicamentos
API Principal com FastAPI, AG2 + Ollama, PostgreSQL + pgvector
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn
import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

# Importar configurações e módulos
from .config import settings
from .db.database import init_db, check_db_health, get_db_stats
from .db.models import Triage, Report, Document, Embedding, IngestJob
# NOTE: CaptainAgent AG2 removido - migrado para LangGraph
from .schemas import (
    TriageCreate, TriageResponse, TriageReport,
    VisionRequest, VisionResponse,
    ReportCreate, ReportResponse,
    MedicationSearch, MedicationSearchResult,
    IngestRequest, IngestResponse
)

# Configurar logging estruturado com cores
import logging
import os
from .utils.logging_config import setup_logging, log_api_request, log_api_response

# Setup logging estruturado
# SKILL: @ultrathink - Logging file opcional, Docker usa stdout por padrão
log_file = os.getenv("MEDSAFE_LOG_FILE", None)  # None = apenas console (Docker-friendly)
setup_logging(log_level=settings.log_level, log_file=log_file)
logger = logging.getLogger(__name__)

logger.info("="*80)
logger.info("🏥 MedSafe - Sistema de Contraindicação de Medicamentos")
logger.info(f"   Versão: {settings.app_version}")
logger.info(f"   Ambiente: {'Produção' if not settings.debug else 'Desenvolvimento'}")
logger.info("="*80)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializar e limpar recursos da aplicação"""
    # Inicialização
    logger.info("🚀 Iniciando MedSafe API...")

    try:
        # Inicializar banco de dados
        init_db()
        logger.info("✅ Banco de dados inicializado")

        # Verificar saúde dos serviços
        await check_services_health()

        logger.info("✅ MedSafe API iniciada com sucesso!")

    except Exception as e:
        logger.error(f"❌ Erro na inicialização: {e}")
        raise

    yield

    # Limpeza
    logger.info("🔄 Encerrando MedSafe API...")


# Configuração da aplicação
app = FastAPI(
    title=settings.app_name,
    description="Sistema de Contraindicação de Medicamentos baseado em diretrizes OMS/ANVISA",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

# Middleware de segurança
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configurar hosts permitidos em produção
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NOTE: Agentes AG2 removidos - sistema migrado para LangGraph
# VisionAgent AG2 ainda usado em /api/v1/vision/analyze (instanciado localmente)

# WORKAROUND: Routers inline devido a problemas obscuros de import no Docker
# Ver ROUTER_IMPORT_ISSUE.md para detalhes
# SKILL: @ultrathink - Pragmatismo > Pureza

# Health & Monitoring Endpoints (inline)
from fastapi import APIRouter
health_router = APIRouter(tags=["Health & Monitoring"])

@health_router.get("/healthz")
async def health_check():
    """Health check endpoint - Retorna status da aplicação"""
    try:
        from .db.database import check_db_health

        db_healthy = check_db_health()

        return {
            "status": "healthy" if db_healthy else "degraded",
            "timestamp": datetime.now().isoformat(),
            "version": settings.app_version,
            "services": {
                "database": "ok" if db_healthy else "error",
                "api": "ok"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@health_router.get("/metrics")
async def metrics():
    """Prometheus-style metrics endpoint"""
    try:
        from .db.database import get_db_stats

        db_stats = get_db_stats()

        return {
            "medsafe_requests_total": 0,  # TODO: Implementar contador
            "medsafe_embeddings_total": db_stats.get("embeddings_count", 0),
            "medsafe_documents_total": db_stats.get("documents_count", 0),
            "medsafe_triage_total": db_stats.get("triage_count", 0),
            "medsafe_reports_total": db_stats.get("reports_count", 0)
        }
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return {}

@health_router.get("/readyz")
async def readiness_check():
    """Readiness probe (Kubernetes) - Retorna 200 se pronto"""
    try:
        from .db.database import check_db_health

        db_healthy = check_db_health()

        if not db_healthy:
            return {
                "status": "not_ready",
                "reason": "Database not available"
            }

        return {
            "status": "ready",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "reason": str(e)
        }

# Registrar health router
app.include_router(health_router)
logger.info("✅ Health endpoints registrados (inline)")


async def check_services_health():
    """Verificar saúde dos serviços essenciais"""
    # Verificar banco de dados
    if not check_db_health():
        raise Exception("Banco de dados não está saudável")

    # Verificar Ollama
    try:
        import requests
        response = requests.get(f"{settings.ollama_host}/api/tags", timeout=5)
        if response.status_code != 200:
            raise Exception("Ollama não está respondendo")
    except Exception as e:
        logger.warning(f"⚠️ Ollama não está disponível: {e}")


# Health endpoints movidos para routers/health.py
# Mantido aqui apenas para referência - REMOVIDO para evitar duplicatas


# Endpoints principais da API
@app.post("/api/v1/triage", response_model=TriageResponse)
async def create_triage(
    triage_data: TriageCreate,
    background_tasks: BackgroundTasks
):
    """
    Criar triagem e disparar análise assíncrona

    UPDATED: Migrado para LangGraph Multi-Agent System
    """
    try:
        # Gerar ID da sessão
        session_id = str(uuid.uuid4())

        # Criar triagem no banco
        from .db.database import get_db_context
        with get_db_context() as db:
            triage = Triage(
                user_id=triage_data.user_id if hasattr(triage_data, 'user_id') else None,
                age=triage_data.age,
                weight=triage_data.weight,
                pregnant=triage_data.pregnant,
                cid_codes=triage_data.cid_codes,
                meds_in_use=triage_data.meds_in_use,
                allergies=triage_data.allergies,
                renal_function=triage_data.renal_function,
                hepatic_function=triage_data.hepatic_function,
                notes=triage_data.notes,
                status="pending"
            )

            db.add(triage)
            db.commit()
            db.refresh(triage)

        # Função auxiliar para executar análise com LangGraph
        async def run_langgraph_analysis():
            """Executar análise usando LangGraph"""
            try:
                from .langgraph_agents import get_graph

                # Criar estado inicial para LangGraph
                initial_state = {
                    'patient_data': {
                        'age': triage_data.age,
                        'weight': triage_data.weight,
                        'conditions': triage_data.cid_codes,
                        'current_medications': triage_data.meds_in_use,
                        'allergies': triage_data.allergies,
                        'renal_function': triage_data.renal_function,
                        'hepatic_function': triage_data.hepatic_function,
                        'pregnant': triage_data.pregnant,
                    },
                    'medication_text': ', '.join(triage_data.meds_in_use) if triage_data.meds_in_use else "unknown",
                    'session_id': session_id,
                    'triage_id': str(triage.id),
                }

                logger.info(f"🚀 Iniciando análise LangGraph para triagem {triage.id}")

                # Obter graph e executar
                graph = get_graph()
                config = {"configurable": {"thread_id": session_id}}

                result = await graph.ainvoke(initial_state, config)

                logger.info(f"✅ Análise LangGraph concluída para triagem {triage.id}")

                # Atualizar status da triagem
                with get_db_context() as db:
                    db_triage = db.query(Triage).filter(Triage.id == triage.id).first()
                    if db_triage:
                        db_triage.status = "completed"
                        db.commit()

            except Exception as e:
                logger.error(f"❌ Erro na análise LangGraph: {e}", exc_info=True)
                # Atualizar status para error
                with get_db_context() as db:
                    db_triage = db.query(Triage).filter(Triage.id == triage.id).first()
                    if db_triage:
                        db_triage.status = "error"
                        db.commit()

        # Disparar análise em background usando LangGraph
        background_tasks.add_task(run_langgraph_analysis)

        return TriageResponse(
            id=str(triage.id),
            user_id=triage.user_id,
            status="pending",
            job_id=session_id,
            age=triage.age,
            weight=triage.weight,
            pregnant=triage.pregnant,
            cid_codes=triage.cid_codes,
            meds_in_use=triage.meds_in_use,
            allergies=triage.allergies,
            renal_function=triage.renal_function,
            hepatic_function=triage.hepatic_function,
            notes=triage.notes,
            created_at=triage.created_at
        )

    except Exception as e:
        logger.error(f"Erro ao criar triagem: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.get("/api/v1/triage/{triage_id}/report", response_model=TriageReport)
async def get_triage_report(triage_id: str):
    """Obter relatório de uma triagem"""
    try:
        from .db.database import get_db_context
        with get_db_context() as db:
            report = db.query(Report).filter(Report.triage_id == triage_id).first()

            if not report:
                raise HTTPException(status_code=404, detail="Relatório não encontrado")

            return TriageReport(
                triage_id=str(report.triage_id),
                risk_level=report.risk_level,
                contraindications=report.contraindications,
                interactions=report.interactions,
                dosage_adjustments=report.dosage_adjustments,
                adverse_reactions=report.adverse_reactions,
                evidence_links=report.evidence_links,
                analysis_timestamp=report.created_at.isoformat(),
                model_used=report.model_used,
                confidence_score=report.confidence_score
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter relatório: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.post("/api/v1/vision/analyze", response_model=VisionResponse)
async def analyze_vision(
    file: UploadFile = File(...),
    medication_text: Optional[str] = Form(None)
):
    """
    Analisar imagem/PDF com VisionAgent

    NOTE: VisionAgent AG2 mantido temporariamente até implementação
    do VisionAgent no LangGraph (funcionalidade específica de OCR/visão)
    """
    try:
        from .utils.file_upload import SecureFileUpload
        from .agents.vision import VisionAgent

        # Instanciar VisionAgent diretamente (não usar CaptainAgent)
        vision_agent = VisionAgent()

        # Upload seguro do arquivo
        file_path = await SecureFileUpload.save_upload_file(file)

        # Preparar dados para análise
        image_data = {
            "file_path": str(file_path),
            "medication_text": medication_text,
            "session_id": str(uuid.uuid4())
        }

        # Analisar com VisionAgent
        result = await vision_agent.analyze_document(image_data, image_data["session_id"])

        # Limpar arquivo temporário (mesmo em caso de erro)
        try:
            file_path.unlink()
        except Exception:
            pass

        return VisionResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na análise de visão: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Erro ao processar imagem")


@app.post("/api/v1/ingest/bulas")
async def ingest_bulas(ingest_request: IngestRequest):
    """Ingerir bulas da ANVISA/SIDER/DrugCentral"""
    try:
        # Implementar ingestão
        # Por enquanto, retornar placeholder
        return IngestResponse(
            id=str(uuid.uuid4()),
            source=ingest_request.source,
            data_type=ingest_request.data_type,
            status="pending",
            total_processed=0,
            successful=0,
            failed=0,
            processing_time=0
        )

    except Exception as e:
        logger.error(f"Erro na ingestão: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.get("/api/v1/meds/search")
async def search_medications(
    q: str,
    limit: int = 10,
    include_generic: bool = True,
    include_brands: bool = True
):
    """Busca híbrida de medicamentos (lexical + vetor)"""
    try:
        # Implementar busca híbrida
        # Por enquanto, retornar placeholder
        return MedicationSearchResult(
            query=q,
            total_results=0,
            results=[],
            search_time=0.0
        )

    except Exception as e:
        logger.error(f"Erro na busca: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


# Endpoints de administração
@app.get("/admin/ingest/status")
async def get_ingest_status():
    """Obter status dos jobs de ingestão"""
    try:
        from .db.database import get_db_context
        with get_db_context() as db:
            jobs = db.query(IngestJob).order_by(IngestJob.created_at.desc()).limit(10).all()

            return [
                {
                    "id": str(job.id),
                    "source": job.source,
                    "data_type": job.data_type,
                    "status": job.status,
                    "progress": job.progress,
                    "created_at": job.created_at.isoformat()
                }
                for job in jobs
            ]

    except Exception as e:
        logger.error(f"Erro ao obter status de ingestão: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


# Endpoints de compatibilidade
@app.post("/api/analyze")
async def analyze_medication_legacy(
    patient_data: str = Form(...),
    image: Optional[UploadFile] = File(None),
    medication_text: Optional[str] = Form(None)
):
    """
    Endpoint legado para compatibilidade

    UPDATED: Agora usa o novo sistema LangGraph ao invés do AutoGen/AG2
    """
    start_time = datetime.now()

    try:
        # Log requisição
        log_api_request(
            "POST",
            "/api/analyze",
            medication=medication_text,
            has_image=image is not None
        )

        logger.info("="*80)
        logger.info("📥 Nova requisição de análise (endpoint legado)")
        logger.info(f"   Medicamento: {medication_text}")
        logger.info(f"   Imagem: {'Sim' if image else 'Não'}")
        logger.info("="*80)

        # Converter dados para novo formato
        patient_info = json.loads(patient_data)

        logger.info(f"📋 Dados do paciente:")
        logger.info(f"   Idade: {patient_info.get('age', 'N/A')}")
        logger.info(f"   Peso: {patient_info.get('weight', 'N/A')} kg")
        logger.info(f"   Medicamentos em uso: {len(patient_info.get('meds_in_use', []))}")
        logger.info(f"   Condições: {len(patient_info.get('cid_codes', []))}")

        # Usar LangGraph Multi-Agent System
        from backend.app.langgraph_agents import get_graph

        # Criar estado inicial para LangGraph
        initial_state = {
            'patient_data': {
                'age': patient_info.get("age", 0),
                'weight': patient_info.get("weight"),
                'conditions': patient_info.get("cid_codes", []),
                'current_medications': patient_info.get("meds_in_use", []),
                'allergies': patient_info.get("allergies", []),
            },
            'medication_text': medication_text or "unknown",
            'session_id': str(uuid.uuid4()),
            'triage_id': None,
        }

        logger.info("🚀 Iniciando análise com LangGraph Multi-Agent System...")

        # Obter graph e executar
        graph = get_graph()
        config = {"configurable": {"thread_id": initial_state['session_id']}}

        result = await graph.ainvoke(initial_state, config)

        # Converter resultado para formato legado
        duration = (datetime.now() - start_time).total_seconds()

        logger.info("="*80)
        logger.info(f"✅ Análise concluída em {duration:.2f}s")
        logger.info(f"   Risco: {result.get('risk_level', 'unknown')}")
        logger.info(f"   Interações: {len(result.get('interactions', []))}")
        logger.info(f"   Contraindicações: {len(result.get('contraindications', []))}")
        logger.info(f"   Confiança: {result.get('confidence_score', 0):.2%}")
        logger.info("="*80)

        # Log resposta
        log_api_response(
            "POST",
            "/api/analyze",
            200,
            duration,
            risk_level=result.get('risk_level', 'unknown')
        )

        # Formatar resposta no formato legado
        legacy_response = {
            "session_id": result.get('session_id'),
            "risk_level": result.get('risk_level', 'unknown').value if hasattr(result.get('risk_level'), 'value') else str(result.get('risk_level', 'low')),
            "confidence_score": result.get('confidence_score', 0.0),
            "interactions": result.get('interactions', []),
            "contraindications": result.get('contraindications', []),
            "dosage_adjustments": result.get('dosage_adjustments', []),
            "adverse_reactions": result.get('adverse_reactions', []),
            "evidence_links": result.get('evidence_links', []),
            "final_report": result.get('final_report', {}),
            "status": result.get('status', 'completed'),
            "requires_human_review": result.get('requires_human_review', False),
            "escalation_reasons": result.get('escalation_reasons', []),
        }

        return legacy_response

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ Erro na análise: {e}", exc_info=True)

        log_api_response(
            "POST",
            "/api/analyze",
            500,
            duration,
            error=str(e)
        )

        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


# Montar arquivos estáticos
from pathlib import Path

# Obter diretório raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIR = BASE_DIR / "frontend"

# Criar diretórios se não existirem
STATIC_DIR.mkdir(exist_ok=True)
FRONTEND_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=9000,
        reload=settings.debug
    )
