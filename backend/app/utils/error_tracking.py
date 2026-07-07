"""
Error tracking via SDK compatível com Sentry (GlitchTip self-hosted).

O backend de destino é definido apenas pelo SENTRY_DSN (env): hoje um
GlitchTip local (docker-compose.glitchtip.yml); trocar de backend no
lançamento é trocar o DSN — nenhuma mudança de código.

SECURITY/LGPD: este app processa PHI. Os guardas send_default_pii=False e
include_local_variables=False são obrigatórios — variáveis locais de stack
frames (patient_data, medication_text, state) carregariam dados de paciente
para dentro dos eventos de erro.
"""

import logging

logger = logging.getLogger(__name__)


def setup_error_tracking(settings) -> bool:
    """
    Inicializa o error tracking se SENTRY_DSN estiver configurado.

    Args:
        settings: instância de Settings (usa sentry_dsn, environment,
            app_version e sentry_traces_sample_rate)

    Returns:
        True se o SDK foi inicializado; False em no-op (sem DSN ou SDK
        indisponível). Nunca levanta exceção — error tracking não pode
        derrubar a aplicação.
    """
    dsn = getattr(settings, "sentry_dsn", None)
    if not dsn:
        logger.info("Error tracking desabilitado (SENTRY_DSN não configurado)")
        return False

    try:
        import sentry_sdk
    except ImportError:
        logger.warning(
            "SENTRY_DSN configurado mas sentry-sdk não está instalado — "
            "error tracking desabilitado"
        )
        return False

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=settings.environment,
            release=f"medsafe@{settings.app_version}",
            traces_sample_rate=getattr(settings, "sentry_traces_sample_rate", 0.0),
            # LGPD/PHI: nunca enviar PII implícito nem variáveis locais de
            # stack frames (contêm patient_data/medication_text).
            send_default_pii=False,
            include_local_variables=False,
        )
    except Exception as e:
        logger.error(f"Falha ao inicializar error tracking: {e}")
        return False

    logger.info(
        "Error tracking inicializado (environment=%s, release=medsafe@%s)",
        settings.environment,
        settings.app_version,
    )
    return True
