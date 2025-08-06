"""
Serviço para consulta de informações de medicamentos
"""

import sqlite3
import json
from typing import List, Dict, Optional, Any
from models.database import get_db_connection
from models.schemas import MedicationInfo, Contraindication, DrugInteraction, RiskLevel

class DrugService:
    """Serviço para busca e análise de informações de medicamentos"""
    
    def __init__(self):
        self.known_alternatives = self._load_medication_alternatives()
    
    def _load_medication_alternatives(self) -> Dict[str, List[str]]:
        """Carregar nomes alternativos/comerciais de medicamentos"""
        return {
            "dipirona": ["novalgina", "metamizol", "anador", "dorflex"],
            "paracetamol": ["tylenol", "acetaminofeno", "parador"],
            "ibuprofeno": ["advil", "alivium", "ibuprofeno"],
            "diclofenaco": ["voltaren", "cataflan", "biofenac"],
            "omeprazol": ["losec", "peprazol", "omeprazol"],
            "amoxicilina": ["amoxil", "novamox", "amoxicilina"],
            "azitromicina": ["azalid", "zitromax", "azitromicina"]
        }
    
    async def get_medication_info(self, medication_name: str) -> MedicationInfo:
        """Buscar informações completas do medicamento"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Normalizar nome para busca
            normalized_name = self._normalize_medication_name(medication_name)
            
            # Buscar no banco de dados
            cursor.execute("""
                SELECT * FROM medications 
                WHERE LOWER(name) LIKE ? OR LOWER(active_ingredient) LIKE ?
            """, (f"%{normalized_name}%", f"%{normalized_name}%"))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return MedicationInfo(
                    name=result["name"],
                    active_ingredient=result["active_ingredient"],
                    therapeutic_class=result["therapeutic_class"],
                    anvisa_registry=result["anvisa_registry"]
                )
            else:
                # Se não encontrar, tentar buscar por alternativas
                active_ingredient = self._find_active_ingredient(normalized_name)
                return MedicationInfo(
                    name=medication_name.title(),
                    active_ingredient=active_ingredient or medication_name.lower(),
                    therapeutic_class="Não classificado",
                    anvisa_registry=None
                )
                
        except Exception as e:
            print(f"Erro ao buscar medicamento: {e}")
            return MedicationInfo(
                name=medication_name.title(),
                active_ingredient=medication_name.lower(),
                therapeutic_class="Erro na consulta"
            )
    
    async def search_medications(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """Buscar medicamentos por nome parcial"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            normalized_query = query.lower().strip()
            
            cursor.execute("""
                SELECT name, active_ingredient, therapeutic_class 
                FROM medications 
                WHERE LOWER(name) LIKE ? OR LOWER(active_ingredient) LIKE ?
                LIMIT ?
            """, (f"%{normalized_query}%", f"%{normalized_query}%", limit))
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "name": result["name"],
                    "active_ingredient": result["active_ingredient"],
                    "therapeutic_class": result["therapeutic_class"]
                }
                for result in results
            ]
            
        except Exception as e:
            print(f"Erro na busca: {e}")
            return []
    
    async def get_contraindications(self, medication: str, patient_conditions: List[str]) -> List[Contraindication]:
        """Buscar contraindicações específicas para as condições do paciente"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            contraindications = []
            
            # Buscar contraindicações diretas
            for condition in patient_conditions:
                cursor.execute("""
                    SELECT * FROM contraindications 
                    WHERE LOWER(medication) LIKE ? AND LOWER(condition_type) LIKE ?
                """, (f"%{medication.lower()}%", f"%{condition.lower()}%"))
                
                results = cursor.fetchall()
                for result in results:
                    risk_level = self._map_severity_to_risk(result["severity"])
                    contraindications.append(
                        Contraindication(
                            type=result["condition_type"],
                            description=result["description"],
                            risk_level=risk_level,
                            source=result["source"],
                            recommendation=result["recommendation"]
                        )
                    )
            
            # Buscar contraindicações gerais do medicamento
            cursor.execute("""
                SELECT contraindications FROM medications 
                WHERE LOWER(name) LIKE ? OR LOWER(active_ingredient) LIKE ?
            """, (f"%{medication.lower()}%", f"%{medication.lower()}%"))
            
            result = cursor.fetchone()
            if result and result["contraindications"]:
                general_contraindications = json.loads(result["contraindications"])
                for contraind in general_contraindications:
                    # Verificar se alguma condição do paciente está nas contraindicações
                    if any(condition.lower() in contraind.lower() for condition in patient_conditions):
                        contraindications.append(
                            Contraindication(
                                type="Condição pré-existente",
                                description=contraind,
                                risk_level=RiskLevel.HIGH,
                                source="ANVISA",
                                recommendation="Avaliar risco/benefício com médico"
                            )
                        )
            
            conn.close()
            return contraindications
            
        except Exception as e:
            print(f"Erro ao buscar contraindicações: {e}")
            return []
    
    async def get_drug_interactions(self, medication: str, current_medications: List[str]) -> List[DrugInteraction]:
        """Buscar interações com medicamentos atuais"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            interactions = []
            
            for current_med in current_medications:
                # Buscar interações bidirecionais
                cursor.execute("""
                    SELECT * FROM drug_interactions 
                    WHERE (LOWER(drug_a) LIKE ? AND LOWER(drug_b) LIKE ?) 
                    OR (LOWER(drug_a) LIKE ? AND LOWER(drug_b) LIKE ?)
                """, (
                    f"%{medication.lower()}%", f"%{current_med.lower()}%",
                    f"%{current_med.lower()}%", f"%{medication.lower()}%"
                ))
                
                results = cursor.fetchall()
                for result in results:
                    risk_level = self._map_severity_to_risk(result["severity"])
                    interactions.append(
                        DrugInteraction(
                            interacting_drug=current_med,
                            interaction_type=result["interaction_type"],
                            effect=result["clinical_effect"],
                            risk_level=risk_level,
                            mechanism=result["mechanism"],
                            recommendation=result["recommendation"]
                        )
                    )
            
            conn.close()
            return interactions
            
        except Exception as e:
            print(f"Erro ao buscar interações: {e}")
            return []
    
    def _normalize_medication_name(self, name: str) -> str:
        """Normalizar nome do medicamento para busca"""
        normalized = name.lower().strip()
        
        # Remover sufixos comuns
        suffixes = [" mg", " comprimido", " cápsula", " solução", " xarope"]
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
        
        return normalized
    
    def _find_active_ingredient(self, medication_name: str) -> Optional[str]:
        """Encontrar princípio ativo por nome comercial"""
        for active, alternatives in self.known_alternatives.items():
            if medication_name.lower() in [alt.lower() for alt in alternatives]:
                return active
        return None
    
    def _map_severity_to_risk(self, severity: str) -> RiskLevel:
        """Mapear severidade para nível de risco"""
        severity_map = {
            "baixa": RiskLevel.LOW,
            "leve": RiskLevel.LOW,
            "moderada": RiskLevel.MEDIUM,
            "média": RiskLevel.MEDIUM,
            "alta": RiskLevel.HIGH,
            "grave": RiskLevel.HIGH,
            "crítica": RiskLevel.CRITICAL,
            "absoluta": RiskLevel.CRITICAL
        }
        
        return severity_map.get(severity.lower(), RiskLevel.MEDIUM)
    
    async def get_medication_by_therapeutic_class(self, therapeutic_class: str) -> List[MedicationInfo]:
        """Buscar medicamentos por classe terapêutica"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM medications 
                WHERE LOWER(therapeutic_class) LIKE ?
            """, (f"%{therapeutic_class.lower()}%",))
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                MedicationInfo(
                    name=result["name"],
                    active_ingredient=result["active_ingredient"],
                    therapeutic_class=result["therapeutic_class"],
                    anvisa_registry=result["anvisa_registry"]
                )
                for result in results
            ]
            
        except Exception as e:
            print(f"Erro na busca por classe: {e}")
            return []