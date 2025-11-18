"""
ClinicalRulesAgent - Agente para aplicação de regras clínicas
Análise REAL de contraindicações e interações medicamentosas
"""

import logging
from typing import Dict, Any, List, Optional
import sys
from pathlib import Path

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.drug_interactions import get_interaction_service

logger = logging.getLogger(__name__)


class ClinicalRulesAgent:
    """Agente para aplicação de regras clínicas com análise REAL"""

    def __init__(self):
        """Inicializar o ClinicalRulesAgent"""
        self.interaction_service = get_interaction_service()
        logger.info("⚕️  ClinicalRulesAgent inicializado - Base de 191k+ interações carregada")

    async def analyze_contraindications(
        self,
        triage_data: Dict[str, Any],
        vision_data: Optional[Dict[str, Any]] = None,
        evidence_snippets: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analisar contraindicações baseado em dados de triagem e evidências

        Args:
            triage_data: Dados da triagem
            vision_data: Dados da análise de visão (opcional)
            evidence_snippets: Evidências coletadas

        Returns:
            Análise clínica estruturada
        """
        logger.info("🔬 Iniciando análise clínica REAL...")

        try:
            # Extrair dados do paciente
            age = triage_data.get('age', 0)
            weight = triage_data.get('weight')
            pregnant = triage_data.get('pregnant', False)

            # Medicamentos em uso
            meds_in_use = triage_data.get('meds_in_use', [])
            if isinstance(meds_in_use, list) and len(meds_in_use) > 0:
                current_meds = [med.get('name', med) if isinstance(med, dict) else str(med)
                               for med in meds_in_use]
            else:
                current_meds = []

            # Condições médicas
            conditions = triage_data.get('conditions', [])
            if isinstance(conditions, str):
                conditions = [c.strip() for c in conditions.split(',') if c.strip()]

            # Alergias
            allergies = triage_data.get('allergies', [])
            if isinstance(allergies, str):
                allergies = [a.strip() for a in allergies.split(',') if a.strip()]

            # Medicamento sendo analisado (vem do vision_data ou evidence)
            medication_name = None
            if vision_data and 'drug_name' in vision_data:
                medication_name = vision_data['drug_name']
            elif vision_data and 'medication_name' in vision_data:
                medication_name = vision_data['medication_name']
            elif evidence_snippets and len(evidence_snippets) > 0:
                medication_name = evidence_snippets[0].get('drug_name', 'medicamento')
            else:
                # Fallback: tentar pegar de medication_text se existir
                medication_name = triage_data.get('medication_text', 'medicamento')

            logger.info(f"   📊 Analisando: {medication_name}")
            logger.info(f"   👤 Idade: {age}, Peso: {weight}")
            logger.info(f"   💊 Medicamentos em uso: {current_meds}")
            logger.info(f"   🏥 Condições: {conditions}")
            logger.info(f"   ⚠️  Alergias: {allergies}")

            # === 1. BUSCAR INTERAÇÕES MEDICAMENTOSAS ===
            interactions_found = []
            if current_meds:
                raw_interactions = self.interaction_service.find_interactions(
                    medication_name,
                    current_meds
                )

                # Formatar interações para o formato esperado
                for interaction in raw_interactions:
                    interactions_found.append({
                        'interacting_drug': interaction['drug2'] if interaction['drug1'].lower() in medication_name.lower() else interaction['drug1'],
                        'effect': interaction['description'],
                        'severity': interaction['severity'],
                        'mechanism': interaction['category'],
                        'recommendation': self._get_interaction_recommendation(interaction['severity'])
                    })

            # === 2. BUSCAR CONTRAINDICAÇÕES ===
            contraindications_found = []

            # Adicionar gravidez se aplicável
            if pregnant:
                conditions.append('gravidez')

            # Buscar contraindicações baseadas em condições
            if conditions or allergies:
                raw_contraindications = self.interaction_service.analyze_contraindications(
                    medication_name,
                    conditions,
                    allergies
                )
                contraindications_found.extend(raw_contraindications)

            # === 3. AJUSTES DE DOSAGEM ===
            dosage_adjustments = self._check_dosage_adjustments(
                medication_name, age, weight, conditions
            )

            # === 4. REAÇÕES ADVERSAS COMUNS ===
            adverse_reactions = self._get_common_adverse_reactions(medication_name)

            # === 5. AVALIAR FATORES DE RISCO DO PACIENTE ===
            patient_risk_factors = self._evaluate_patient_risk_factors(
                adverse_reactions, age, pregnant, conditions, current_meds
            )

            # === 6. CALCULAR RISCO GERAL ===
            risk_level = self.interaction_service.calculate_overall_risk(
                interactions_found,
                contraindications_found
            )

            # Ajustar risco baseado em fatores de risco do paciente
            if patient_risk_factors['critical_risk_count'] >= 2:
                risk_level = 'critical'
            elif patient_risk_factors['critical_risk_count'] >= 1 and risk_level in ['low']:
                risk_level = 'high'
            elif patient_risk_factors['high_risk_count'] >= 2 and risk_level == 'low':
                risk_level = 'high'
            elif patient_risk_factors['high_risk_count'] >= 1 and risk_level == 'low':
                risk_level = 'medium'

            # === 7. GERAR NOTAS DE ANÁLISE ===
            analysis_notes = self._generate_analysis_notes(
                medication_name,
                risk_level,
                len(interactions_found),
                len(contraindications_found),
                age,
                pregnant
            )

            # === 8. CALCULAR CONFIDENCE SCORE ===
            confidence = 0.85 if (interactions_found or contraindications_found) else 0.65

            logger.info(f"   ✅ Análise concluída - Risco: {risk_level}")
            logger.info(f"   📊 Interações: {len(interactions_found)}, Contraindicações: {len(contraindications_found)}")

            return {
                "risk_level": risk_level,
                "contraindications": contraindications_found,
                "interactions": interactions_found,
                "dosage_adjustments": dosage_adjustments,
                "adverse_reactions": adverse_reactions,
                "evidence_links": [e.get('source', 'Database') for e in evidence_snippets] if evidence_snippets else [],
                "model_used": "clinical_rules_v1 + drug_interactions_db_191k",
                "confidence_score": confidence,
                "analysis_notes": analysis_notes,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"❌ Erro na análise clínica: {e}", exc_info=True)
            # Retornar análise básica em caso de erro
            return {
                "risk_level": "medium",
                "contraindications": [],
                "interactions": [],
                "dosage_adjustments": [],
                "adverse_reactions": [],
                "evidence_links": [],
                "model_used": "clinical_rules_v1_fallback",
                "confidence_score": 0.3,
                "analysis_notes": f"Erro na análise: {str(e)}. Consulte um profissional de saúde.",
                "status": "error_fallback"
            }

    def _get_interaction_recommendation(self, severity: str) -> str:
        """Gerar recomendação baseada na severidade"""
        recommendations = {
            'critical': 'EVITAR COMBINAÇÃO - Risco de reação grave. Consulte médico IMEDIATAMENTE.',
            'high': 'Usar com EXTREMA CAUTELA - Monitoramento médico rigoroso necessário.',
            'medium': 'Usar com cautela - Monitorar sinais e sintomas. Informar médico.',
            'low': 'Risco mínimo - Manter acompanhamento médico de rotina.'
        }
        return recommendations.get(severity, 'Consultar profissional de saúde.')

    def _evaluate_patient_risk_factors(
        self,
        adverse_reactions: List[Dict[str, Any]],
        age: int,
        pregnant: bool,
        conditions: List[str],
        current_meds: List[str]
    ) -> Dict[str, int]:
        """
        Avaliar se o perfil do paciente tem fatores de risco
        para as reações adversas do medicamento
        """
        high_risk_count = 0
        critical_risk_count = 0

        # Juntar condições e características do paciente
        patient_profile = []

        if age >= 65:
            patient_profile.extend(['idosos', 'idade >65 anos', 'idade >60 anos'])

        if pregnant:
            patient_profile.append('gravidez')

        # Adicionar condições
        for condition in conditions:
            condition_lower = condition.lower()
            patient_profile.append(condition_lower)

            # Mapear condições para fatores de risco
            if 'hipertensão' in condition_lower or 'pressão alta' in condition_lower:
                patient_profile.extend(['hipertensão', 'insuficiência cardíaca'])
            if 'diabetes' in condition_lower:
                patient_profile.extend(['diabetes', 'insuficiência renal'])
            if 'renal' in condition_lower or 'rim' in condition_lower:
                patient_profile.extend(['insuficiência renal', 'insuficiência renal prévia'])
            if 'cardíaca' in condition_lower or 'coração' in condition_lower:
                patient_profile.append('cardiopatia')

        # Medicamentos em uso também são fatores de risco
        for med in current_meds:
            med_lower = med.lower()
            if any(x in med_lower for x in ['varfarina', 'warfarin', 'anticoagulante']):
                patient_profile.append('uso concomitante de anticoagulantes')

        # Verificar se reações adversas têm fatores de risco relevantes
        for reaction in adverse_reactions:
            risk_factors = reaction.get('risk_factors', [])
            severity = reaction.get('severity', '').lower()

            # Verificar se algum fator de risco do paciente está na lista
            matched_risk_factors = []
            for patient_factor in patient_profile:
                for reaction_factor in risk_factors:
                    if patient_factor.lower() in reaction_factor.lower() or reaction_factor.lower() in patient_factor.lower():
                        matched_risk_factors.append(reaction_factor)
                        break

            # Contar baseado em severidade
            if matched_risk_factors:
                if 'crítica' in severity or 'grave' in severity:
                    critical_risk_count += 1
                elif 'moderada' in severity or 'alta' in severity:
                    high_risk_count += 1

        return {
            'high_risk_count': high_risk_count,
            'critical_risk_count': critical_risk_count
        }

    def _check_dosage_adjustments(
        self,
        medication: str,
        age: int,
        weight: Optional[float],
        conditions: List[str]
    ) -> List[Dict[str, Any]]:
        """Verificar necessidade de ajustes de dosagem"""
        adjustments = []

        # Ajuste por idade (idosos)
        if age >= 65:
            adjustments.append({
                'reason': 'Paciente idoso (≥65 anos)',
                'recommendation': 'Considerar dose reduzida. Idosos têm metabolismo mais lento.',
                'adjustment_type': 'dose_reduction'
            })

        # Ajuste por idade (crianças)
        if age < 18:
            adjustments.append({
                'reason': f'Paciente pediátrico ({age} anos)',
                'recommendation': 'Calcular dose baseada em peso corporal (mg/kg). Consultar pediatra.',
                'adjustment_type': 'pediatric_dosing'
            })

        # Ajuste por condições renais
        if any(cond in ' '.join(conditions).lower() for cond in ['renal', 'rim', 'kidney']):
            adjustments.append({
                'reason': 'Insuficiência renal',
                'recommendation': 'Ajustar dose baseado em clearance de creatinina. Monitorar função renal.',
                'adjustment_type': 'renal_impairment'
            })

        # Ajuste por condições hepáticas
        if any(cond in ' '.join(conditions).lower() for cond in ['hepática', 'liver', 'fígado']):
            adjustments.append({
                'reason': 'Insuficiência hepática',
                'recommendation': 'Reduzir dose. Monitorar enzimas hepáticas regularmente.',
                'adjustment_type': 'hepatic_impairment'
            })

        return adjustments

    def _get_common_adverse_reactions(self, medication: str) -> List[Dict[str, Any]]:
        """
        Retornar reações adversas específicas do medicamento
        Base de conhecimento expandida por classe farmacológica
        """
        med_lower = medication.lower()
        reactions = []

        # === ANTI-INFLAMATÓRIOS (AINEs) ===
        if any(med in med_lower for med in ['ibuprofen', 'ibuprofeno', 'aspirin', 'aspirina', 'diclofenac', 'naproxen']):
            reactions.extend([
                {
                    'reaction': 'Irritação gastrointestinal',
                    'description': 'Dor epigástrica, náuseas, azia, possível úlcera péptica',
                    'frequency': 'Muito comum (>10%)',
                    'severity': 'Moderada a grave',
                    'risk_factors': ['uso prolongado', 'história de úlcera', 'uso concomitante de anticoagulantes']
                },
                {
                    'reaction': 'Disfunção renal',
                    'description': 'Redução da filtração glomerular, retenção de líquidos',
                    'frequency': 'Comum (1-10%)',
                    'severity': 'Moderada',
                    'risk_factors': ['idosos', 'desidratação', 'insuficiência renal prévia']
                },
                {
                    'reaction': 'Aumento de pressão arterial',
                    'description': 'Elevação da pressão arterial, edema periférico',
                    'frequency': 'Comum (1-10%)',
                    'severity': 'Moderada',
                    'risk_factors': ['hipertensão', 'insuficiência cardíaca']
                }
            ])

        # === ANTICOAGULANTES ===
        elif any(med in med_lower for med in ['warfarin', 'varfarina', 'marevan']):
            reactions.extend([
                {
                    'reaction': 'Sangramento',
                    'description': 'Hemorragias (nasal, gengival, hematomas, sangue na urina/fezes)',
                    'frequency': 'Comum (1-10%)',
                    'severity': 'Grave',
                    'risk_factors': ['INR elevado', 'trauma', 'cirurgia recente', 'idade >65 anos']
                },
                {
                    'reaction': 'Necrose cutânea',
                    'description': 'Necrose de pele e tecido subcutâneo (raro)',
                    'frequency': 'Raro (<0.1%)',
                    'severity': 'Grave',
                    'risk_factors': ['deficiência de proteína C/S', 'doses altas iniciais']
                }
            ])

        # === ANTIDIABÉTICOS (METFORMINA) ===
        elif any(med in med_lower for med in ['metformin', 'metformina', 'glifage']):
            reactions.extend([
                {
                    'reaction': 'Distúrbios gastrointestinais',
                    'description': 'Diarreia, náuseas, vômitos, flatulência, gosto metálico',
                    'frequency': 'Muito comum (>10%)',
                    'severity': 'Leve a moderada',
                    'risk_factors': ['início de tratamento', 'doses altas']
                },
                {
                    'reaction': 'Acidose lática',
                    'description': 'Acúmulo de ácido lático (EMERGÊNCIA MÉDICA)',
                    'frequency': 'Muito raro (<0.01%)',
                    'severity': 'Crítica',
                    'risk_factors': ['insuficiência renal', 'insuficiência hepática', 'desidratação', 'sepse']
                },
                {
                    'reaction': 'Deficiência de vitamina B12',
                    'description': 'Redução da absorção de B12 (uso prolongado)',
                    'frequency': 'Comum (1-10%)',
                    'severity': 'Leve',
                    'risk_factors': ['uso prolongado >4 anos', 'não suplementação']
                }
            ])

        # === ESTATINAS ===
        elif any(med in med_lower for med in ['atorvastatin', 'atorvastatina', 'simvastatin', 'simvastatina', 'rosuva']):
            reactions.extend([
                {
                    'reaction': 'Mialgia e dor muscular',
                    'description': 'Dor muscular, fraqueza, cãibras',
                    'frequency': 'Comum (1-10%)',
                    'severity': 'Leve a moderada',
                    'risk_factors': ['doses altas', 'interações medicamentosas', 'idosos']
                },
                {
                    'reaction': 'Rabdomiólise',
                    'description': 'Destruição muscular grave com liberação de mioglobina',
                    'frequency': 'Raro (<0.1%)',
                    'severity': 'Crítica',
                    'risk_factors': ['doses altas', 'interação com fibratos', 'hipotireoidismo']
                },
                {
                    'reaction': 'Elevação de enzimas hepáticas',
                    'description': 'Aumento de ALT/AST',
                    'frequency': 'Comum (1-10%)',
                    'severity': 'Leve a moderada',
                    'risk_factors': ['doença hepática prévia', 'uso concomitante de álcool']
                }
            ])

        # === ANTIDEPRESSIVOS (ISRS) ===
        elif any(med in med_lower for med in ['fluoxetine', 'fluoxetina', 'sertraline', 'sertralina', 'prozac', 'zoloft']):
            reactions.extend([
                {
                    'reaction': 'Síndrome serotoninérgica',
                    'description': 'Agitação, confusão, taquicardia, hipertermia, tremores',
                    'frequency': 'Raro (<0.1%)',
                    'severity': 'Grave',
                    'risk_factors': ['uso concomitante de outros serotoninérgicos', 'tramadol', 'IMAOs']
                },
                {
                    'reaction': 'Disfunção sexual',
                    'description': 'Diminuição da libido, disfunção erétil, anorgasmia',
                    'frequency': 'Muito comum (>10%)',
                    'severity': 'Moderada',
                    'risk_factors': ['doses elevadas', 'uso prolongado']
                },
                {
                    'reaction': 'Insônia ou sonolência',
                    'description': 'Alterações no padrão de sono',
                    'frequency': 'Comum (1-10%)',
                    'severity': 'Leve',
                    'risk_factors': ['início de tratamento']
                }
            ])

        # === BENZODIAZEPÍNICOS ===
        elif any(med in med_lower for med in ['diazepam', 'clonazepam', 'alprazolam', 'rivotril', 'valium']):
            reactions.extend([
                {
                    'reaction': 'Sedação e sonolência',
                    'description': 'Sonolência diurna, diminuição de reflexos, fadiga',
                    'frequency': 'Muito comum (>10%)',
                    'severity': 'Moderada',
                    'risk_factors': ['idosos', 'doses altas', 'uso de álcool']
                },
                {
                    'reaction': 'Dependência e abstinência',
                    'description': 'Dependência física e psicológica, síndrome de abstinência',
                    'frequency': 'Comum (1-10%)',
                    'severity': 'Grave',
                    'risk_factors': ['uso prolongado >4 semanas', 'doses altas', 'histórico de dependência']
                },
                {
                    'reaction': 'Prejuízo cognitivo',
                    'description': 'Dificuldade de concentração, amnésia anterógrada',
                    'frequency': 'Comum (1-10%)',
                    'severity': 'Moderada',
                    'risk_factors': ['idosos', 'doses altas']
                }
            ])

        # === PARACETAMOL/ACETAMINOFENO ===
        elif any(med in med_lower for med in ['paracetamol', 'acetaminophen', 'tylenol']):
            reactions.extend([
                {
                    'reaction': 'Hepatotoxicidade',
                    'description': 'Lesão hepática (doses >4g/dia ou intoxicação)',
                    'frequency': 'Raro em doses terapêuticas',
                    'severity': 'Crítica (em overdose)',
                    'risk_factors': ['doses >4g/dia', 'uso de álcool', 'doença hepática', 'jejum']
                },
                {
                    'reaction': 'Reações alérgicas',
                    'description': 'Rash cutâneo, urticária (raro)',
                    'frequency': 'Raro (<0.1%)',
                    'severity': 'Leve a moderada',
                    'risk_factors': ['histórico de alergias']
                }
            ])

        # === ANTIBIÓTICOS (QUINOLONAS) ===
        elif any(med in med_lower for med in ['levofloxacin', 'ciprofloxacin', 'norfloxacin']):
            reactions.extend([
                {
                    'reaction': 'Tendinite e ruptura de tendão',
                    'description': 'Inflamação e possível ruptura do tendão de Aquiles',
                    'frequency': 'Incomum (0.1-1%)',
                    'severity': 'Grave',
                    'risk_factors': ['idade >60 anos', 'corticoides', 'atividade física intensa']
                },
                {
                    'reaction': 'Fotossensibilidade',
                    'description': 'Aumento da sensibilidade à luz solar',
                    'frequency': 'Comum (1-10%)',
                    'severity': 'Leve a moderada',
                    'risk_factors': ['exposição solar']
                },
                {
                    'reaction': 'Prolongamento do intervalo QT',
                    'description': 'Risco de arritmias cardíacas',
                    'frequency': 'Raro (<0.1%)',
                    'severity': 'Grave',
                    'risk_factors': ['cardiopatia', 'uso de outros QT prolongadores', 'distúrbios eletrolíticos']
                }
            ])

        # === FALLBACK GENÉRICO (para medicamentos não mapeados) ===
        else:
            reactions.append({
                'reaction': 'Reações adversas gerais',
                'description': 'Consulte a bula para lista completa de reações adversas específicas',
                'frequency': 'Variável',
                'severity': 'Variável',
                'risk_factors': ['sensibilidade individual', 'interações medicamentosas']
            })

        return reactions

    def _generate_analysis_notes(
        self,
        medication: str,
        risk_level: str,
        interaction_count: int,
        contraindication_count: int,
        age: int,
        pregnant: bool
    ) -> str:
        """Gerar notas descritivas da análise"""
        notes = []

        # Cabeçalho
        notes.append(f"## Análise Clínica - {medication}\n")

        # Resumo de risco
        risk_descriptions = {
            'critical': '🔴 **RISCO CRÍTICO** - Uso contraindicado ou requer atenção médica IMEDIATA',
            'high': '🟠 **RISCO ALTO** - Uso requer supervisão médica rigorosa e monitoramento',
            'medium': '🟡 **RISCO MODERADO** - Usar com cautela e acompanhamento médico',
            'low': '🟢 **RISCO BAIXO** - Perfil de segurança aceitável com acompanhamento de rotina'
        }
        notes.append(risk_descriptions.get(risk_level, ''))
        notes.append("")

        # Estatísticas
        if interaction_count > 0 or contraindication_count > 0:
            notes.append("### Alertas Identificados:")
            if contraindication_count > 0:
                notes.append(f"- **{contraindication_count}** contraindicação(ões) detectada(s)")
            if interaction_count > 0:
                notes.append(f"- **{interaction_count}** interação(ões) medicamentosa(s) encontrada(s)")
            notes.append("")

        # Populações especiais
        if age >= 65 or age < 18 or pregnant:
            notes.append("### População Especial:")
            if age >= 65:
                notes.append("- **Paciente idoso**: Requer atenção especial para dosagem")
            if age < 18:
                notes.append("- **Paciente pediátrico**: Dose deve ser calculada por profissional")
            if pregnant:
                notes.append("- **GESTANTE**: Avaliar risco/benefício com obstetra")
            notes.append("")

        # Disclaimer
        notes.append("---")
        notes.append("**IMPORTANTE**: Esta análise é informativa e não substitui consulta médica. "
                    "Sempre consulte um profissional de saúde antes de iniciar, alterar ou interromper "
                    "qualquer tratamento.")

        return "\n".join(notes)
