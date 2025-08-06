"""
Serviço de logging para auditoria de farmacovigilância
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from models.database import log_session, log_event
from models.schemas import PatientData, AnalysisResult

class LoggingService:
    """Serviço para logging e auditoria de farmacovigilância"""
    
    def __init__(self):
        self.log_dir = "../logs"
        os.makedirs(self.log_dir, exist_ok=True)
    
    async def log_session_start(self, session_id: str, patient_data: Dict[str, Any], ip_address: str = None):
        """Registrar início de sessão"""
        try:
            # Log no banco de dados
            log_event(
                session_id=session_id,
                event_type="session_start",
                event_data={
                    "patient_age": patient_data.get("age"),
                    "patient_gender": patient_data.get("gender"),
                    "conditions_count": len(patient_data.get("conditions", [])),
                    "medications_count": len(patient_data.get("current_medications", [])),
                    "has_allergies": len(patient_data.get("allergies", [])) > 0
                },
                ip_address=ip_address
            )
            
            # Log em arquivo
            await self._write_file_log("session_start", {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "event": "session_start",
                "data": patient_data
            })
            
        except Exception as e:
            print(f"Erro no log de início de sessão: {e}")
    
    async def log_ocr_result(self, session_id: str, image_path: str, extracted_text: str, medication_name: str = None):
        """Registrar resultado do OCR"""
        try:
            log_event(
                session_id=session_id,
                event_type="ocr_processing",
                event_data={
                    "image_path": os.path.basename(image_path),
                    "text_length": len(extracted_text),
                    "medication_identified": medication_name is not None,
                    "medication_name": medication_name
                }
            )
            
            await self._write_file_log("ocr_result", {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "image_path": image_path,
                "extracted_text": extracted_text,
                "medication_name": medication_name
            })
            
        except Exception as e:
            print(f"Erro no log de OCR: {e}")
    
    async def log_analysis_result(self, session_id: str, analysis: AnalysisResult):
        """Registrar resultado da análise"""
        try:
            # Dados anonimizados para o banco
            analysis_summary = {
                "overall_risk": analysis.overall_risk.value,
                "contraindications_count": len(analysis.contraindications),
                "interactions_count": len(analysis.drug_interactions),
                "adverse_reactions_count": len(analysis.adverse_reactions),
                "medication_name": analysis.medication.name,
                "active_ingredient": analysis.medication.active_ingredient
            }
            
            log_session(
                session_id=session_id,
                patient_data=analysis.patient.model_dump(),
                medication_name=analysis.medication.name,
                analysis_result=analysis_summary,
                risk_level=analysis.overall_risk.value
            )
            
            log_event(
                session_id=session_id,
                event_type="analysis_complete",
                event_data=analysis_summary
            )
            
            # Log detalhado em arquivo (para auditoria técnica)
            await self._write_file_log("analysis_result", {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "analysis": analysis.model_dump()
            })
            
        except Exception as e:
            print(f"Erro no log de análise: {e}")
    
    async def log_error(self, session_id: str, error_message: str, error_type: str = "general"):
        """Registrar erro"""
        try:
            log_event(
                session_id=session_id,
                event_type="error",
                event_data={
                    "error_type": error_type,
                    "error_message": error_message,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            await self._write_file_log("error", {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "error_type": error_type,
                "error_message": error_message
            })
            
        except Exception as e:
            print(f"Erro no log de erro: {e}")
    
    async def log_user_action(self, session_id: str, action: str, details: Dict[str, Any] = None):
        """Registrar ação do usuário"""
        try:
            log_event(
                session_id=session_id,
                event_type="user_action",
                event_data={
                    "action": action,
                    "details": details or {},
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            print(f"Erro no log de ação do usuário: {e}")
    
    async def _write_file_log(self, log_type: str, data: Dict[str, Any]):
        """Escrever log em arquivo"""
        try:
            # Criar nome do arquivo baseado na data
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"{log_type}_{date_str}.jsonl"
            filepath = os.path.join(self.log_dir, filename)
            
            # Escrever linha JSON
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
                
        except Exception as e:
            print(f"Erro ao escrever log em arquivo: {e}")
    
    async def get_session_logs(self, session_id: str) -> Dict[str, Any]:
        """Obter logs de uma sessão específica"""
        try:
            from models.database import get_db_connection
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Buscar sessão principal
            cursor.execute("""
                SELECT * FROM sessions WHERE id = ?
            """, (session_id,))
            session = cursor.fetchone()
            
            # Buscar eventos da sessão
            cursor.execute("""
                SELECT * FROM audit_logs WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))
            events = cursor.fetchall()
            
            conn.close()
            
            return {
                "session": dict(session) if session else None,
                "events": [dict(event) for event in events]
            }
            
        except Exception as e:
            print(f"Erro ao buscar logs da sessão: {e}")
            return {"session": None, "events": []}
    
    async def generate_audit_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Gerar relatório de auditoria para período"""
        try:
            from models.database import get_db_connection
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Estatísticas gerais
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(CASE WHEN risk_level = 'critico' THEN 1 END) as critical_risk,
                    COUNT(CASE WHEN risk_level = 'alto' THEN 1 END) as high_risk,
                    COUNT(CASE WHEN risk_level = 'medio' THEN 1 END) as medium_risk,
                    COUNT(CASE WHEN risk_level = 'baixo' THEN 1 END) as low_risk
                FROM sessions 
                WHERE timestamp BETWEEN ? AND ?
            """, (start_date, end_date))
            
            stats = cursor.fetchone()
            
            # Top medicamentos analisados
            cursor.execute("""
                SELECT medication_name, COUNT(*) as count
                FROM sessions 
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY medication_name
                ORDER BY count DESC
                LIMIT 10
            """, (start_date, end_date))
            
            top_medications = cursor.fetchall()
            
            # Eventos por tipo
            cursor.execute("""
                SELECT event_type, COUNT(*) as count
                FROM audit_logs 
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY event_type
            """, (start_date, end_date))
            
            events_by_type = cursor.fetchall()
            
            conn.close()
            
            return {
                "period": {"start": start_date, "end": end_date},
                "statistics": dict(stats) if stats else {},
                "top_medications": [dict(med) for med in top_medications],
                "events_by_type": [dict(event) for event in events_by_type],
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Erro ao gerar relatório de auditoria: {e}")
            return {}
    
    async def anonymize_old_logs(self, days_old: int = 90):
        """Anonimizar logs antigos para conformidade com LGPD"""
        try:
            from models.database import get_db_connection
            from datetime import timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Anonimizar dados pessoais em sessões antigas
            cursor.execute("""
                UPDATE sessions 
                SET patient_data = '{"anonymized": true}',
                    ip_address = NULL
                WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            # Anonimizar logs de eventos antigos
            cursor.execute("""
                UPDATE audit_logs 
                SET event_data = '{"anonymized": true}',
                    ip_address = NULL
                WHERE timestamp < ?
                AND event_type NOT IN ('analysis_complete', 'error')
            """, (cutoff_date.isoformat(),))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            await self._write_file_log("anonymization", {
                "timestamp": datetime.now().isoformat(),
                "cutoff_date": cutoff_date.isoformat(),
                "rows_affected": rows_affected
            })
            
            return {"rows_anonymized": rows_affected}
            
        except Exception as e:
            print(f"Erro na anonimização: {e}")
            return {"error": str(e)}