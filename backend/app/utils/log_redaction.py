"""
Redaction Filter para Logs do MedSafe.

SECURITY: Sanitização centralizada de PHI/PII em logs para compliance LGPD.
Este módulo DEVE ser aplicado a TODOS os handlers de logging em produção.

Padrões detectados e redatados:
- CPF, CNPJ, RG
- E-mails, telefones
- Nomes de medicamentos em contexto sensível
- Dados de paciente (idade, peso, condições)
- Chaves/tokens/senhas
"""

import re
import logging
from typing import Any, Dict, List, Optional, Pattern, Set
from dataclasses import dataclass, field


# ============================================================================
# Padrões de dados sensíveis (PHI/PII) - Brasil/LGPD
# ============================================================================

@dataclass(frozen=True)
class RedactionPattern:
    """Define um padrão de redação com regex e substituição."""
    name: str
    pattern: Pattern
    replacement: str
    priority: int = 0  # Maior prioridade = processado primeiro


# Padrões de identificação pessoal
CPF_PATTERN = RedactionPattern(
    name="cpf",
    pattern=re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'),
    replacement="[CPF_REDACTED]",
    priority=100,
)

CNPJ_PATTERN = RedactionPattern(
    name="cnpj",
    pattern=re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b'),
    replacement="[CNPJ_REDACTED]",
    priority=100,
)

RG_PATTERN = RedactionPattern(
    name="rg",
    pattern=re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[0-9Xx]\b'),
    replacement="[RG_REDACTED]",
    priority=90,
)

# Contato
EMAIL_PATTERN = RedactionPattern(
    name="email",
    pattern=re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    replacement="[EMAIL_REDACTED]",
    priority=80,
)

PHONE_BR_PATTERN = RedactionPattern(
    name="phone_br",
    pattern=re.compile(r'\b(?:\+55\s?)?(?:\(?\d{2}\)?[\s.-]?)?\d{4,5}[\s.-]?\d{4}\b'),
    replacement="[PHONE_REDACTED]",
    priority=80,
)

# Dados médicos sensíveis
PATIENT_AGE_PATTERN = RedactionPattern(
    name="patient_age",
    pattern=re.compile(r'(?:idade|age|paciente)[:\s=]*\d{1,3}(?:\s*anos?)?', re.IGNORECASE),
    replacement="[PATIENT_AGE_REDACTED]",
    priority=70,
)

PATIENT_WEIGHT_PATTERN = RedactionPattern(
    name="patient_weight",
    pattern=re.compile(r'(?:peso|weight)[:\s=]*\d{1,3}(?:\.\d+)?(?:\s*kg)?', re.IGNORECASE),
    replacement="[PATIENT_WEIGHT_REDACTED]",
    priority=70,
)

