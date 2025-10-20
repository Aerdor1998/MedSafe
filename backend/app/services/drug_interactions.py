"""
Serviço para análise de interações medicamentosas
Utiliza base de dados CSV com 191k+ interações
"""

import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache
import re

logger = logging.getLogger(__name__)

class DrugInteractionService:
    """Serviço para buscar e analisar interações medicamentosas"""
    
    # Mapa de nomes comerciais/populares → nomes científicos
    DRUG_SYNONYMS = {
        # Aspirina
        'aspirina': 'acetylsalicylic acid',
        'aspirin': 'acetylsalicylic acid',
        'aas': 'acetylsalicylic acid',
        'ácido acetilsalicílico': 'acetylsalicylic acid',
        
        # Paracetamol/Tylenol
        'paracetamol': 'acetaminophen',
        'tylenol': 'acetaminophen',
        'parac humanoid': 'acetaminophen',
        
        # Metformina
        'metformina': 'metformin',
        'glifage': 'metformin',
        
        # Losartana
        'losartana': 'losartan',
        'losartan potássico': 'losartan',
        'cozaar': 'losartan',
        
        # Ibuprofeno
        'ibuprofeno': 'ibuprofen',
        'advil': 'ibuprofen',
        'motrin': 'ibuprofen',
        
        # Amoxicilina
        'amoxicilina': 'amoxicillin',
        
        # Dipirona
        'dipirona': 'metamizole',
        'novalgina': 'metamizole',
        
        # Omeprazol
        'omeprazol': 'omeprazole',
        
        # Sertralina
        'sertralina': 'sertraline',
        'zoloft': 'sertraline',
        
        # Fluoxetina
        'fluoxetina': 'fluoxetine',
        'prozac': 'fluoxetine',
        
        # Atorvastatina
        'atorvastatina': 'atorvastatin',
        'lipitor': 'atorvastatin',
        
        # Simvastatina
        'simvastatina': 'simvastatin',
        'zocor': 'simvastatin',
        
        # Varfarina
        'varfarina': 'warfarin',
        'coumadin': 'warfarin',
        'marevan': 'warfarin',
        
        # Diazepam
        'diazepam': 'diazepam',
        'valium': 'diazepam',
        
        # Clonazepam
        'clonazepam': 'clonazepam',
        'rivotril': 'clonazepam',
    }
    
    def __init__(self):
        self.db_path = Path(__file__).parent.parent.parent.parent / "data" / "db_drug_interactions.csv"
        self._interactions_cache = None
        logger.info(f"🔍 DrugInteractionService inicializado - Base: {self.db_path}")
    
    @property
    def interactions_db(self):
        """Lazy loading da base de interações"""
        if self._interactions_cache is None:
            self._load_interactions()
        return self._interactions_cache
    
    def _load_interactions(self):
        """Carregar base de dados de interações"""
        try:
            logger.info("📚 Carregando base de interações medicamentosas...")
            
            self._interactions_cache = {}
            
            with open(self.db_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    drug1 = self._normalize_drug_name(row['Drug 1'])
                    drug2 = self._normalize_drug_name(row['Drug 2'])
                    description = row['Interaction Description']
                    
                    # Criar chave bidirecional
                    key1 = f"{drug1}|{drug2}"
                    key2 = f"{drug2}|{drug1}"
                    
                    interaction_data = {
                        'drug1': row['Drug 1'],
                        'drug2': row['Drug 2'],
                        'description': description,
                        'severity': self._classify_severity(description),
                        'category': self._classify_category(description)
                    }
                    
                    self._interactions_cache[key1] = interaction_data
                    self._interactions_cache[key2] = interaction_data
            
            logger.info(f"✅ Base carregada: {len(self._interactions_cache)} interações indexadas")
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar base de interações: {e}")
            self._interactions_cache = {}
    
    def _normalize_drug_name(self, name: str) -> str:
        """
        Normalizar nome do medicamento para busca
        Converte nomes comerciais para nomes científicos
        """
        normalized = name.lower().strip()
        
        # Verificar se há sinônimo mapeado
        if normalized in self.DRUG_SYNONYMS:
            scientific_name = self.DRUG_SYNONYMS[normalized]
            logger.debug(f"   🔄 Mapeando '{name}' → '{scientific_name}'")
            return scientific_name
        
        return normalized
    
    def _classify_severity(self, description: str) -> str:
        """
        Classificar severidade da interação baseado na descrição
        
        Returns:
            'critical', 'high', 'medium', 'low'
        """
        description_lower = description.lower()
        
        # Palavras-chave para severidade crítica
        critical_keywords = [
            'contraindicated', 'contraindication', 'fatal', 'life-threatening',
            'severe', 'serious', 'major', 'cardiotoxic', 'hepatotoxic',
            'nephrotoxic', 'neurotoxic', 'may cause death'
        ]
        
        # Palavras-chave para severidade alta
        high_keywords = [
            'significant', 'increase the risk', 'adverse effects',
            'toxicity', 'dangerous', 'harmful', 'may increase',
            'serum concentration', 'metabolism'
        ]
        
        # Palavras-chave para severidade média
        medium_keywords = [
            'moderate', 'caution', 'monitor', 'may decrease',
            'effectiveness', 'therapeutic effect', 'bioavailability'
        ]
        
        # Verificar severidade
        if any(keyword in description_lower for keyword in critical_keywords):
            return 'critical'
        elif any(keyword in description_lower for keyword in high_keywords):
            return 'high'
        elif any(keyword in description_lower for keyword in medium_keywords):
            return 'medium'
        else:
            return 'low'
    
    def _classify_category(self, description: str) -> str:
        """Classificar categoria da interação"""
        description_lower = description.lower()
        
        if 'cardiotoxic' in description_lower or 'cardiac' in description_lower:
            return 'Cardiovascular'
        elif 'hepatotoxic' in description_lower or 'liver' in description_lower:
            return 'Hepática'
        elif 'nephrotoxic' in description_lower or 'renal' in description_lower or 'kidney' in description_lower:
            return 'Renal'
        elif 'neurotoxic' in description_lower or 'cns' in description_lower or 'sedation' in description_lower:
            return 'Neurológica'
        elif 'photosensitiz' in description_lower:
            return 'Fotossensibilidade'
        elif 'metabolism' in description_lower or 'cyp' in description_lower:
            return 'Farmacocinética'
        elif 'bleeding' in description_lower or 'anticoagulant' in description_lower:
            return 'Coagulação'
        else:
            return 'Farmacológica'
    
    def find_interactions(
        self, 
        drug_name: str, 
        other_drugs: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Buscar interações entre um medicamento e uma lista de outros
        
        Args:
            drug_name: Nome do medicamento principal
            other_drugs: Lista de outros medicamentos em uso
            
        Returns:
            Lista de interações encontradas
        """
        interactions = []
        drug_normalized = self._normalize_drug_name(drug_name)
        
        logger.info(f"🔍 Buscando interações para: {drug_name}")
        logger.info(f"   Outros medicamentos: {other_drugs}")
        
        for other_drug in other_drugs:
            if not other_drug or not other_drug.strip():
                continue
            
            other_normalized = self._normalize_drug_name(other_drug)
            key = f"{drug_normalized}|{other_normalized}"
            
            if key in self.interactions_db:
                interaction = self.interactions_db[key].copy()
                interactions.append(interaction)
                logger.info(f"   ✅ Interação encontrada: {drug_name} + {other_drug} ({interaction['severity']})")
        
        logger.info(f"📊 Total de interações encontradas: {len(interactions)}")
        return interactions
    
    def analyze_contraindications(
        self,
        drug_name: str,
        patient_conditions: List[str],
        allergies: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Analisar contraindicações baseado em condições do paciente
        
        Args:
            drug_name: Nome do medicamento
            patient_conditions: Condições médicas do paciente
            allergies: Alergias conhecidas
            
        Returns:
            Lista de contraindicações identificadas
        """
        contraindications = []
        drug_normalized = self._normalize_drug_name(drug_name)
        
        # Verificar alergias
        for allergy in allergies:
            allergy_normalized = self._normalize_drug_name(allergy)
            if allergy_normalized in drug_normalized or drug_normalized in allergy_normalized:
                contraindications.append({
                    'type': 'Alergia Conhecida',
                    'description': f'Paciente possui alergia conhecida a {allergy}',
                    'severity': 'critical',
                    'source': 'Histórico do Paciente',
                    'recommendation': 'CONTRAINDICADO - Não administrar'
                })
        
        # Contraindicações baseadas em condições comuns
        condition_contraindications = self._get_condition_contraindications(drug_normalized, patient_conditions)
        contraindications.extend(condition_contraindications)
        
        return contraindications
    
    def _get_condition_contraindications(
        self, 
        drug_normalized: str, 
        conditions: List[str]
    ) -> List[Dict[str, Any]]:
        """Contraindicações baseadas em condições médicas"""
        contraindications = []
        
        # Mapa de condições -> medicamentos contraindicados
        condition_drug_map = {
            'gravidez': ['methotrexate', 'isotretinoin', 'warfarin', 'valproic acid'],
            'gestação': ['methotrexate', 'isotretinoin', 'warfarin', 'valproic acid'],
            'pregnant': ['methotrexate', 'isotretinoin', 'warfarin', 'valproic acid'],
            'insuficiência renal': ['metformin', 'nsaid', 'lithium'],
            'renal': ['metformin', 'nsaid', 'lithium'],
            'kidney': ['metformin', 'nsaid', 'lithium'],
            'insuficiência hepática': ['acetaminophen', 'paracetamol', 'statins'],
            'liver': ['acetaminophen', 'paracetamol', 'statins'],
            'hepática': ['acetaminophen', 'paracetamol', 'statins'],
        }
        
        for condition in conditions:
            condition_lower = condition.lower().strip()
            for condition_key, contraindicated_drugs in condition_drug_map.items():
                if condition_key in condition_lower:
                    for contra_drug in contraindicated_drugs:
                        if contra_drug in drug_normalized:
                            contraindications.append({
                                'type': f'Contraindicação por {condition}',
                                'description': f'{contra_drug.capitalize()} pode ser contraindicado em pacientes com {condition}',
                                'severity': 'high',
                                'source': 'Diretrizes Clínicas',
                                'recommendation': 'Avaliar alternativas terapêuticas com médico'
                            })
        
        return contraindications
    
    def calculate_overall_risk(
        self,
        interactions: List[Dict[str, Any]],
        contraindications: List[Dict[str, Any]]
    ) -> str:
        """
        Calcular nível de risco geral
        
        Returns:
            'critical', 'high', 'medium', 'low'
        """
        # Se há contraindicações críticas
        if any(c['severity'] == 'critical' for c in contraindications):
            return 'critical'
        
        # Se há interações críticas
        if any(i['severity'] == 'critical' for i in interactions):
            return 'critical'
        
        # Contar severidades HIGH
        high_count = (
            len([i for i in interactions if i['severity'] == 'high']) +
            len([c for c in contraindications if c['severity'] == 'high'])
        )
        
        # Se há pelo menos 1 interação/contraindicação HIGH → risco HIGH
        if high_count >= 1:
            return 'high'
        
        # Contar severidades MEDIUM
        medium_count = (
            len([i for i in interactions if i['severity'] == 'medium']) +
            len([c for c in contraindications if c['severity'] == 'medium'])
        )
        
        # Se há pelo menos 1 interação/contraindicação MEDIUM → risco MEDIUM
        if medium_count >= 1:
            return 'medium'
        
        # Sem interações significativas → risco LOW
        return 'low'


# Instância global (singleton)
_interaction_service = None

def get_interaction_service() -> DrugInteractionService:
    """Obter instância do serviço de interações"""
    global _interaction_service
    if _interaction_service is None:
        _interaction_service = DrugInteractionService()
    return _interaction_service

