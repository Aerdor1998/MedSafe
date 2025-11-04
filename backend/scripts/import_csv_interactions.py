"""
Script para importar interações medicamentosas do CSV para PostgreSQL

IMPORTANTE: Este script requer variáveis de ambiente configuradas.
Crie um arquivo .env ou configure as variáveis antes de executar.

Variáveis necessárias:
- POSTGRES_HOST (padrão: localhost)
- POSTGRES_PORT (padrão: 5432)
- POSTGRES_DB (padrão: medsafe)
- POSTGRES_USER (obrigatório)
- POSTGRES_PASSWORD (obrigatório)
"""

import csv
import psycopg2
from psycopg2.extras import execute_batch
import os
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    """
    Obter conexão com banco de dados usando variáveis de ambiente.

    Raises:
        ValueError: Se variáveis obrigatórias não estiverem configuradas
    """
    # Validar variáveis obrigatórias
    required_vars = ["POSTGRES_USER", "POSTGRES_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        raise ValueError(
            f"Variáveis de ambiente obrigatórias não configuradas: "
            f"{', '.join(missing_vars)}\n"
            f"Configure-as no arquivo .env ou exporte-as no terminal."
        )

    # Configurações do banco
    db_config = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "database": os.getenv("POSTGRES_DB", "medsafe"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "sslmode": os.getenv("POSTGRES_SSLMODE", "prefer"),
    }

    logger.info(
        "🔌 Conectando ao banco: "
        f"{db_config['user']}@{db_config['host']}:"
        f"{db_config['port']}/{db_config['database']}"
    )

    try:
        return psycopg2.connect(**db_config)
    except psycopg2.OperationalError as e:
        logger.error(f"❌ Erro ao conectar ao banco de dados: {e}")
        logger.error(
            "Verifique se o PostgreSQL está rodando e as credenciais estão corretas."
        )
        raise


def find_csv_file():
    """
    Encontrar arquivo CSV de interações medicamentosas.

    Returns:
        Path: Caminho para o arquivo CSV

    Raises:
        FileNotFoundError: Se o arquivo não for encontrado
    """
    # Possíveis localizações do CSV
    possible_paths = [
        Path(__file__).parent.parent.parent / "data" / "db_drug_interactions.csv",
        Path(__file__).parent.parent / "data" / "db_drug_interactions.csv",
        Path("data/db_drug_interactions.csv"),
        Path("/app/data/db_drug_interactions.csv"),  # Docker
    ]

    for csv_path in possible_paths:
        if csv_path.exists():
            logger.info(f"📁 Arquivo CSV encontrado: {csv_path}")
            return csv_path

    raise FileNotFoundError(
        "Arquivo CSV não encontrado. Procurado em:\n"
        + "\n".join(f"  - {p}" for p in possible_paths)
    )


def import_interactions():
    """Importar interações do CSV para o banco"""

    # Obter conexão
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verificar se já tem dados
        cursor.execute(
            "SELECT COUNT(*) FROM drug_interactions WHERE source = 'CSV Import'"
        )
        count = cursor.fetchone()[0]

        if count > 0:
            logger.info(f"✅ Base já possui {count} interações do CSV. Limpando...")
            cursor.execute("DELETE FROM drug_interactions WHERE source = 'CSV Import'")
            conn.commit()

        # Encontrar e ler CSV
        csv_path = find_csv_file()
        logger.info(f"📊 Lendo CSV: {csv_path}")

        interactions = []
        with open(csv_path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                drug_a = row["Drug 1"].strip()
                drug_b = row["Drug 2"].strip()
                description = row["Interaction Description"].strip()

                # Classificar severidade pela descrição
                severity = classify_severity(description)
                interaction_type = classify_interaction_type(description)

                interactions.append(
                    (
                        drug_a,
                        drug_b,
                        interaction_type,
                        severity,
                        description,  # mechanism
                        description,  # clinical_effect
                        "Consultar médico antes de usar em conjunto",  # recommendation
                        "CSV Import",
                    )
                )

        logger.info(f"📊 Total de interações a importar: {len(interactions):,}")

        # Inserir em batch para melhor performance
        execute_batch(
            cursor,
            """
            INSERT INTO drug_interactions
            (drug_a, drug_b, interaction_type, severity, mechanism,
             clinical_effect, recommendation, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
            interactions,
            page_size=1000,
        )

        conn.commit()

        # Verificar
        cursor.execute(
            "SELECT COUNT(*) FROM drug_interactions WHERE source = 'CSV Import'"
        )
        final_count = cursor.fetchone()[0]

        logger.info(f"✅ Importação concluída: {final_count:,} interações importadas")

        # Estatísticas
        cursor.execute(
            """
            SELECT severity, COUNT(*)
            FROM drug_interactions
            WHERE source = 'CSV Import'
            GROUP BY severity
            ORDER BY COUNT(*) DESC
        """
        )

        stats = cursor.fetchall()
        logger.info("\n📈 Estatísticas por severidade:")
        for severity, count in stats:
            logger.info(f"  - {severity}: {count:,}")

    except Exception as e:
        logger.error(f"❌ Erro durante importação: {e}")
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


def classify_severity(description: str) -> str:
    """
    Classificar severidade pela descrição.

    Args:
        description: Descrição da interação

    Returns:
        str: Nível de severidade ('crítica', 'alta', 'moderada', 'baixa')
    """
    desc_lower = description.lower()

    # Palavras-chave para classificação
    critical_keywords = [
        "fatal",
        "death",
        "lethal",
        "contraindicated",
        "avoid",
        "severe",
        "life-threatening",
        "toxic",
        "poisoning",
    ]

    high_keywords = [
        "increase",
        "decrease",
        "potentiate",
        "enhance",
        "reduce",
        "risk",
        "serious",
        "significant",
        "major",
    ]

    moderate_keywords = ["may", "might", "can", "possible", "monitor", "caution"]

    for keyword in critical_keywords:
        if keyword in desc_lower:
            return "crítica"

    for keyword in high_keywords:
        if keyword in desc_lower:
            return "alta"

    for keyword in moderate_keywords:
        if keyword in desc_lower:
            return "moderada"

    return "baixa"


def classify_interaction_type(description: str) -> str:
    """
    Classificar tipo de interação.

    Args:
        description: Descrição da interação

    Returns:
        str: Tipo de interação ('farmacocinética' ou 'farmacodinâmica')
    """
    desc_lower = description.lower()

    if any(
        word in desc_lower
        for word in ["absorption", "metabolism", "excretion", "distribution"]
    ):
        return "farmacocinética"
    elif any(
        word in desc_lower for word in ["effect", "activity", "action", "response"]
    ):
        return "farmacodinâmica"
    elif any(
        word in desc_lower for word in ["serum", "concentration", "level", "plasma"]
    ):
        return "farmacocinética"
    else:
        return "farmacodinâmica"


if __name__ == "__main__":
    logger.info("🚀 Iniciando importação de interações medicamentosas do CSV...")
    logger.info("=" * 70)

    start_time = datetime.now()

    try:
        import_interactions()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 70)
        logger.info("✅ Importação concluída com sucesso!")
        logger.info(f"⏱️  Tempo total: {duration:.2f} segundos")

    except Exception as e:
        logger.error("=" * 70)
        logger.error(f"❌ Importação falhou: {e}")
        logger.error("=" * 70)
        exit(1)
