#!/usr/bin/env python3
"""
Script para ingestão de bulas da ANVISA
Uso: python ingest_anvisa.py --query "dipirona" --max 20
"""

import argparse
import asyncio
import logging
import json
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys
import os

# Adicionar backend ao path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../backend'))

from app.config import settings
from app.db.database import get_db_context
from app.db.models import Document, IngestJob

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ANVISAIngester:
    """Ingestor de dados da ANVISA"""
    
    def __init__(self):
        """Inicializar ingestor"""
        self.base_url = "https://consultas.anvisa.gov.br"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MedSafe/1.0 (https://github.com/medsafe)'
        })
    
    async def search_medications(
        self, 
        query: str, 
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Buscar medicamentos na ANVISA
        
        Args:
            query: Termo de busca
            max_results: Máximo de resultados
            
        Returns:
            Lista de medicamentos encontrados
        """
        try:
            logger.info(f"🔍 Buscando medicamentos: {query}")
            
            # Endpoint de busca da ANVISA
            search_url = f"{self.base_url}/#/medicamentos/25331320000169911"
            
            # Parâmetros de busca
            params = {
                'q': query,
                'limit': max_results,
                'offset': 0
            }
            
            # Fazer requisição
            response = self.session.get(search_url, params=params)
            response.raise_for_status()
            
            # Processar resposta (implementar parsing específico da ANVISA)
            medications = self._parse_search_results(response.text, max_results)
            
            logger.info(f"✅ {len(medications)} medicamentos encontrados")
            return medications
            
        except Exception as e:
            logger.error(f"❌ Erro na busca: {e}")
            return []
    
    def _parse_search_results(
        self, 
        html_content: str, 
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Fazer parse dos resultados de busca HTML
        
        Args:
            html_content: Conteúdo HTML da resposta
            max_results: Máximo de resultados
            
        Returns:
            Lista de medicamentos estruturados
        """
        # Implementar parsing específico da ANVISA
        # Por enquanto, retornar estrutura básica
        medications = []
        
        # TODO: Implementar parsing real do HTML da ANVISA
        # Usar BeautifulSoup ou similar para extrair dados
        
        logger.warning("⚠️  Parsing de resultados não implementado completamente")
        
        return medications[:max_results]
    
    async def get_medication_details(
        self, 
        medication_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Obter detalhes completos de um medicamento
        
        Args:
            medication_id: ID do medicamento na ANVISA
            
        Returns:
            Detalhes do medicamento ou None
        """
        try:
            # Endpoint para detalhes do medicamento
            detail_url = f"{self.base_url}/#/medicamentos/{medication_id}"
            
            response = self.session.get(detail_url)
            response.raise_for_status()
            
            # Processar detalhes
            details = self._parse_medication_details(response.text)
            
            return details
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter detalhes: {e}")
            return None
    
    def _parse_medication_details(self, html_content: str) -> Dict[str, Any]:
        """
        Fazer parse dos detalhes do medicamento
        
        Args:
            html_content: Conteúdo HTML dos detalhes
            
        Returns:
            Detalhes estruturados
        """
        # TODO: Implementar parsing real dos detalhes
        return {
            "id": "placeholder",
            "name": "Medicamento Placeholder",
            "active_ingredient": "Ingrediente Ativo",
            "manufacturer": "Fabricante",
            "registration": "Registro ANVISA",
            "status": "Ativo"
        }
    
    async def download_bula(
        self, 
        medication_id: str
    ) -> Optional[str]:
        """
        Baixar bula de um medicamento
        
        Args:
            medication_id: ID do medicamento
            
        Returns:
            Conteúdo da bula ou None
        """
        try:
            # Endpoint para download da bula
            bula_url = f"{self.base_url}/#/medicamentos/{medication_id}/bula"
            
            response = self.session.get(bula_url)
            response.raise_for_status()
            
            # Processar bula
            bula_content = self._parse_bula_content(response.text)
            
            return bula_content
            
        except Exception as e:
            logger.error(f"❌ Erro ao baixar bula: {e}")
            return None
    
    def _parse_bula_content(self, html_content: str) -> str:
        """
        Fazer parse do conteúdo da bula
        
        Args:
            html_content: Conteúdo HTML da bula
            
        Returns:
            Texto da bula limpo
        """
        # TODO: Implementar parsing real da bula
        # Extrair seções: contraindicações, advertências, posologia, interações
        
        return "Conteúdo da bula (parsing não implementado completamente)"
    
    async def ingest_medications(
        self, 
        query: str, 
        max_results: int = 20
    ) -> Dict[str, Any]:
        """
        Ingerir medicamentos da ANVISA
        
        Args:
            query: Termo de busca
            max_results: Máximo de resultados
            
        Returns:
            Resumo da ingestão
        """
        try:
            start_time = datetime.now()
            logger.info(f"🚀 Iniciando ingestão ANVISA: {query}")
            
            # Criar job de ingestão
            ingest_job = await self._create_ingest_job(query, max_results)
            
            # Buscar medicamentos
            medications = await self.search_medications(query, max_results)
            
            if not medications:
                logger.warning("⚠️  Nenhum medicamento encontrado")
                return {
                    "status": "completed",
                    "total_processed": 0,
                    "successful": 0,
                    "failed": 0,
                    "processing_time": 0
                }
            
            # Processar cada medicamento
            successful = 0
            failed = 0
            processed_items = []
            
            for i, med in enumerate(medications):
                try:
                    logger.info(f"📥 Processando {i+1}/{len(medications)}: {med.get('name', 'N/A')}")
                    
                    # Obter detalhes
                    details = await self.get_medication_details(med.get('id', ''))
                    
                    if details:
                        # Baixar bula
                        bula_content = await self.download_bula(med.get('id', ''))
                        
                        if bula_content:
                            # Salvar no banco
                            await self._save_medication_data(details, bula_content)
                            successful += 1
                            
                            processed_items.append({
                                "medication_id": med.get('id'),
                                "name": med.get('name'),
                                "status": "success"
                            })
                        else:
                            failed += 1
                            processed_items.append({
                                "medication_id": med.get('id'),
                                "name": med.get('name'),
                                "status": "failed",
                                "error": "Bula não encontrada"
                            })
                    else:
                        failed += 1
                        processed_items.append({
                            "medication_id": med.get('id'),
                            "name": med.get('name'),
                            "status": "failed",
                            "error": "Detalhes não encontrados"
                        })
                    
                    # Atualizar progresso
                    progress = ((i + 1) / len(medications)) * 100
                    await self._update_ingest_job(ingest_job.id, progress, successful, failed)
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao processar medicamento: {e}")
                    failed += 1
                    processed_items.append({
                        "medication_id": med.get('id'),
                        "name": med.get('name'),
                        "status": "failed",
                        "error": str(e)
                    })
            
            # Finalizar job
            processing_time = (datetime.now() - start_time).total_seconds()
            await self._finalize_ingest_job(
                ingest_job.id, 
                "completed", 
                len(medications), 
                successful, 
                failed, 
                processing_time,
                processed_items
            )
            
            logger.info(f"✅ Ingestão concluída: {successful} sucessos, {failed} falhas")
            
            return {
                "status": "completed",
                "total_processed": len(medications),
                "successful": successful,
                "failed": failed,
                "processing_time": processing_time,
                "processed_items": processed_items
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na ingestão: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "total_processed": 0,
                "successful": 0,
                "failed": 0,
                "processing_time": 0
            }
    
    async def _create_ingest_job(
        self, 
        query: str, 
        max_results: int
    ) -> IngestJob:
        """Criar job de ingestão no banco"""
        try:
            with get_db_context() as db:
                job = IngestJob(
                    source="ANVISA",
                    data_type="bulas",
                    query=query,
                    max_results=max_results,
                    status="running",
                    progress=0.0,
                    current_step="Iniciando busca"
                )
                
                db.add(job)
                db.commit()
                db.refresh(job)
                
                return job
                
        except Exception as e:
            logger.error(f"❌ Erro ao criar job: {e}")
            raise
    
    async def _update_ingest_job(
        self, 
        job_id: str, 
        progress: float, 
        successful: int, 
        failed: int
    ):
        """Atualizar progresso do job"""
        try:
            with get_db_context() as db:
                job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
                if job:
                    job.progress = progress
                    job.successful = successful
                    job.failed = failed
                    job.current_step = f"Processados: {successful + failed}"
                    db.commit()
                    
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar job: {e}")
    
    async def _finalize_ingest_job(
        self, 
        job_id: str, 
        status: str, 
        total: int, 
        successful: int, 
        failed: int, 
        processing_time: float,
        processed_items: List[Dict[str, Any]]
    ):
        """Finalizar job de ingestão"""
        try:
            with get_db_context() as db:
                job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
                if job:
                    job.status = status
                    job.progress = 100.0
                    job.total_processed = total
                    job.successful = successful
                    job.failed = failed
                    job.processing_time = processing_time
                    job.processed_items = processed_items
                    job.current_step = "Concluído"
                    db.commit()
                    
        except Exception as e:
            logger.error(f"❌ Erro ao finalizar job: {e}")
    
    async def _save_medication_data(
        self, 
        details: Dict[str, Any], 
        bula_content: str
    ):
        """Salvar dados do medicamento no banco"""
        try:
            with get_db_context() as db:
                # Salvar documento principal
                document = Document(
                    source="ANVISA",
                    source_url=f"https://consultas.anvisa.gov.br/#/medicamentos/{details.get('id')}",
                    drug_name=details.get('name', ''),
                    section="bula_completa",
                    text=bula_content,
                    meta={
                        "active_ingredient": details.get('active_ingredient'),
                        "manufacturer": details.get('manufacturer'),
                        "registration": details.get('registration'),
                        "status": details.get('status')
                    }
                )
                
                db.add(document)
                db.commit()
                
                logger.info(f"💾 Medicamento salvo: {details.get('name')}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao salvar medicamento: {e}")
            raise


async def main():
    """Função principal"""
    parser = argparse.ArgumentParser(description="Ingestor de dados da ANVISA")
    parser.add_argument("--query", required=True, help="Termo de busca")
    parser.add_argument("--max", type=int, default=20, help="Máximo de resultados")
    parser.add_argument("--verbose", "-v", action="store_true", help="Log detalhado")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Inicializar ingestor
    ingestor = ANVISAIngester()
    
    # Executar ingestão
    result = await ingestor.ingest_medications(args.query, args.max)
    
    # Exibir resultado
    print(json.dumps(result, indent=2, default=str))
    
    if result.get("status") == "completed":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