# Tokens e credenciais
JWT_PATTERN = RedactionPattern(
    name="jwt",
    pattern=re.compile(r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*'),
    replacement="[JWT_REDACTED]",
    priority=100,
)

API_KEY_PATTERN = RedactionPattern(
    name="api_key",
    pattern=re.compile(r'(?:api[_-]?key|apikey|token|secret|password|senha)[:\s=]["\']*[A-Za-z0-9_\-]{8,}["\']*', re.IGNORECASE),
    replacement="[CREDENTIAL_REDACTED]",
    priority=100,
)

BEARER_TOKEN_PATTERN = RedactionPattern(
    name="bearer",
    pattern=re.compile(r'Bearer\s+[A-Za-z0-9_\-\.]+', re.IGNORECASE),
    replacement="Bearer [TOKEN_REDACTED]",
    priority=100,
)

# Hash de senha (BCrypt, Argon2, etc)
PASSWORD_HASH_PATTERN = RedactionPattern(
    name="password_hash",
    pattern=re.compile(r'\$2[aby]?\$\d{1,2}\$[A-Za-z0-9./]{53}|\$argon2[id]+\$[^\s]+'),
    replacement="[HASH_REDACTED]",
    priority=100,
)

# Dados clínicos em JSON/dict
MEDS_IN_USE_PATTERN = RedactionPattern(
    name="meds_in_use",
    pattern=re.compile(r'"meds_in_use"\s*:\s*\[[^\]]*\]', re.IGNORECASE),
    replacement='"meds_in_use": [REDACTED]',
    priority=60,
)

CONDITIONS_PATTERN = RedactionPattern(
    name="conditions",
    pattern=re.compile(r'"(?:conditions|comorbidades|allergies|alergias)"\s*:\s*\[[^\]]*\]', re.IGNORECASE),
    replacement='"conditions": [REDACTED]',
    priority=60,
)

CID_CODES_PATTERN = RedactionPattern(
    name="cid_codes",
    pattern=re.compile(r'"cid_codes"\s*:\s*\[[^\]]*\]', re.IGNORECASE),
    replacement='"cid_codes": [REDACTED]',
    priority=60,
)

# Cartão de crédito (PCI-DSS)
CREDIT_CARD_PATTERN = RedactionPattern(
    name="credit_card",
    pattern=re.compile(r'\b(?:\d{4}[\s-]?){3}\d{4}\b'),
    replacement="[CARD_REDACTED]",
    priority=100,
)


# ============================================================================
# Configuração de padrões ativos
# ============================================================================

# Padrões padrão para produção
DEFAULT_PATTERNS: List[RedactionPattern] = [
    # Alta prioridade (credentials/tokens)
    JWT_PATTERN,
    API_KEY_PATTERN,
    BEARER_TOKEN_PATTERN,
    PASSWORD_HASH_PATTERN,
    CREDIT_CARD_PATTERN,
    # Identificação pessoal
    CPF_PATTERN,
    CNPJ_PATTERN,
    RG_PATTERN,
    EMAIL_PATTERN,
    PHONE_BR_PATTERN,
    # Dados médicos
    PATIENT_AGE_PATTERN,
    PATIENT_WEIGHT_PATTERN,
    MEDS_IN_USE_PATTERN,
    CONDITIONS_PATTERN,
    CID_CODES_PATTERN,
]

# Keywords que acionam redação adicional do contexto
SENSITIVE_KEYWORDS: Set[str] = {
    "password", "senha", "secret", "token", "api_key",
    "cpf", "rg", "cnpj", "credit_card", "cartao",
    "patient_data", "dados_paciente", "medicamento",
    "medication", "diagnosis", "diagnostico",
    "crm", "crf", "prontuario",
}


# ============================================================================
# Filtro de Redação
# ============================================================================

class PHIRedactionFilter(logging.Filter):
    """
    Filtro de logging que redacta dados sensíveis (PHI/PII).
    
    Uso:
        handler.addFilter(PHIRedactionFilter())
        
    Ou globalmente:
        logging.root.addFilter(PHIRedactionFilter())
    """
    
    def __init__(
        self,
        patterns: Optional[List[RedactionPattern]] = None,
        enabled: bool = True,
        name: str = "",
    ):
        super().__init__(name)
        self.enabled = enabled
        self.patterns = sorted(
            patterns or DEFAULT_PATTERNS,
            key=lambda p: -p.priority  # Maior prioridade primeiro
        )
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Processa o record de log, redatando dados sensíveis.
        
        Retorna True para permitir o log (após sanitização).
        """
        if not self.enabled:
            return True
        
        # Redactar mensagem principal
        if record.msg:
            record.msg = self._redact_string(str(record.msg))
        
        # Redactar args se existirem
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, (tuple, list)):
                record.args = tuple(self._redact_value(arg) for arg in record.args)
        
        # Redactar campos extras comuns
        for attr in ('extra_data', 'audit_data', 'details'):
            if hasattr(record, attr):
                value = getattr(record, attr)
                if value:
                    setattr(record, attr, self._redact_value(value))
        
        return True
    
    def _redact_string(self, text: str) -> str:
        """Aplica todos os padrões de redação a uma string."""
        if not text:
            return text
        
        result = text
        for pattern in self.patterns:
            result = pattern.pattern.sub(pattern.replacement, result)
        
        return result
    
    def _redact_value(self, value: Any) -> Any:
        """Redacta um valor de qualquer tipo."""
        if value is None:
            return value
        
        if isinstance(value, str):
            return self._redact_string(value)
        
        if isinstance(value, dict):
            return self._redact_dict(value)
        
        if isinstance(value, (list, tuple)):
            return type(value)(self._redact_value(item) for item in value)
        
        # Para outros tipos, converter para string e redactar
        try:
            return self._redact_string(str(value))
        except Exception:
            return "[REDACTION_ERROR]"
    
    def _redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redacta um dicionário, tratando chaves sensíveis."""
        result = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Chaves totalmente sensíveis - substituir valor inteiro
            if any(kw in key_lower for kw in ('password', 'senha', 'secret', 'token', 'api_key', 'hash')):
                result[key] = "[REDACTED]"
            
            # Chaves com dados médicos - redactar conteúdo
            elif any(kw in key_lower for kw in ('patient', 'medication', 'meds', 'condition', 'allerg', 'cid')):
                if isinstance(value, (list, dict)):
                    result[key] = "[PHI_REDACTED]"
                else:
                    result[key] = self._redact_value(value)
            
            # Outras chaves - redactar recursivamente
            else:
                result[key] = self._redact_value(value)
        
        return result


# ============================================================================
# Funções auxiliares
# ============================================================================

def redact_sensitive_data(text: str, patterns: Optional[List[RedactionPattern]] = None) -> str:
    """
    Função utilitária para redactar dados sensíveis de uma string.
    
    Args:
        text: Texto a ser sanitizado
        patterns: Lista de padrões (usa DEFAULT_PATTERNS se não fornecido)
        
    Returns:
        Texto sanitizado
    """
    if not text:
        return text
    
    patterns = patterns or DEFAULT_PATTERNS
    result = text
    
    for pattern in sorted(patterns, key=lambda p: -p.priority):
        result = pattern.pattern.sub(pattern.replacement, result)
    
    return result


def redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redacta um dicionário inteiro.
    
    Args:
        data: Dicionário com dados potencialmente sensíveis
        
    Returns:
        Dicionário sanitizado
    """
    filter_instance = PHIRedactionFilter()
    return filter_instance._redact_dict(data)


def setup_log_redaction(logger: Optional[logging.Logger] = None, enabled: bool = True) -> PHIRedactionFilter:
    """
    Configura redação de PHI/PII em um logger.
    
    Args:
        logger: Logger específico ou None para root logger
        enabled: Se a redação está habilitada
        
    Returns:
        Instância do filtro aplicado
    """
    target_logger = logger or logging.getLogger()
    
    # Remover filtros de redação existentes
    for f in target_logger.filters[:]:
        if isinstance(f, PHIRedactionFilter):
            target_logger.removeFilter(f)
    
    # Adicionar novo filtro
    redaction_filter = PHIRedactionFilter(enabled=enabled)
    target_logger.addFilter(redaction_filter)
    
    # Também aplicar a todos os handlers
    for handler in target_logger.handlers:
        for f in handler.filters[:]:
            if isinstance(f, PHIRedactionFilter):
                handler.removeFilter(f)
        handler.addFilter(PHIRedactionFilter(enabled=enabled))
    
    return redaction_filter


# ============================================================================
# Exportações
# ============================================================================

__all__ = [
    "PHIRedactionFilter",
    "RedactionPattern",
    "redact_sensitive_data",
    "redact_dict",
    "setup_log_redaction",
    "DEFAULT_PATTERNS",
    "SENSITIVE_KEYWORDS",
]

