"""
Serviço de IA para análise de contra-indicações usando AG2/Ollama
"""

import json
import requests
from typing import Dict, List, Any, Optional
from models.schemas import (
    PatientData, MedicationInfo, AnalysisResult, 
    Contraindication, DrugInteraction, AdverseReaction, 
    Recommendation, RiskLevel
)
from services.drug_service import DrugService
import os
from datetime import datetime

class AIService:
    """Serviço para análise de IA com AG2/Ollama local"""
    
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.api_key = os.getenv("OLLAMA_API_KEY", "ollama")
        self.text_model = os.getenv("OLLAMA_TEXT_MODEL", "qwen3:4b")
        self.vision_model = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
        self.drug_service = DrugService()
        
        # Configuração para compatibilidade OpenAI
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
    async def analyze_contraindications(
        self, 
        patient: PatientData, 
        medication: MedicationInfo,
        session_id: str
    ) -> AnalysisResult:
        """Análise principal de contra-indicações usando IA"""
        
        try:
            # Buscar dados específicos do medicamento
            contraindications = await self.drug_service.get_contraindications(
                medication.active_ingredient, 
                patient.conditions
            )
            
            drug_interactions = await self.drug_service.get_drug_interactions(
                medication.active_ingredient,
                patient.current_medications
            )
            
            # Construir prompt para IA
            prompt = self._build_analysis_prompt(patient, medication)
            
            # Obter análise da IA
            ai_response = await self._query_ollama(prompt)
            
            # Processar resposta da IA
            ai_analysis = self._parse_ai_response(ai_response)
            
            # Combinar dados do banco com análise da IA
            combined_analysis = self._combine_analysis(
                contraindications,
                drug_interactions,
                ai_analysis,
                patient,
                medication
            )
            
            # Determinar risco geral
            overall_risk = self._calculate_overall_risk(combined_analysis)
            
            # Gerar recomendações
            recommendations = self._generate_recommendations(combined_analysis, overall_risk)
            
            # Gerar resumo explicativo
            summary = self._generate_patient_summary(combined_analysis, patient, medication)
            
            return AnalysisResult(
                session_id=session_id,
                timestamp=datetime.now(),
                patient=patient,
                medication=medication,
                contraindications=combined_analysis.get("contraindications", []),
                drug_interactions=combined_analysis.get("interactions", []),
                adverse_reactions=combined_analysis.get("adverse_reactions", []),
                recommendations=recommendations,
                overall_risk=overall_risk,
                summary=summary
            )
            
        except Exception as e:
            print(f"Erro na análise de IA: {e}")
            # Retornar análise básica em caso de erro
            return self._fallback_analysis(patient, medication, session_id)
    
    def _build_analysis_prompt(self, patient: PatientData, medication: MedicationInfo) -> str:
        """Construir prompt específico para análise farmacológica"""
        
        prompt = f"""
ANÁLISE DE FARMACOVIGILÂNCIA - DIRETRIZES OMS E ANVISA

Você é um especialista em farmacovigilância seguindo rigorosamente as diretrizes da OMS e regulamentações da ANVISA (RDC 47/2009, 94/2008, 96/2008).

DADOS DO PACIENTE:
- Idade: {patient.age} anos
- Gênero: {patient.gender}
- Peso: {patient.weight or 'não informado'} kg
- Condições médicas: {', '.join(patient.conditions) if patient.conditions else 'nenhuma informada'}
- Alergias conhecidas: {', '.join(patient.allergies) if patient.allergies else 'nenhuma informada'}
- Medicamentos atuais: {', '.join(patient.current_medications) if patient.current_medications else 'nenhum'}
- Suplementos: {', '.join(patient.supplements) if patient.supplements else 'nenhum'}
- Uso de álcool: {'sim' if patient.alcohol_use else 'não'}
- Tabagismo: {'sim' if patient.smoking else 'não'}
- Gravidez: {patient.pregnancy if patient.pregnancy is not None else 'não aplicável'}
- Amamentação: {patient.breastfeeding if patient.breastfeeding is not None else 'não aplicável'}
- Função renal: {patient.kidney_function or 'não informada'}
- Função hepática: {patient.liver_function or 'não informada'}

MEDICAMENTO ANALISADO:
- Nome: {medication.name}
- Princípio ativo: {medication.active_ingredient}
- Classe terapêutica: {medication.therapeutic_class or 'não classificada'}

DIRETRIZES A SEGUIR:
1. OMS - Classificação de reações adversas e interações medicamentosas
2. ANVISA - RDC 47/2009 (rotulagem), RDC 94/2008 (bulas), RDC 96/2008 (propagandas)
3. Farmacocinética e farmacodinâmica específicas do princípio ativo
4. Populações especiais (idosos, gestantes, pediatria, insuficiência renal/hepática)

ANÁLISE SOLICITADA:
Forneça uma análise estruturada em JSON com:

1. CONTRAINDICAÇÕES FORMAIS:
   - Baseadas nas condições do paciente
   - Classificação por gravidade (absoluta, relativa)
   - Fonte regulatória (OMS/ANVISA)

2. INTERAÇÕES MEDICAMENTOSAS:
   - Tipo: farmacocinética ou farmacodinâmica
   - Mecanismo de ação
   - Efeito clínico esperado
   - Classificação: potencialização (entourage) ou antagonismo

3. REAÇÕES ADVERSAS ESPERADAS:
   - Baseadas no perfil do paciente
   - Frequência segundo bula ANVISA
   - Fatores de risco presentes

4. RECOMENDAÇÕES CLÍNICAS:
   - Monitoramento necessário
   - Ajustes de dose se aplicável
   - Alternativas terapêuticas se contraindicado

Responda APENAS com JSON válido seguindo esta estrutura:
{{
    "contraindications": [
        {{
            "type": "string",
            "description": "string",
            "severity": "absoluta|relativa",
            "source": "OMS|ANVISA|Literatura",
            "recommendation": "string"
        }}
    ],
    "interactions": [
        {{
            "drug": "string",
            "type": "farmacocinética|farmacodinâmica",
            "effect": "string",
            "severity": "leve|moderada|grave",
            "mechanism": "string",
            "recommendation": "string"
        }}
    ],
    "adverse_reactions": [
        {{
            "reaction": "string",
            "frequency": "muito comum|comum|incomum|rara|muito rara",
            "risk_factors": ["string"],
            "description": "string"
        }}
    ],
    "special_populations": {{
        "elderly": "string",
        "pregnancy": "string",
        "breastfeeding": "string",
        "renal_impairment": "string",
        "hepatic_impairment": "string"
    }},
    "monitoring": [
        {{
            "parameter": "string",
            "frequency": "string",
            "rationale": "string"
        }}
    ]
}}
"""
        return prompt
    
    async def _query_ollama(self, prompt: str, use_vision: bool = False, image_data: str = None) -> str:
        """Consultar API do Ollama local usando formato OpenAI"""
        try:
            model = self.vision_model if use_vision else self.text_model
            
            # Preparar mensagens
            messages = []
            
            if use_vision and image_data:
                # Para modelo de visão com imagem
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                })
            else:
                # Para modelo de texto apenas
                messages.append({
                    "role": "user",
                    "content": prompt
                })
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2048,
                "top_p": 0.9
            }
            
            response = requests.post(
                f"{self.ollama_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                print(f"Erro na API Ollama: {response.status_code} - {response.text}")
                return ""
                
        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão com Ollama: {e}")
            return ""
        except Exception as e:
            print(f"Erro inesperado no Ollama: {e}")
            return ""
    
    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """Analisar resposta JSON da IA"""
        try:
            # Tentar extrair JSON da resposta
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                print("JSON não encontrado na resposta da IA")
                return {}
                
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON da IA: {e}")
            return {}
        except Exception as e:
            print(f"Erro ao processar resposta da IA: {e}")
            return {}
    
    def _combine_analysis(
        self, 
        db_contraindications: List[Contraindication],
        db_interactions: List[DrugInteraction],
        ai_analysis: Dict[str, Any],
        patient: PatientData,
        medication: MedicationInfo
    ) -> Dict[str, Any]:
        """Combinar análise do banco de dados com IA"""
        
        combined = {
            "contraindications": [],
            "interactions": [],
            "adverse_reactions": []
        }
        
        # Adicionar contraindicações do banco
        combined["contraindications"].extend(db_contraindications)
        
        # Adicionar contraindicações da IA
        ai_contraindications = ai_analysis.get("contraindications", [])
        for ai_contra in ai_contraindications:
            severity = ai_contra.get("severity", "relativa")
            risk_level = RiskLevel.HIGH if severity == "absoluta" else RiskLevel.MEDIUM
            
            combined["contraindications"].append(
                Contraindication(
                    type=ai_contra.get("type", "IA Analysis"),
                    description=ai_contra.get("description", ""),
                    risk_level=risk_level,
                    source=ai_contra.get("source", "IA/AG2"),
                    recommendation=ai_contra.get("recommendation", "")
                )
            )
        
        # Adicionar interações do banco
        combined["interactions"].extend(db_interactions)
        
        # Adicionar interações da IA
        ai_interactions = ai_analysis.get("interactions", [])
        for ai_inter in ai_interactions:
            severity = ai_inter.get("severity", "moderada")
            risk_level = self._map_severity_to_risk_level(severity)
            
            combined["interactions"].append(
                DrugInteraction(
                    interacting_drug=ai_inter.get("drug", ""),
                    interaction_type=ai_inter.get("type", ""),
                    effect=ai_inter.get("effect", ""),
                    risk_level=risk_level,
                    mechanism=ai_inter.get("mechanism", ""),
                    recommendation=ai_inter.get("recommendation", "")
                )
            )
        
        # Adicionar reações adversas da IA
        ai_reactions = ai_analysis.get("adverse_reactions", [])
        for ai_reaction in ai_reactions:
            combined["adverse_reactions"].append(
                AdverseReaction(
                    reaction=ai_reaction.get("reaction", ""),
                    frequency=ai_reaction.get("frequency", ""),
                    severity=self._map_frequency_to_severity(ai_reaction.get("frequency", "")),
                    risk_factors=ai_reaction.get("risk_factors", []),
                    description=ai_reaction.get("description", "")
                )
            )
        
        return combined
    
    def _calculate_overall_risk(self, analysis: Dict[str, Any]) -> RiskLevel:
        """Calcular risco geral baseado na análise"""
        
        max_risk = RiskLevel.LOW
        
        # Verificar contraindicações
        for contraind in analysis.get("contraindications", []):
            if contraind.risk_level.value == RiskLevel.CRITICAL.value:
                return RiskLevel.CRITICAL
            elif contraind.risk_level.value == RiskLevel.HIGH.value:
                max_risk = RiskLevel.HIGH
            elif contraind.risk_level.value == RiskLevel.MEDIUM.value and max_risk == RiskLevel.LOW:
                max_risk = RiskLevel.MEDIUM
        
        # Verificar interações
        for interaction in analysis.get("interactions", []):
            if interaction.risk_level.value == RiskLevel.CRITICAL.value:
                return RiskLevel.CRITICAL
            elif interaction.risk_level.value == RiskLevel.HIGH.value and max_risk != RiskLevel.CRITICAL:
                max_risk = RiskLevel.HIGH
        
        return max_risk
    
    def _generate_recommendations(self, analysis: Dict[str, Any], overall_risk: RiskLevel) -> List[Recommendation]:
        """Gerar recomendações baseadas na análise"""
        
        recommendations = []
        
        # Recomendações baseadas no risco geral
        if overall_risk == RiskLevel.CRITICAL:
            recommendations.append(
                Recommendation(
                    category="URGENTE",
                    priority=RiskLevel.CRITICAL,
                    action="Contraindicação absoluta identificada - NÃO usar este medicamento",
                    rationale="Risco significativo de reações graves ou potencialmente fatais"
                )
            )
        elif overall_risk == RiskLevel.HIGH:
            recommendations.append(
                Recommendation(
                    category="CUIDADO",
                    priority=RiskLevel.HIGH,
                    action="Uso apenas sob supervisão médica rigorosa",
                    rationale="Múltiplos fatores de risco identificados"
                )
            )
        
        # Recomendações específicas para contraindicações
        for contraind in analysis.get("contraindications", []):
            if contraind.recommendation:
                recommendations.append(
                    Recommendation(
                        category="Contraindicação",
                        priority=contraind.risk_level,
                        action=contraind.recommendation,
                        rationale=contraind.description
                    )
                )
        
        # Sempre incluir consulta médica
        recommendations.append(
            Recommendation(
                category="GERAL",
                priority=RiskLevel.HIGH,
                action="Consulte seu médico antes de usar qualquer medicamento",
                rationale="Esta é uma ferramenta de apoio informativo, não substitui consulta médica"
            )
        )
        
        return recommendations
    
    def _generate_patient_summary(
        self, 
        analysis: Dict[str, Any], 
        patient: PatientData, 
        medication: MedicationInfo
    ) -> str:
        """Gerar resumo explicativo para o paciente"""
        
        summary_parts = [
            f"**Análise para {medication.name} ({medication.active_ingredient})**\n"
        ]
        
        # Contraindicações
        contraindications = analysis.get("contraindications", [])
        if contraindications:
            summary_parts.append("⚠️ **CONTRAINDICAÇÕES IDENTIFICADAS:**")
            for contraind in contraindications:
                risk_emoji = "🔴" if contraind.risk_level == RiskLevel.CRITICAL else "🟡"
                summary_parts.append(f"{risk_emoji} {contraind.description}")
            summary_parts.append("")
        
        # Interações
        interactions = analysis.get("interactions", [])
        if interactions:
            summary_parts.append("🔄 **INTERAÇÕES MEDICAMENTOSAS:**")
            for interaction in interactions:
                summary_parts.append(f"• {interaction.effect} (com {interaction.interacting_drug})")
            summary_parts.append("")
        
        # Reações adversas
        adverse_reactions = analysis.get("adverse_reactions", [])
        if adverse_reactions:
            summary_parts.append("⚡ **POSSÍVEIS REAÇÕES ADVERSAS:**")
            for reaction in adverse_reactions:
                summary_parts.append(f"• {reaction.reaction} ({reaction.frequency})")
            summary_parts.append("")
        
        # Conclusão
        summary_parts.extend([
            "---",
            "**IMPORTANTE:** Esta análise segue diretrizes da OMS e ANVISA.",
            "**SEMPRE consulte seu médico antes de usar qualquer medicamento.**",
            "",
            "*Fonte: Análise baseada em RDC ANVISA 47/2009, 94/2008, 96/2008 e diretrizes OMS.*"
        ])
        
        return "\n".join(summary_parts)
    
    def _fallback_analysis(self, patient: PatientData, medication: MedicationInfo, session_id: str) -> AnalysisResult:
        """Análise de fallback em caso de erro na IA"""
        
        return AnalysisResult(
            session_id=session_id,
            timestamp=datetime.now(),
            patient=patient,
            medication=medication,
            contraindications=[],
            drug_interactions=[],
            adverse_reactions=[],
            recommendations=[
                Recommendation(
                    category="SISTEMA",
                    priority=RiskLevel.HIGH,
                    action="Sistema temporariamente indisponível - consulte seu médico",
                    rationale="Não foi possível completar a análise automatizada"
                )
            ],
            overall_risk=RiskLevel.MEDIUM,
            summary="Sistema temporariamente indisponível. Por favor, consulte seu médico ou farmacêutico."
        )
    
    def _map_severity_to_risk_level(self, severity: str) -> RiskLevel:
        """Mapear severidade para nível de risco"""
        severity_map = {
            "leve": RiskLevel.LOW,
            "moderada": RiskLevel.MEDIUM,
            "grave": RiskLevel.HIGH,
            "crítica": RiskLevel.CRITICAL
        }
        return severity_map.get(severity.lower(), RiskLevel.MEDIUM)
    
    def _map_frequency_to_severity(self, frequency: str) -> str:
        """Mapear frequência ANVISA para severidade"""
        frequency_map = {
            "muito comum": "leve",
            "comum": "leve",
            "incomum": "moderada",
            "rara": "grave",
            "muito rara": "grave"
        }
        return frequency_map.get(frequency.lower(), "moderada")