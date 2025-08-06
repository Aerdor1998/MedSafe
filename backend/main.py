"""
MedSafe - Sistema de Contra-indicativos de Medicamentos
API Principal com FastAPI
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
import json
import sqlite3
from datetime import datetime
import uuid

from models.database import init_db, get_db_connection
from services.ocr_service import OCRService
from services.drug_service import DrugService
from services.ai_service import AIService
from services.logging_service import LoggingService
from services.vision_service import VisionService
from models.schemas import PatientData, MedicationRequest, AnalysisResult

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializar banco de dados e serviços na inicialização."""
    init_db()
    print("✅ MedSafe API iniciada com sucesso!")
    yield
    # Código para executar no desligamento pode ser adicionado aqui
    print("✅ MedSafe API encerrada.")

# Configuração da aplicação
app = FastAPI(
    title="MedSafe API",
    description="Sistema de Contra-indicativos de Medicamentos baseado em diretrizes OMS/ANVISA",
    version="1.0.0",
    lifespan=lifespan
)

# CORS para desenvolvimento e produção
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Adicionar origem de produção a partir de variáveis de ambiente
PRODUCTION_ORIGIN = os.getenv("CORS_ORIGIN")
if PRODUCTION_ORIGIN:
    origins.append(PRODUCTION_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Inicializar serviços
ocr_service = OCRService()
drug_service = DrugService()
ai_service = AIService()
vision_service = VisionService()
logging_service = LoggingService()





@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_medication(
    patient_data: str = Form(...),
    image: Optional[UploadFile] = File(None),
    medication_text: Optional[str] = Form(None)
):
    """
    Endpoint principal para análise de medicamentos
    """
    try:
        # Gerar ID da sessão
        session_id = str(uuid.uuid4())
        
        # Parse dos dados do paciente
        patient_info = json.loads(patient_data)
        patient = PatientData(**patient_info)
        
        # Log inicial
        await logging_service.log_session_start(session_id, patient.model_dump())
        
        # Identificar medicamento
        medication_name = None
        if image:
            # OCR na imagem
            image_path = await save_upload_file(image, session_id)
            medication_name = await ocr_service.extract_medication(image_path)
            
        if medication_text:
            medication_name = medication_text
            
        if not medication_name:
            raise HTTPException(status_code=400, detail="Medicamento não identificado")
        
        # Buscar informações do medicamento
        medication_info = await drug_service.get_medication_info(medication_name)
        
        # Análise com IA (AG2/Ollama)
        analysis = await ai_service.analyze_contraindications(
            patient=patient,
            medication=medication_info,
            session_id=session_id
        )
        
        # Log do resultado
        await logging_service.log_analysis_result(session_id, analysis)
        
        return analysis
        
    except Exception as e:
        await logging_service.log_error(session_id, str(e))
        raise HTTPException(status_code=500, detail=f"Erro na análise: {str(e)}")

@app.post("/api/upload-image")
async def upload_medication_image(file: UploadFile = File(...)):
    """Upload e OCR de imagem de medicamento"""
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Arquivo deve ser uma imagem")
        
        session_id = str(uuid.uuid4())
        image_path = await save_upload_file(file, session_id)
        
        # Extrair texto da imagem
        extracted_text = await ocr_service.extract_text(image_path)
        medication_name = await ocr_service.extract_medication(image_path)
        
        return {
            "session_id": session_id,
            "extracted_text": extracted_text,
            "medication_name": medication_name,
            "image_path": image_path
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no upload: {str(e)}")

@app.get("/api/medications/search")
async def search_medications(q: str):
    """Buscar medicamentos por nome"""
    try:
        results = await drug_service.search_medications(q)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na busca: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Verificar saúde da API"""
    
    # Verificar Ollama
    ollama_status = "ok"
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            ollama_status = "offline"
    except:
        ollama_status = "offline"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "ok",
            "ocr": "ok", 
            "ai": "ok",
            "vision": "ok",
            "ollama": ollama_status
        },
        "models": {
            "text_model": os.getenv("OLLAMA_TEXT_MODEL", "qwen3:4b"),
            "vision_model": os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
        }
    }

async def save_upload_file(file: UploadFile, session_id: str) -> str:
    """Salvar arquivo carregado"""
    os.makedirs("../static/uploads", exist_ok=True)
    
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
    file_path = f"../static/uploads/{filename}"
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    return file_path


# Montar arquivos estáticos no final para não sobrescrever rotas da API
app.mount("/static", StaticFiles(directory="../static"), name="static")
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)