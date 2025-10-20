"""
Script para importar interações medicamentosas do CSV para PostgreSQL
"""

import csv
import psycopg2
from psycopg2.extras import execute_batch
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def import_interactions():
    """Importar interações do CSV para o banco"""

    # Conectar ao banco
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        database="medsafe",
        user="medsafe",
        password="medsafe123"
    )
    cursor = conn.cursor()

    # Verificar se já tem dados
    cursor.execute("SELECT COUNT(*) FROM drug_interactions WHERE source = 'CSV Import'")
    count = cursor.fetchone()[0]

    if count > 0:
        logger.info(f"✅ Base já possui {count} interações do CSV. Limpando...")
        cursor.execute("DELETE FROM drug_interactions WHERE source = 'CSV Import'")
        conn.commit()

    # Ler CSV
    csv_path = "../../data/db_drug_interactions.csv"
    if not os.path.exists(csv_path):
        csv_path = "/home/lucasmsilva/Documentos/Cursor/MedSafe/data/db_drug_interactions.csv"

    logger.info(f"📁 Lendo CSV: {csv_path}")

    interactions = []
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            drug_a = row['Drug 1'].strip()
            drug_b = row['Drug 2'].strip()
            description = row['Interaction Description'].strip()

            # Classificar severidade pela descrição
            severity = classify_severity(description)
            interaction_type = classify_interaction_type(description)

            interactions.append((
                drug_a,
                drug_b,
                interaction_type,
                severity,
                description,  # mechanism
                description,  # clinical_effect
                "Consultar médico antes de usar em conjunto",  # recommendation
                "CSV Import"
            ))

    logger.info(f"📊 Total de interações a importar: {len(interactions)}")

    # Inserir em batch para melhor performance
    execute_batch(cursor, """
        INSERT INTO drug_interactions
        (drug_a, drug_b, interaction_type, severity, mechanism, clinical_effect, recommendation, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, interactions, page_size=1000)

    conn.commit()

    # Verificar
    cursor.execute("SELECT COUNT(*) FROM drug_interactions WHERE source = 'CSV Import'")
    final_count = cursor.fetchone()[0]

    logger.info(f"✅ Importação concluída: {final_count} interações importadas")

    # Estatísticas
    cursor.execute("""
        SELECT severity, COUNT(*)
        FROM drug_interactions
        WHERE source = 'CSV Import'
        GROUP BY severity
        ORDER BY COUNT(*) DESC
    """)

    stats = cursor.fetchall()
    logger.info("\n📈 Estatísticas por severidade:")
    for severity, count in stats:
        logger.info(f"  - {severity}: {count}")

    cursor.close()
    conn.close()

def classify_severity(description: str) -> str:
    """Classificar severidade pela descrição"""
    desc_lower = description.lower()

    # Palavras-chave para classificação
    critical_keywords = [
        'fatal', 'death', 'lethal', 'contraindicated', 'avoid', 'severe',
        'life-threatening', 'toxic', 'poisoning'
    ]

    high_keywords = [
        'increase', 'decrease', 'potentiate', 'enhance', 'reduce',
        'risk', 'serious', 'significant', 'major'
    ]

    moderate_keywords = [
        'may', 'might', 'can', 'possible', 'monitor', 'caution'
    ]

    for keyword in critical_keywords:
        if keyword in desc_lower:
            return 'crítica'

    for keyword in high_keywords:
        if keyword in desc_lower:
            return 'alta'

    for keyword in moderate_keywords:
        if keyword in desc_lower:
            return 'moderada'

    return 'baixa'

def classify_interaction_type(description: str) -> str:
    """Classificar tipo de interação"""
    desc_lower = description.lower()

    if any(word in desc_lower for word in ['absorption', 'metabolism', 'excretion', 'distribution']):
        return 'farmacocinética'
    elif any(word in desc_lower for word in ['effect', 'activity', 'action', 'response']):
        return 'farmacodinâmica'
    elif any(word in desc_lower for word in ['serum', 'concentration', 'level', 'plasma']):
        return 'farmacocinética'
    else:
        return 'farmacodinâmica'

if __name__ == "__main__":
    logger.info("🚀 Iniciando importação de interações medicamentosas do CSV...")
    start_time = datetime.now()

    import_interactions()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"\n⏱️  Tempo total: {duration:.2f} segundos")
