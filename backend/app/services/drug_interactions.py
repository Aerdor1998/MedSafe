"""
Serviço para análise de interações medicamentosas
Utiliza base de dados CSV com 191k+ interações

SKILLS APLICADAS:
- ULTRATHINK: Integração elegante com agente especializado
- DEBUGGING-STRATEGIES: Root cause fix + logging estruturado
- API-DESIGN-PRINCIPLES: Interface clara e consistente
- CODE-REVIEW-EXCELLENCE: Documentação e rastreabilidade
"""

import asyncio
import csv
import logging
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..db.database import get_db_context
from ..db.models import DrugInteraction
from .clinical_rules import CRITICAL_INTERACTIONS
from .drug_identifier import (
    HybridDrugIdentifier,
    IdentificationMethod,
    get_drug_identifier,
)

# Import do agente especializado em classificação
# SKILL: API-DESIGN-PRINCIPLES - Separação correta de responsabilidades
# Movido de agents/ para services/ para evitar circular import
from .interaction_classifier import SeverityLevel, get_classifier_agent
from .openfda_service import OpenFDAService

logger = logging.getLogger(__name__)


class DrugInteractionService:
    """Serviço para buscar e analisar interações medicamentosas"""

    # Mapa de nomes comerciais/populares → nomes científicos
    # SKILL: ULTRATHINK - Mapeamento abrangente para busca precisa de interações
    DRUG_SYNONYMS = {
        # ===== ESTIMULANTES / TDAH =====
        # Metilfenidato (Ritalina) - CRÍTICO para interações com IMAOs
        "ritalina": "methylphenidate",
        "ritalin": "methylphenidate",
        "metilfenidato": "methylphenidate",
        "concerta": "methylphenidate",
        "methylphenidate": "methylphenidate",
        # Anfetaminas
        "anfetamina": "amphetamine",
        "adderall": "amphetamine",
        "venvanse": "lisdexamfetamine",
        "lisdexanfetamina": "lisdexamfetamine",
        # ===== IMAOs (Inibidores da Monoamina Oxidase) - ALTO RISCO =====
        # Fenelzina
        "fenelzina": "phenelzine",
        "phenelzine": "phenelzine",
        "nardil": "phenelzine",
        # Tranilcipromina
        "tranilcipromina": "tranylcypromine",
        "parnate": "tranylcypromine",
        # Isocarboxazida
        "isocarboxazida": "isocarboxazid",
        "marplan": "isocarboxazid",
        # Selegilina
        "selegilina": "selegiline",
        "emsam": "selegiline",
        "eldepryl": "selegiline",
        # Moclobemida
        "moclobemida": "moclobemide",
        "aurorix": "moclobemide",
        # ===== ANALGÉSICOS =====
        # Aspirina
        "aspirina": "acetylsalicylic acid",
        "aspirin": "acetylsalicylic acid",
        "aas": "acetylsalicylic acid",
        "ácido acetilsalicílico": "acetylsalicylic acid",
        # Paracetamol/Tylenol
        "paracetamol": "acetaminophen",
        "tylenol": "acetaminophen",
        "parac humanoid": "acetaminophen",
        # Tramadol
        "tramadol": "tramadol",
        "tramal": "tramadol",
        # Codeína
        "codeina": "codeine",
        "codeína": "codeine",
        # Dipirona
        "dipirona": "metamizole",
        "novalgina": "metamizole",
        # Ibuprofeno
        "ibuprofeno": "ibuprofen",
        "advil": "ibuprofen",
        "motrin": "ibuprofen",
        # ===== ANTIDEPRESSIVOS =====
        # Sertralina
        "sertralina": "sertraline",
        "zoloft": "sertraline",
        # Fluoxetina
        "fluoxetina": "fluoxetine",
        "prozac": "fluoxetine",
        # Paroxetina
        "paroxetina": "paroxetine",
        "paxil": "paroxetine",
        # Escitalopram
        "escitalopram": "escitalopram",
        "lexapro": "escitalopram",
        # Venlafaxina
        "venlafaxina": "venlafaxine",
        "effexor": "venlafaxine",
        # Duloxetina
        "duloxetina": "duloxetine",
        "cymbalta": "duloxetine",
        # Amitriptilina
        "amitriptilina": "amitriptyline",
        # Nortriptilina
        "nortriptilina": "nortriptyline",
        # Bupropiona
        "bupropiona": "bupropion",
        "wellbutrin": "bupropion",
        # ===== ANTI-HIPERTENSIVOS =====
        # Metformina
        "metformina": "metformin",
        "glifage": "metformin",
        # Losartana
        "losartana": "losartan",
        "losartan potássico": "losartan",
        "cozaar": "losartan",
        # Enalapril
        "enalapril": "enalapril",
        # Captopril
        "captopril": "captopril",
        # Atenolol
        "atenolol": "atenolol",
        # Propranolol
        "propranolol": "propranolol",
        # ===== ESTATINAS =====
        # Atorvastatina
        "atorvastatina": "atorvastatin",
        "lipitor": "atorvastatin",
        # Simvastatina
        "simvastatina": "simvastatin",
        "zocor": "simvastatin",
        # Rosuvastatina
        "rosuvastatina": "rosuvastatin",
        "crestor": "rosuvastatin",
        # ===== ANTICOAGULANTES =====
        # Varfarina
        "varfarina": "warfarin",
        "coumadin": "warfarin",
        "marevan": "warfarin",
        # Rivaroxabana
        "rivaroxabana": "rivaroxaban",
        "xarelto": "rivaroxaban",
        # ===== BENZODIAZEPÍNICOS =====
        # Diazepam
        "diazepam": "diazepam",
        "valium": "diazepam",
        # Clonazepam
        "clonazepam": "clonazepam",
        "rivotril": "clonazepam",
        # Alprazolam
        "alprazolam": "alprazolam",
        "frontal": "alprazolam",
        "xanax": "alprazolam",
        # Lorazepam
        "lorazepam": "lorazepam",
        "lorax": "lorazepam",
        # ===== ANTIBIÓTICOS =====
        # Amoxicilina
        "amoxicilina": "amoxicillin",
        # Azitromicina
        "azitromicina": "azithromycin",
        # Ciprofloxacino
        "ciprofloxacino": "ciprofloxacin",
        # ===== ANTIÁCIDOS / GASTROPROTEÇÃO =====
        # Omeprazol
        "omeprazol": "omeprazole",
        # Pantoprazol
        "pantoprazol": "pantoprazole",
        # Esomeprazol
        "esomeprazol": "esomeprazole",
        # Hidroclorotiazida
        "hidroclorotiazida": "hydrochlorothiazide",
        # ===== ANTIPSICÓTICOS =====
        # Haloperidol
        "haloperidol": "haloperidol",
        "haldol": "haloperidol",
        # Risperidona
        "risperidona": "risperidone",
        "risperdal": "risperidone",
        # Quetiapina
        "quetiapina": "quetiapine",
        "seroquel": "quetiapine",
        # Olanzapina
        "olanzapina": "olanzapine",
        "zyprexa": "olanzapine",
        # ===== CRÍTICOS ADICIONAIS (PT → EN) =====
        "espironolactona": "spironolactone",
        "spironolactona": "spironolactone",
        "aldactone": "spironolactone",
        "sinvastatina": "simvastatin",
        "omeprazole": "omeprazole",
        "pantoprazole": "pantoprazole",
        "diclofenaco": "diclofenac",
        "voltaren": "diclofenac",
        "cataflam": "diclofenac",
        "metamizol": "metamizole",
        "acetaminofeno": "acetaminophen",
        "insulina": "insulin",
        "insulin": "insulin",
        "glibenclamida": "glyburide",
        "glimepirida": "glimepiride",
        # ===== CARDIOVASCULAR ADICIONAL =====
        "amlodipina": "amlodipine",
        "norvasc": "amlodipine",
        "anlodipino": "amlodipine",
        "carvedilol": "carvedilol",
        "coreg": "carvedilol",
        "metoprolol": "metoprolol",
        "seloken": "metoprolol",
        "bisoprolol": "bisoprolol",
        "concor": "bisoprolol",
        "furosemida": "furosemide",
        "lasix": "furosemide",
        "lisinopril": "lisinopril",
        "ramipril": "ramipril",
        "valsartana": "valsartan",
        "diovan": "valsartan",
        "candesartana": "candesartan",
        "atacand": "candesartan",
        "telmisartana": "telmisartan",
        "micardis": "telmisartan",
        "nifedipina": "nifedipine",
        "adalat": "nifedipine",
        "diltiazem": "diltiazem",
        "verapamil": "verapamil",
        "digoxina": "digoxin",
        "lanoxin": "digoxin",
        # ===== DIABETES ADICIONAL =====
        "glicazida": "gliclazide",
        "diamicron": "gliclazide",
        "sitagliptina": "sitagliptin",
        "januvia": "sitagliptin",
        "janumet": "sitagliptin",
        "vildagliptina": "vildagliptin",
        "galvus": "vildagliptin",
        "linagliptina": "linagliptin",
        "trayenta": "linagliptin",
        "empagliflozina": "empagliflozin",
        "jardiance": "empagliflozin",
        "dapagliflozina": "dapagliflozin",
        "forxiga": "dapagliflozin",
        "canagliflozina": "canagliflozin",
        "invokana": "canagliflozin",
        "liraglutida": "liraglutide",
        "victoza": "liraglutide",
        "saxenda": "liraglutide",
        "dulaglutida": "dulaglutide",
        "trulicity": "dulaglutide",
        "semaglutida": "semaglutide",
        "ozempic": "semaglutide",
        "wegovy": "semaglutide",
        "rybelsus": "semaglutide",
        "pioglitazona": "pioglitazone",
        "actos": "pioglitazone",
        # ===== NEUROLÓGICO/PSIQUIÁTRICO ADICIONAL =====
        "pregabalina": "pregabalin",
        "lyrica": "pregabalin",
        "gabapentina": "gabapentin",
        "neurontin": "gabapentin",
        "carbamazepina": "carbamazepine",
        "tegretol": "carbamazepine",
        "lamotrigina": "lamotrigine",
        "lamictal": "lamotrigine",
        "valproato": "valproic acid",
        "depakene": "valproic acid",
        "depakote": "valproic acid",
        "ácido valproico": "valproic acid",
        "topiramato": "topiramate",
        "topamax": "topiramate",
        "fenitoína": "phenytoin",
        "dilantin": "phenytoin",
        "levetiracetam": "levetiracetam",
        "keppra": "levetiracetam",
        "lítio": "lithium",
        "lithium": "lithium",
        "carbolithium": "lithium",
        "aripiprazol": "aripiprazole",
        "abilify": "aripiprazole",
        "paliperidona": "paliperidone",
        "invega": "paliperidone",
        "zolpidem": "zolpidem",
        "stilnox": "zolpidem",
        "trazodona": "trazodone",
        "donaren": "trazodone",
        "mirtazapina": "mirtazapine",
        "remeron": "mirtazapine",
        "desvenlafaxina": "desvenlafaxine",
        "pristiq": "desvenlafaxine",
        # ===== ANTIBIÓTICOS ADICIONAL =====
        "levofloxacino": "levofloxacin",
        "levaquin": "levofloxacin",
        "moxifloxacino": "moxifloxacin",
        "avelox": "moxifloxacin",
        "claritromicina": "clarithromycin",
        "biaxin": "clarithromycin",
        "metronidazol": "metronidazole",
        "flagyl": "metronidazole",
        "sulfametoxazol": "sulfamethoxazole",
        "bactrim": "sulfamethoxazole",
        "trimetoprima": "trimethoprim",
        "doxiciclina": "doxycycline",
        "clindamicina": "clindamycin",
        "vancomicina": "vancomycin",
        "gentamicina": "gentamicin",
        "cefalexina": "cephalexin",
        "keflex": "cephalexin",
        "ceftriaxona": "ceftriaxone",
        "rocefin": "ceftriaxone",
        "penicilina": "penicillin",
        # ===== ANTICOAGULANTES ADICIONAL =====
        "apixabana": "apixaban",
        "eliquis": "apixaban",
        "dabigatrana": "dabigatran",
        "pradaxa": "dabigatran",
        "edoxabana": "edoxaban",
        "savaysa": "edoxaban",
        "enoxaparina": "enoxaparin",
        "clexane": "enoxaparin",
        "heparina": "heparin",
        "clopidogrel": "clopidogrel",
        "plavix": "clopidogrel",
        "ticagrelor": "ticagrelor",
        "brilinta": "ticagrelor",
        # ===== OTC / COMUM =====
        "naproxeno": "naproxen",
        "flanax": "naproxen",
        "nimesulida": "nimesulide",
        "meloxicam": "meloxicam",
        "mobic": "meloxicam",
        "cetoprofeno": "ketoprofen",
        "piroxicam": "piroxicam",
        "feldene": "piroxicam",
        "prednisona": "prednisone",
        "prednisolona": "prednisolone",
        "dexametasona": "dexamethasone",
        "decadron": "dexamethasone",
        "betametasona": "betamethasone",
        "celestone": "betamethasone",
        "hidrocortisona": "hydrocortisone",
        "cortisol": "hydrocortisone",
        "loratadina": "loratadine",
        "claritin": "loratadine",
        "cetirizina": "cetirizine",
        "zyrtec": "cetirizine",
        "fexofenadina": "fexofenadine",
        "allegra": "fexofenadine",
        "difenidramina": "diphenhydramine",
        "benadryl": "diphenhydramine",
        "ranitidina": "ranitidine",
        "zantac": "ranitidine",
        "famotidina": "famotidine",
        "pepcid": "famotidine",
        # ===== TIREOIDE =====
        "levotiroxina": "levothyroxine",
        "synthroid": "levothyroxine",
        "puran t4": "levothyroxine",
        "euthyrox": "levothyroxine",
        "propiltiouracil": "propylthiouracil",
        "metimazol": "methimazole",
        "tapazole": "methimazole",
        # ===== DISFUNÇÃO ERÉTIL =====
        "sildenafil": "sildenafil",
        "viagra": "sildenafil",
        "tadalafil": "tadalafil",
        "cialis": "tadalafil",
        "vardenafil": "vardenafil",
        "levitra": "vardenafil",
        # ===== HIPERPLASIA PROSTÁTICA =====
        "tansulosina": "tamsulosin",
        "flomax": "tamsulosin",
        "finasterida": "finasteride",
        "proscar": "finasteride",
        "propecia": "finasteride",
        "dutasterida": "dutasteride",
        "avodart": "dutasteride",
        # ===== GOTA =====
        "alopurinol": "allopurinol",
        "zyloprim": "allopurinol",
        "colchicina": "colchicine",
        "febuxostat": "febuxostat",
        "uloric": "febuxostat",
    }

    def __init__(self, llm_client=None):
        self.db_path = (
            Path(__file__).parent.parent.parent.parent
            / "data"
            / "db_drug_interactions.csv"
        )
        self._interactions_cache = None
        self.classifier_agent = get_classifier_agent()  # Agente especializado
        self.openfda_service = OpenFDAService()

        # NOVO: Identificador híbrido (regex + fuzzy + LLM)
        self.drug_identifier = get_drug_identifier(llm_client=llm_client)

        logger.info(f"DrugInteractionService inicializado - Base: {self.db_path}")
        logger.info(f"🤖 InteractionClassifierAgent integrado")
        logger.info(f"🔬 HybridDrugIdentifier integrado (regex + fuzzy + LLM)")

    @property
    def interactions_db(self):
        """Lazy loading da base de interações"""
        if self._interactions_cache is None:
            self._load_interactions()
        return self._interactions_cache

    def _load_interactions(self):
        """
        Carregar base de dados de interações - LAZY LOADING ONLY WHEN NEEDED

        IMPORTANTE: Base NÃO é carregada no __init__ para economizar memória
        Interações são buscadas sob demanda via find_interactions()
        """
        try:
            logger.info(
                "📚 Base de interações pronta para busca sob demanda (lazy loading)"
            )
            # Não carregar tudo na memória - apenas indexar o arquivo
            self._interactions_cache = {}  # Cache vazio inicialmente

            if not self.db_path.exists():
                logger.error(f"Arquivo de interações não encontrado: {self.db_path}")
                return

            logger.info(f"Arquivo de interações disponível: {self.db_path}")
            logger.info(
                "   Interações serão buscadas sob demanda para economizar memória"
            )

        except Exception as e:
            logger.error(f"Erro ao verificar base de interações: {e}")
            self._interactions_cache = {}

    def _normalize_drug_name(self, name: str) -> str:
        """
        Normalizar nome do medicamento para busca usando identificador híbrido

        REFATORADO: Agora usa HybridDrugIdentifier que combina:
        1. Exact match no dicionário
        2. Regex patterns para variações
        3. Fuzzy matching para erros de digitação
        4. LLM inference como fallback (se disponível)

        SKILL: ULTRATHINK - Abordagem híbrida elegante
        """
        if not name:
            return ""

        # Usar identificador híbrido
        identification = self.drug_identifier.identify(name)

        # Log do método usado
        if identification.method != IdentificationMethod.NOT_FOUND:
            logger.debug(
                f"   🔄 Identificado '{name}' → '{identification.canonical_name}' "
                f"via {identification.method.value} (confiança: {identification.confidence:.2f})"
            )

        return identification.canonical_name

    def _classify_severity(
        self, description: str, drug1: str = "", drug2: str = ""
    ) -> str:
        """
        Classificar severidade da interação baseado na descrição

        REFATORADO: Agora usa InteractionClassifierAgent (padrão agêntico)
        SKILL: ULTRATHINK - Delegação para agente especializado
        SKILL: DEBUGGING-STRATEGIES - Fix do bug de classificação

        Args:
            description: Descrição da interação
            drug1: Nome do primeiro medicamento (para logging)
            drug2: Nome do segundo medicamento (para logging)

        Returns:
            'critical', 'high', 'medium', 'low'
        """
        # Delegar para agente especializado
        result = self.classifier_agent.classify_interaction(
            description=description, drug1=drug1 or "drug1", drug2=drug2 or "drug2"
        )

        # Validar decisões críticas com Reflection Pattern
        if result.severity == SeverityLevel.CRITICAL:
            result = self.classifier_agent.validate_critical_decision(
                result, description
            )

        # Log detalhado para auditoria
        logger.debug(
            f"   Severidade: {result.severity.value} (confiança: {result.confidence:.2f})"
        )
        logger.debug(f"   Raciocínio: {result.reasoning}")

        return result.severity.value

    def _classify_category(self, description: str) -> str:
        """Classificar categoria da interação"""
        description_lower = description.lower()

        if "cardiotoxic" in description_lower or "cardiac" in description_lower:
            return "Cardiovascular"
        elif "hepatotoxic" in description_lower or "liver" in description_lower:
            return "Hepática"
        elif (
            "nephrotoxic" in description_lower
            or "renal" in description_lower
            or "kidney" in description_lower
        ):
            return "Renal"
        elif (
            "neurotoxic" in description_lower
            or "cns" in description_lower
            or "sedation" in description_lower
        ):
            return "Neurológica"
        elif "photosensitiz" in description_lower:
            return "Fotossensibilidade"
        elif "metabolism" in description_lower or "cyp" in description_lower:
            return "Farmacocinética"
        elif "bleeding" in description_lower or "anticoagulant" in description_lower:
            return "Coagulação"
        else:
            return "Farmacológica"

    def find_interactions(
        self, drug_name: str, other_drugs: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Buscar interações entre um medicamento e uma lista de outros
        OTIMIZADO: Pre-normaliza medicamentos e usa filtro rápido antes de normalização completa

        Args:
            drug_name: Nome do medicamento principal
            other_drugs: Lista de outros medicamentos em uso

        Returns:
            Lista de interações encontradas (apenas as relevantes)
        """
        interactions = []

        # Pre-normalize all input drugs ONCE (not per row!)
        drug_normalized = self._normalize_drug_name(drug_name)
        other_normalized_map = {}
        for other in other_drugs:
            if other and other.strip():
                other_normalized_map[other] = self._normalize_drug_name(other)

        # Build set of normalized names for fast lookup
        search_drugs = {drug_normalized} | set(other_normalized_map.values())

        # LGPD/PHI: avoid logging medication names in plaintext
        logger.info(
            "Buscando interações (other_meds_count=%s)", len(other_normalized_map)
        )

        if not other_normalized_map:
            logger.info("   No other medications to check for interactions")
            return []

        # 0) Fast path: DB lookup (if drug_interactions table is populated)
        try:
            db_results = self._find_interactions_db(
                drug_normalized, other_normalized_map
            )
            if db_results:
                logger.info(f"DB interactions found: {len(db_results)}")
                return db_results
        except Exception as e:
            logger.debug(f"DB lookup skipped/fallback to CSV: {e}")

        # 1) Fallback: Buscar interações no CSV com filtro rápido
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows_scanned = 0
                rows_checked = 0

                for row in reader:
                    rows_scanned += 1

                    # FAST FILTER: Skip rows that can't possibly match
                    # Check if raw drug names (lowercase) contain any of our search terms
                    drug1_raw = row["Drug 1"].lower()
                    drug2_raw = row["Drug 2"].lower()

                    # Quick check: does this row potentially involve our drugs?
                    might_match = False
                    for search_term in search_drugs:
                        if search_term in drug1_raw or search_term in drug2_raw:
                            might_match = True
                            break

                    if not might_match:
                        continue  # Skip this row - no potential match

                    # DETAILED CHECK: Only normalize when there's potential match
                    rows_checked += 1
                    drug1_normalized = self._normalize_drug_name(row["Drug 1"])
                    drug2_normalized = self._normalize_drug_name(row["Drug 2"])

                    # Check if interaction involves our drugs
                    for other_drug, other_norm in other_normalized_map.items():
                        # Match bidirecional
                        if (
                            drug_normalized == drug1_normalized
                            and other_norm == drug2_normalized
                        ) or (
                            drug_normalized == drug2_normalized
                            and other_norm == drug1_normalized
                        ):
                            interaction_data = {
                                "drug1": row["Drug 1"],
                                "drug2": row["Drug 2"],
                                "description": row["Interaction Description"],
                                "severity": self._classify_severity(
                                    row["Interaction Description"],
                                    row["Drug 1"],
                                    row["Drug 2"],
                                ),
                                "category": self._classify_category(
                                    row["Interaction Description"]
                                ),
                            }

                            interactions.append(interaction_data)
                            logger.info(
                                f"   Interação encontrada: {drug_name} + {other_drug} ({interaction_data['severity']})"
                            )
                            break  # Found interaction, next row

                logger.info(
                    f"Total de interações encontradas: {len(interactions)} (escaneadas {rows_scanned}, verificadas {rows_checked})"
                )

        except Exception as e:
            logger.error(f"Erro ao buscar interações: {e}")

        return interactions

    def _find_interactions_db(
        self, drug_norm: str, other_map: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Lookup interactions by canonical pairs in Postgres.

        Stores pairs in sorted (a_norm, b_norm) order for indexed lookup.
        """
        if not drug_norm or not other_map:
            return []

        interactions: List[Dict[str, Any]] = []

        with get_db_context() as db:
            for other_raw, other_norm in other_map.items():
                if not other_norm:
                    continue

                a_norm, b_norm = sorted([drug_norm, other_norm])
                row = (
                    db.query(DrugInteraction)
                    .filter(DrugInteraction.drug_a_norm == a_norm)
                    .filter(DrugInteraction.drug_b_norm == b_norm)
                    .first()
                )
                if not row:
                    continue

                desc = row.clinical_effect or row.mechanism or ""
                interactions.append(
                    {
                        "drug1": drug_norm,
                        "drug2": other_norm,
                        "description": desc,
                        "severity": row.severity
                        or self._classify_severity(desc, drug_norm, other_norm),
                        "category": row.interaction_type or "DrugInteractionDB",
                        "source": row.source or "db",
                    }
                )

        return interactions

    async def find_interactions_with_fallback(
        self, drug_name: str, other_drugs: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Busca interações com fallback para OpenFDA e regras clínicas conhecidas
        """
        interactions = self.find_interactions(drug_name, other_drugs)

        if interactions:
            return interactions

        logger.info("CSV não encontrou interações, tentando OpenFDA...")

        try:
            openfda_interactions = await self._query_openfda(drug_name, other_drugs)
            if openfda_interactions:
                logger.info(f"OpenFDA encontrou {len(openfda_interactions)} interações")
                return openfda_interactions
        except Exception as e:
            logger.warning(f"OpenFDA fallback falhou: {e}")

        return self._check_known_clinical_rules(drug_name, other_drugs)

    async def _query_openfda(
        self, drug_name: str, other_drugs: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Consulta OpenFDA para validar interações com base em bulas/labels.
        """
        if not self.openfda_service:
            return []

        interactions: List[Dict[str, Any]] = []
        primary_norm = self._normalize_drug_name(drug_name)

        # Buscar bula (label) e eventos adversos
        label = await self.openfda_service.get_drug_label(primary_norm)

        # Consolidar texto relevante
        label_sections = []
        if label:
            for key in [
                "drug_interactions",
                "drug_interactions_table",
                "warnings",
                "warnings_and_cautions",
            ]:
                value = label.get(key)
                if isinstance(value, list):
                    label_sections.extend(value)
                elif isinstance(value, str):
                    label_sections.append(value)

        label_text = " ".join(label_sections).lower() if label_sections else ""

        for other in other_drugs:
            if not other or not other.strip():
                continue
            other_norm = self._normalize_drug_name(other)
            if not other_norm:
                continue

            if other_norm in label_text:
                severity = "high" if "contraindicat" in label_text else "medium"
                interactions.append(
                    {
                        "drug1": drug_name,
                        "drug2": other,
                        "description": "OpenFDA label mentions interaction",
                        "severity": severity,
                        "category": "OpenFDA",
                        "source": "openfda_label",
                    }
                )

        return interactions

    async def find_interactions_openfda(
        self, drug_name: str, other_drugs: List[str]
    ) -> List[Dict[str, Any]]:
        """Consulta OpenFDA independentemente do CSV para validação."""
        try:
            return await self._query_openfda(drug_name, other_drugs)
        except Exception as e:
            logger.warning(f"OpenFDA validation failed: {e}")
            return []

    def _check_known_clinical_rules(
        self, drug_name: str, other_drugs: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Última camada: regras clínicas críticas conhecidas
        """
        results: List[Dict[str, Any]] = []
        primary = self._normalize_drug_name(drug_name)

        for other in other_drugs:
            if not other or not other.strip():
                continue
            other_norm = self._normalize_drug_name(other)

            for (drug_a, drug_b), data in CRITICAL_INTERACTIONS.items():
                if {primary, other_norm} == {drug_a, drug_b}:
                    results.append(
                        {
                            "drug1": drug_name,
                            "drug2": other,
                            "description": data.get(
                                "effect", "Interação clínica conhecida"
                            ),
                            "severity": data.get("severity", "high"),
                            "category": data.get("category", "ClinicalRule"),
                            "mechanism": data.get("mechanism"),
                            "recommendation": data.get("recommendation"),
                        }
                    )

        if results:
            logger.info(f"Regras clínicas retornaram {len(results)} interações")

        return results

    def analyze_contraindications(
        self, drug_name: str, patient_conditions: List[str], allergies: List[str]
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
            if (
                allergy_normalized in drug_normalized
                or drug_normalized in allergy_normalized
            ):
                contraindications.append(
                    {
                        "type": "Alergia Conhecida",
                        "description": f"Paciente possui alergia conhecida a {allergy}",
                        "severity": "critical",
                        "source": "Histórico do Paciente",
                        "recommendation": "CONTRAINDICADO - Não administrar",
                    }
                )

        # Contraindicações baseadas em condições comuns
        condition_contraindications = self._get_condition_contraindications(
            drug_normalized, patient_conditions
        )
        contraindications.extend(condition_contraindications)

        return contraindications

    def _get_condition_contraindications(
        self, drug_normalized: str, conditions: List[str]
    ) -> List[Dict[str, Any]]:
        """Contraindicações baseadas em condições médicas"""
        contraindications = []

        # Mapa de condições -> medicamentos contraindicados (expandido PT/EN)
        condition_drug_map = {
            # Gravidez
            "gravidez": [
                "methotrexate",
                "isotretinoin",
                "warfarin",
                "valproic acid",
                "atorvastatin",
                "simvastatin",
                "rosuvastatin",
            ],
            "gestação": [
                "methotrexate",
                "isotretinoin",
                "warfarin",
                "valproic acid",
                "atorvastatin",
                "simvastatin",
                "rosuvastatin",
            ],
            "pregnant": [
                "methotrexate",
                "isotretinoin",
                "warfarin",
                "valproic acid",
                "atorvastatin",
                "simvastatin",
                "rosuvastatin",
            ],
            "grávida": [
                "methotrexate",
                "isotretinoin",
                "warfarin",
                "valproic acid",
                "atorvastatin",
                "simvastatin",
                "rosuvastatin",
            ],
            # Insuficiência Renal
            "insuficiência renal": [
                "metformin",
                "nsaid",
                "ibuprofen",
                "diclofenac",
                "naproxen",
                "lithium",
                "spironolactone",
                "enalapril",
                "lisinopril",
            ],
            "renal": [
                "metformin",
                "nsaid",
                "ibuprofen",
                "diclofenac",
                "naproxen",
                "lithium",
                "spironolactone",
                "enalapril",
                "lisinopril",
            ],
            "kidney": [
                "metformin",
                "nsaid",
                "ibuprofen",
                "diclofenac",
                "naproxen",
                "lithium",
                "spironolactone",
                "enalapril",
                "lisinopril",
            ],
            "doença renal": [
                "metformin",
                "nsaid",
                "ibuprofen",
                "diclofenac",
                "naproxen",
                "lithium",
                "spironolactone",
            ],
            # Insuficiência Hepática
            "insuficiência hepática": [
                "acetaminophen",
                "paracetamol",
                "simvastatin",
                "atorvastatin",
                "methotrexate",
            ],
            "liver": [
                "acetaminophen",
                "paracetamol",
                "simvastatin",
                "atorvastatin",
                "methotrexate",
            ],
            "hepática": [
                "acetaminophen",
                "paracetamol",
                "simvastatin",
                "atorvastatin",
                "methotrexate",
            ],
            "cirrose": [
                "acetaminophen",
                "paracetamol",
                "simvastatin",
                "atorvastatin",
                "methotrexate",
            ],
            # Cardiovascular
            "insuficiência cardíaca": [
                "nsaid",
                "ibuprofen",
                "diclofenac",
                "verapamil",
                "diltiazem",
            ],
            "heart failure": [
                "nsaid",
                "ibuprofen",
                "diclofenac",
                "verapamil",
                "diltiazem",
            ],
            "cardíaca": ["nsaid", "ibuprofen", "diclofenac"],
            # Hipercalemia / Potássio alto
            "hipercalemia": [
                "spironolactone",
                "enalapril",
                "losartan",
                "lisinopril",
                "potassium",
            ],
            "hyperkalemia": [
                "spironolactone",
                "enalapril",
                "losartan",
                "lisinopril",
                "potassium",
            ],
            "potássio alto": ["spironolactone", "enalapril", "losartan", "lisinopril"],
            # Diabetes
            "diabetes": ["corticosteroid", "prednisone", "dexamethasone"],
            "diabético": ["corticosteroid", "prednisone", "dexamethasone"],
            # Asma
            "asma": ["propranolol", "atenolol", "metoprolol", "aspirin"],
            "asthma": ["propranolol", "atenolol", "metoprolol", "aspirin"],
            # Úlcera gástrica
            "úlcera": ["nsaid", "ibuprofen", "aspirin", "diclofenac", "naproxen"],
            "ulcer": ["nsaid", "ibuprofen", "aspirin", "diclofenac", "naproxen"],
            "gástrica": ["nsaid", "ibuprofen", "aspirin", "diclofenac"],
            # Hipertensão
            "hipertensão": [],  # Não é contraindicação, mas pode exigir ajustes
            "hypertension": [],
        }

        for condition in conditions:
            condition_lower = condition.lower().strip()
            for condition_key, contraindicated_drugs in condition_drug_map.items():
                if condition_key in condition_lower:
                    for contra_drug in contraindicated_drugs:
                        if contra_drug in drug_normalized:
                            contraindications.append(
                                {
                                    "type": f"Contraindicação por {condition}",
                                    "description": f"{contra_drug.capitalize()} pode ser contraindicado em pacientes com {condition}",
                                    "severity": "high",
                                    "source": "Diretrizes Clínicas",
                                    "recommendation": "Avaliar alternativas terapêuticas com médico",
                                }
                            )

        return contraindications

    def calculate_overall_risk(
        self,
        interactions: List[Dict[str, Any]],
        contraindications: List[Dict[str, Any]],
    ) -> str:
        """
        Calcular nível de risco geral baseado em interações e contraindicações

        SKILL: ULTRATHINK - Lógica clara e auditável
        SKILL: DEBUGGING-STRATEGIES - Logging detalhado para rastreabilidade

        Algoritmo:
        1. CRITICAL: Se há pelo menos 1 interação/contraindicação crítica
        2. HIGH: Se há pelo menos 1 high (mas nenhuma critical)
        3. MEDIUM: Se há pelo menos 1 medium (mas nenhuma high/critical)
        4. LOW: Caso contrário

        Returns:
            'critical', 'high', 'medium', 'low'
        """
        logger.info("Calculando risco geral...")
        logger.info(
            f"   {len(interactions)} interações, {len(contraindications)} contraindicações"
        )

        # Contar severidades
        critical_contraindications = [
            c for c in contraindications if c.get("severity") == "critical"
        ]
        critical_interactions = [
            i for i in interactions if i.get("severity") == "critical"
        ]

        high_contraindications = [
            c for c in contraindications if c.get("severity") == "high"
        ]
        high_interactions = [i for i in interactions if i.get("severity") == "high"]

        medium_contraindications = [
            c for c in contraindications if c.get("severity") == "medium"
        ]
        medium_interactions = [i for i in interactions if i.get("severity") == "medium"]

        # 1. Se há contraindicações ou interações CRÍTICAS → CRITICAL
        if critical_contraindications or critical_interactions:
            logger.warning(f"🔴 RISCO CRÍTICO identificado:")
            if critical_contraindications:
                logger.warning(
                    f"   - {len(critical_contraindications)} contraindicação(ões) crítica(s)"
                )
            if critical_interactions:
                logger.warning(
                    f"   - {len(critical_interactions)} interação(ões) crítica(s)"
                )
            return "critical"

        # 2. Se há pelo menos 1 HIGH → HIGH
        high_count = len(high_contraindications) + len(high_interactions)
        if high_count >= 1:
            logger.warning(f"🟠 RISCO ALTO identificado:")
            if high_contraindications:
                logger.warning(
                    f"   - {len(high_contraindications)} contraindicação(ões) de alto risco"
                )
            if high_interactions:
                logger.warning(
                    f"   - {len(high_interactions)} interação(ões) de alto risco"
                )
            return "high"

        # 3. Se há pelo menos 1 MEDIUM → MEDIUM
        medium_count = len(medium_contraindications) + len(medium_interactions)
        if medium_count >= 1:
            logger.info(f"🟡 RISCO MODERADO identificado:")
            if medium_contraindications:
                logger.info(
                    f"   - {len(medium_contraindications)} contraindicação(ões) moderada(s)"
                )
            if medium_interactions:
                logger.info(
                    f"   - {len(medium_interactions)} interação(ões) moderada(s)"
                )
            return "medium"

        # 4. Sem interações significativas → LOW
        logger.info("🟢 RISCO BAIXO - Sem interações significativas identificadas")
        return "low"


# Instância global (singleton)
_interaction_service = None


def normalize_drug_name(drug_name: str) -> str:
    """
    Normalize drug name for consistent matching

    Args:
        drug_name: Drug name to normalize

    Returns:
        Normalized drug name (lowercase, trimmed)
    """
    if not drug_name:
        return ""

    # Convert to lowercase and remove extra whitespace
    normalized = drug_name.lower().strip()

    # Remove common suffixes/prefixes
    normalized = normalized.replace(" hcl", "").replace(" sulfate", "")
    normalized = normalized.replace(" sodium", "").replace(" potassium", "")

    return normalized


def get_interaction_service() -> DrugInteractionService:
    """Obter instância do serviço de interações"""
    global _interaction_service
    if _interaction_service is None:
        _interaction_service = DrugInteractionService()
    return _interaction_service
