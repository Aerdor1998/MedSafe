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
from .agents import CaptainAgent
from .schemas import (
    TriageCreate, TriageResponse, TriageReport,
    VisionRequest, VisionResponse,
    ReportCreate, ReportResponse,
    MedicationSearch, MedicationSearchResult,
    IngestRequest, IngestResponse
)

# Configurar logging
import logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


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

# Inicializar agentes
captain_agent = CaptainAgent()


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


# Endpoints de saúde e monitoramento
@app.get("/healthz")
async def health_check():
    """Verificar saúde da API"""
    try:
        db_healthy = check_db_health()

        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "version": settings.app_version,
            "services": {
                "database": "ok" if db_healthy else "error",
                "ollama": "ok",  # Placeholder
                "api": "ok"
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/metrics")
async def metrics():
    """Métricas Prometheus da aplicação"""
    try:
        db_stats = get_db_stats()

        return {
            "medsafe_requests_total": 0,  # Implementar contador
            "medsafe_analysis_duration_seconds": 0,  # Implementar métrica
            "medsafe_database_size_bytes": 0,  # Implementar métrica
            "medsafe_embeddings_total": db_stats.get("embeddings_count", 0),
            "medsafe_documents_total": db_stats.get("documents_count", 0),
            "medsafe_triage_total": db_stats.get("triage_count", 0),
            "medsafe_reports_total": db_stats.get("reports_count", 0)
        }
    except Exception as e:
        logger.error(f"Erro ao obter métricas: {e}")
        return {}


# Endpoints principais da API
@app.post("/api/v1/triage", response_model=TriageResponse)
async def create_triage(
    triage_data: TriageCreate,
    background_tasks: BackgroundTasks
):
    """Criar triagem e disparar análise assíncrona"""
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

        # Disparar análise em background
        background_tasks.add_task(
            captain_agent.orchestrate_analysis,
            triage_data.model_dump(),
            None
        )

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
    """Analisar imagem/PDF com VisionAgent"""
    try:
        from .utils.file_upload import SecureFileUpload

        # Upload seguro do arquivo
        file_path = await SecureFileUpload.save_upload_file(file)

        # Preparar dados para análise
        image_data = {
            "file_path": str(file_path),
            "medication_text": medication_text,
            "session_id": str(uuid.uuid4())
        }

        # Analisar com VisionAgent
        result = await captain_agent.vision_agent.analyze_document(image_data, image_data["session_id"])

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


# Endpoints de compatibilidade (manter estrutura existente)
@app.post("/api/analyze")
async def analyze_medication_legacy(
    patient_data: str = Form(...),
    image: Optional[UploadFile] = File(None),
    medication_text: Optional[str] = Form(None)
):
    """Endpoint legado para compatibilidade"""
    try:
        # Converter dados para novo formato
        patient_info = json.loads(patient_data)

        # Criar triagem
        triage_data = TriageCreate(
            age=patient_info.get("age", 0),
            weight=patient_info.get("weight"),
            pregnant=patient_info.get("pregnant", False),
            cid_codes=patient_info.get("cid_codes", []),
            meds_in_use=patient_info.get("meds_in_use", []),
            allergies=patient_info.get("allergies", []),
            renal_function=patient_info.get("renal_function"),
            hepatic_function=patient_info.get("hepatic_function"),
            notes=patient_info.get("notes")
        )

        # Processar imagem se disponível
        image_data = None
        if image:
            image_data = {
                "file_type": "image",
                "file_size": image.size,
                "session_id": str(uuid.uuid4()),
                "medication_text": medication_text  # Passar medicamento da requisição
            }
        elif medication_text:
            # Se não há imagem mas há medication_text, criar image_data só para passar o medication
            image_data = {
                "drug_name": medication_text,
                "medication_text": medication_text,
                "session_id": str(uuid.uuid4())
            }

        # Orquestrar análise
        result = await captain_agent.orchestrate_analysis(
            triage_data.model_dump(),
            image_data
        )

        return result

    except Exception as e:
        logger.error(f"Erro na análise legada: {e}")
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
        port=8000,
        reload=settings.debug
    )
