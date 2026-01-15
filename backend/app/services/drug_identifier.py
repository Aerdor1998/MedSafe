"""
Serviço Híbrido de Identificação de Medicamentos

Combina:
1. Regex patterns para identificação rápida e determinística
2. Fuzzy matching para variações ortográficas
3. LLM fallback para casos complexos (nomes comerciais desconhecidos)

SKILLS APLICADAS:
- ULTRATHINK: Abordagem híbrida elegante
- DEBUGGING-STRATEGIES: Logging estruturado para auditoria
- CODE-REVIEW-EXCELLENCE: Documentação clara
"""

import re
import logging
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from difflib import SequenceMatcher
from functools import lru_cache

logger = logging.getLogger(__name__)


class IdentificationMethod(Enum):
    """Método usado para identificar o medicamento"""
    EXACT_MATCH = "exact_match"
    REGEX_PATTERN = "regex_pattern"
    FUZZY_MATCH = "fuzzy_match"
    LLM_INFERENCE = "llm_inference"
    NOT_FOUND = "not_found"


@dataclass
class DrugIdentification:
    """Resultado da identificação de um medicamento"""
    original_name: str
    canonical_name: str
    method: IdentificationMethod
    confidence: float
    alternatives: List[str] = None
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


class HybridDrugIdentifier:
    """
    Identificador híbrido de medicamentos usando múltiplas estratégias
    
    Ordem de prioridade:
    1. Exact match no dicionário de sinônimos
    2. Regex patterns para variações comuns
    3. Fuzzy matching para erros de digitação
    4. LLM inference para casos complexos
    """
    
    # Mapeamento completo de sinônimos (português → inglês científico)
    DRUG_SYNONYMS = {
        # ===== DIURÉTICOS =====
        "espironolactona": "spironolactone",
        "spironolactona": "spironolactone",
        "aldactone": "spironolactone",
        "hidroclorotiazida": "hydrochlorothiazide",
        "hctz": "hydrochlorothiazide",
        "furosemida": "furosemide",
        "lasix": "furosemide",
        
        # ===== ANTI-HIPERTENSIVOS (BRA/IECA) =====
        "losartana": "losartan",
        "losartan": "losartan",
        "cozaar": "losartan",
        "valsartana": "valsartan",
        "diovan": "valsartan",
        "enalapril": "enalapril",
        "renitec": "enalapril",
        "captopril": "captopril",
        "capoten": "captopril",
        "lisinopril": "lisinopril",
        "zestril": "lisinopril",
        "ramipril": "ramipril",
        
        # ===== BETA-BLOQUEADORES =====
        "atenolol": "atenolol",
        "propranolol": "propranolol",
        "metoprolol": "metoprolol",
        "carvedilol": "carvedilol",
        "bisoprolol": "bisoprolol",
        
        # ===== ESTATINAS =====
        "sinvastatina": "simvastatin",
        "simvastatina": "simvastatin",
        "zocor": "simvastatin",
        "atorvastatina": "atorvastatin",
        "lipitor": "atorvastatin",
        "rosuvastatina": "rosuvastatin",
        "crestor": "rosuvastatin",
        
        # ===== ANTICOAGULANTES =====
        "warfarina": "warfarin",
        "varfarina": "warfarin",
        "coumadin": "warfarin",
        "marevan": "warfarin",
        "rivaroxabana": "rivaroxaban",
        "xarelto": "rivaroxaban",
        "apixabana": "apixaban",
        "eliquis": "apixaban",
        "heparina": "heparin",
        
        # ===== ANTIPLAQUETÁRIOS =====
        "aspirina": "acetylsalicylic acid",
        "aas": "acetylsalicylic acid",
        "ácido acetilsalicílico": "acetylsalicylic acid",
        "clopidogrel": "clopidogrel",
        "plavix": "clopidogrel",
        
        # ===== ANALGÉSICOS =====
        "paracetamol": "acetaminophen",
        "tylenol": "acetaminophen",
        "dipirona": "metamizole",
        "novalgina": "metamizole",
        "ibuprofeno": "ibuprofen",
        "advil": "ibuprofen",
        "diclofenaco": "diclofenac",
        "voltaren": "diclofenac",
        "naproxeno": "naproxen",
        "tramadol": "tramadol",
        "tramal": "tramadol",
        "codeina": "codeine",
        "codeína": "codeine",
        "morfina": "morphine",
        
        # ===== ANTIDEPRESSIVOS =====
        "sertralina": "sertraline",
        "zoloft": "sertraline",
        "fluoxetina": "fluoxetine",
        "prozac": "fluoxetine",
        "paroxetina": "paroxetine",
        "paxil": "paroxetine",
        "escitalopram": "escitalopram",
        "lexapro": "escitalopram",
        "venlafaxina": "venlafaxine",
        "effexor": "venlafaxine",
        "duloxetina": "duloxetine",
        "cymbalta": "duloxetine",
        "amitriptilina": "amitriptyline",
        "tryptanol": "amitriptyline",
        "bupropiona": "bupropion",
        "wellbutrin": "bupropion",
        
        # ===== ANSIOLÍTICOS/BENZODIAZEPÍNICOS =====
        "diazepam": "diazepam",
        "valium": "diazepam",
        "clonazepam": "clonazepam",
        "rivotril": "clonazepam",
        "alprazolam": "alprazolam",
        "frontal": "alprazolam",
        "xanax": "alprazolam",
        "lorazepam": "lorazepam",
        "lorax": "lorazepam",
        
        # ===== ANTIDIABÉTICOS =====
        "metformina": "metformin",
        "glifage": "metformin",
        "glibenclamida": "glyburide",
        "daonil": "glyburide",
        "glimepirida": "glimepiride",
        "insulina": "insulin",
        "sitagliptina": "sitagliptin",
        "januvia": "sitagliptin",
        
        # ===== ANTIBIÓTICOS =====
        "amoxicilina": "amoxicillin",
        "azitromicina": "azithromycin",
        "zitromax": "azithromycin",
        "ciprofloxacino": "ciprofloxacin",
        "cipro": "ciprofloxacin",
        "levofloxacino": "levofloxacin",
        "cefalexina": "cephalexin",
        "clindamicina": "clindamycin",
        "metronidazol": "metronidazole",
        "flagyl": "metronidazole",
        
        # ===== GASTROPROTETORES =====
        "omeprazol": "omeprazole",
        "losec": "omeprazole",
        "pantoprazol": "pantoprazole",
        "esomeprazol": "esomeprazole",
        "nexium": "esomeprazole",
        "ranitidina": "ranitidine",
        
        # ===== ANTIPSICÓTICOS =====
        "haloperidol": "haloperidol",
        "haldol": "haloperidol",
        "risperidona": "risperidone",
        "risperdal": "risperidone",
        "quetiapina": "quetiapine",
        "seroquel": "quetiapine",
        "olanzapina": "olanzapine",
        "zyprexa": "olanzapine",
        
        # ===== IMAOs (Alto Risco) =====
        "fenelzina": "phenelzine",
        "nardil": "phenelzine",
        "tranilcipromina": "tranylcypromine",
        "parnate": "tranylcypromine",
        "selegilina": "selegiline",
        
        # ===== ESTIMULANTES =====
        "metilfenidato": "methylphenidate",
        "ritalina": "methylphenidate",
        "concerta": "methylphenidate",
        "lisdexanfetamina": "lisdexamfetamine",
        "venvanse": "lisdexamfetamine",
        
        # ===== ANTICONVULSIVANTES =====
        "carbamazepina": "carbamazepine",
        "tegretol": "carbamazepine",
        "fenitoina": "phenytoin",
        "fenitoína": "phenytoin",
        "valproato": "valproic acid",
        "ácido valpróico": "valproic acid",
        "depakene": "valproic acid",
        "lamotrigina": "lamotrigine",
        "levetiracetam": "levetiracetam",
        "keppra": "levetiracetam",
        "gabapentina": "gabapentin",
        "pregabalina": "pregabalin",
        "lyrica": "pregabalin",
        
        # ===== CORTICOSTEROIDES =====
        "prednisona": "prednisone",
        "prednisolona": "prednisolone",
        "dexametasona": "dexamethasone",
        "hidrocortisona": "hydrocortisone",
        
        # ===== IMUNOSSUPRESSORES =====
        "metotrexato": "methotrexate",
        "ciclosporina": "cyclosporine",
        "azatioprina": "azathioprine",
        
        # ===== OUTROS =====
        "alopurinol": "allopurinol",
        "colchicina": "colchicine",
        "levotiroxina": "levothyroxine",
        "puran": "levothyroxine",
        "sildenafil": "sildenafil",
        "viagra": "sildenafil",
    }
    
    # Padrões regex para identificação de variações
    DRUG_PATTERNS = {
        # Padrão: nome base + variações de sufixo/prefixo
        r"espironolact[oa]n[ae]?": "spironolactone",
        r"losart[aã]n[ae]?": "losartan",
        r"warfarin[ae]?|varfarin[ae]?": "warfarin",
        r"metformin[ae]?": "metformin",
        r"atorvastatin[ae]?": "atorvastatin",
        r"simvastatin[ae]?": "simvastatin",
        r"omepraz[oó]l": "omeprazole",
        r"pantopraz[oó]l": "pantoprazole",
        r"sertralin[ae]?": "sertraline",
        r"fluoxetin[ae]?": "fluoxetine",
        r"diazep[aã]m": "diazepam",
        r"clonazep[aã]m": "clonazepam",
        r"alprazol[aã]m": "alprazolam",
        r"amoxicilin[ae]?": "amoxicillin",
        r"azitromicin[ae]?": "azithromycin",
        r"ciprofloxacin[oe]?": "ciprofloxacin",
        r"hidroclorotiazid[ae]?": "hydrochlorothiazide",
        r"enalapril": "enalapril",
        r"captopril": "captopril",
        r"propranolol": "propranolol",
        r"atenolol": "atenolol",
        r"metoprolol": "metoprolol",
        r"ibuprofeno?": "ibuprofen",
        r"diclofenaco?": "diclofenac",
        r"paracetamol": "acetaminophen",
        r"dipirona": "metamizole",
        r"clopidogrel": "clopidogrel",
        r"insulina?": "insulin",
        r"glibenclamid[ae]?": "glyburide",
        r"glimepirid[ae]?": "glimepiride",
    }
    
    def __init__(self, llm_client=None):
        """
        Inicializa o identificador híbrido
        
        Args:
            llm_client: Cliente LLM opcional para fallback (ChatOllama ou similar)
        """
        self.llm_client = llm_client
        self._compiled_patterns = self._compile_patterns()
        logger.info(f"HybridDrugIdentifier inicializado")
        logger.info(f"   - {len(self.DRUG_SYNONYMS)} sinônimos mapeados")
        logger.info(f"   - {len(self.DRUG_PATTERNS)} padrões regex")
        logger.info(f"   - LLM fallback: {'habilitado' if llm_client else 'desabilitado'}")
    
    def _compile_patterns(self) -> List[Tuple[re.Pattern, str]]:
        """Compila padrões regex para busca eficiente"""
        compiled = []
        for pattern, canonical in self.DRUG_PATTERNS.items():
            try:
                compiled.append((re.compile(pattern, re.IGNORECASE), canonical))
            except re.error as e:
                logger.warning(f"Padrão regex inválido '{pattern}': {e}")
        return compiled
    
    def _preprocess_name(self, name: str) -> str:
        """
        Pré-processa o nome do medicamento para normalização
        Remove dosagens, formas farmacêuticas, espaços extras
        """
        if not name:
            return ""
        
        # Lowercase e strip
        normalized = name.lower().strip()
        
        # Remover dosagens (50mg, 100 mg, 500UI, etc.)
        normalized = re.sub(r'\s*\d+(?:[.,]\d+)?\s*(mg|ml|g|ui|mcg|%|mg/ml)\s*', ' ', normalized)
        
        # Remover formas farmacêuticas
        forms = r'\b(comprimido|comprimidos|cápsula|capsula|cápsulas|capsulas|'
        forms += r'gotas|xarope|pomada|creme|gel|injetável|injetavel|'
        forms += r'solução|solucao|suspensão|suspensao|spray|adesivo|'
        forms += r'liberação prolongada|lp|xr|sr|cr|retard)\b'
        normalized = re.sub(forms, ' ', normalized, flags=re.IGNORECASE)
        
        # Remover múltiplos espaços
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    @lru_cache(maxsize=1000)
    def identify(self, drug_name: str) -> DrugIdentification:
        """
        Identifica um medicamento usando abordagem híbrida
        
        Estratégias (em ordem de prioridade):
        1. Exact match no dicionário
        2. Regex patterns
        3. Fuzzy matching
        4. LLM inference (se disponível)
        
        Args:
            drug_name: Nome do medicamento (pode ser comercial ou genérico)
            
        Returns:
            DrugIdentification com nome canônico e método usado
        """
        if not drug_name:
            return DrugIdentification(
                original_name="",
                canonical_name="",
                method=IdentificationMethod.NOT_FOUND,
                confidence=0.0
            )
        
        # Pré-processar
        processed = self._preprocess_name(drug_name)
        
        # 1. Exact match
        result = self._try_exact_match(processed)
        if result:
            logger.debug(f"Exact match: '{drug_name}' → '{result}'")
            return DrugIdentification(
                original_name=drug_name,
                canonical_name=result,
                method=IdentificationMethod.EXACT_MATCH,
                confidence=1.0
            )
        
        # 2. Regex patterns
        result = self._try_regex_match(processed)
        if result:
            logger.debug(f"Regex match: '{drug_name}' → '{result}'")
            return DrugIdentification(
                original_name=drug_name,
                canonical_name=result,
                method=IdentificationMethod.REGEX_PATTERN,
                confidence=0.95
            )
        
        # 3. Fuzzy matching
        result, confidence, alternatives = self._try_fuzzy_match(processed)
        if result and confidence >= 0.85:
            logger.debug(f"Fuzzy match: '{drug_name}' → '{result}' ({confidence:.2f})")
            return DrugIdentification(
                original_name=drug_name,
                canonical_name=result,
                method=IdentificationMethod.FUZZY_MATCH,
                confidence=confidence,
                alternatives=alternatives
            )
        
        # 4. LLM fallback (se disponível)
        if self.llm_client:
            result = self._try_llm_inference(drug_name, processed)
            if result:
                logger.debug(f"LLM inference: '{drug_name}' → '{result}'")
                return DrugIdentification(
                    original_name=drug_name,
                    canonical_name=result,
                    method=IdentificationMethod.LLM_INFERENCE,
                    confidence=0.8
                )
        
        # Não encontrado - retornar nome processado como fallback
        logger.warning(f"Medicamento não identificado: '{drug_name}'")
        return DrugIdentification(
            original_name=drug_name,
            canonical_name=processed,  # Usar nome processado
            method=IdentificationMethod.NOT_FOUND,
            confidence=0.5,
            alternatives=alternatives if result else []
        )
    
    def _try_exact_match(self, name: str) -> Optional[str]:
        """Busca exata no dicionário de sinônimos"""
        return self.DRUG_SYNONYMS.get(name)
    
    def _try_regex_match(self, name: str) -> Optional[str]:
        """Busca usando padrões regex"""
        for pattern, canonical in self._compiled_patterns:
            if pattern.fullmatch(name):
                return canonical
        return None
    
    def _try_fuzzy_match(self, name: str) -> Tuple[Optional[str], float, List[str]]:
        """
        Busca aproximada usando SequenceMatcher
        Retorna: (melhor_match, confiança, alternativas)
        """
        best_match = None
        best_ratio = 0.0
        alternatives = []
        
        for synonym, canonical in self.DRUG_SYNONYMS.items():
            ratio = SequenceMatcher(None, name, synonym).ratio()
            
            if ratio > best_ratio:
                # Mover match anterior para alternativas
                if best_match and best_ratio >= 0.7:
                    alternatives.append(best_match)
                best_ratio = ratio
                best_match = canonical
            elif ratio >= 0.7 and canonical != best_match:
                alternatives.append(canonical)
        
        # Limitar alternativas
        alternatives = list(set(alternatives))[:3]
        
        return best_match, best_ratio, alternatives
    
    def _try_llm_inference(self, original: str, processed: str) -> Optional[str]:
        """
        Usa LLM para identificar medicamentos não reconhecidos
        """
        if not self.llm_client:
            return None
        
        try:
            prompt = f"""Identify the canonical English scientific name for this medication.
            
Input: "{original}" (processed: "{processed}")

Rules:
1. Return ONLY the canonical English scientific name (e.g., "acetaminophen", "warfarin")
2. If it's a brand name, return the generic name
3. If uncertain, return "UNKNOWN"
4. Do NOT include dosage or formulation

Response (single word or compound name only):"""

            from langchain_core.messages import HumanMessage
            response = self.llm_client.invoke([HumanMessage(content=prompt)])
            
            result = response.content.strip().lower()
            
            # Validar resposta
            if result and result != "unknown" and len(result) < 50:
                return result
            
        except Exception as e:
            logger.warning(f"LLM inference falhou: {e}")
        
        return None
    
    def identify_multiple(self, drug_names: List[str]) -> Dict[str, DrugIdentification]:
        """
        Identifica múltiplos medicamentos de uma vez
        
        Args:
            drug_names: Lista de nomes de medicamentos
            
        Returns:
            Dicionário {nome_original: DrugIdentification}
        """
        results = {}
        for name in drug_names:
            if name and name.strip():
                results[name] = self.identify(name)
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do identificador"""
        return {
            "synonyms_count": len(self.DRUG_SYNONYMS),
            "patterns_count": len(self.DRUG_PATTERNS),
            "llm_enabled": self.llm_client is not None,
            "cache_info": self.identify.cache_info()._asdict()
        }


# Instância global
_identifier: Optional[HybridDrugIdentifier] = None


def get_drug_identifier(llm_client=None) -> HybridDrugIdentifier:
    """Obter instância do identificador (singleton)"""
    global _identifier
    if _identifier is None:
        _identifier = HybridDrugIdentifier(llm_client=llm_client)
    return _identifier


def reset_identifier():
    """Reset do identificador (para testes)"""
    global _identifier
    _identifier = None

