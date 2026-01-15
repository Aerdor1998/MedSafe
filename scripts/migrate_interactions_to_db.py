#!/usr/bin/env python3
"""
Script para migrar interações medicamentosas do CSV para PostgreSQL.

Este script importa todas as interações do arquivo CSV para a tabela drug_interactions,
permitindo buscas muito mais eficientes (de ~2-5s para <50ms).

Uso:
    python scripts/migrate_interactions_to_db.py
    
    # Com opções
    python scripts/migrate_interactions_to_db.py --batch-size=1000 --dry-run

Performance:
    - CSV: ~191k linhas iteradas a cada busca
    - DB com índice: Lookup direto via índice composto
    - Melhoria esperada: 100x mais rápido
"""

import argparse
import csv
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# Constantes
CSV_PATH = Path(__file__).parent.parent / "data" / "db_drug_interactions.csv"
BATCH_SIZE_DEFAULT = 500


def normalize_drug_name(name: str) -> str:
    """
    Normaliza nome de medicamento para busca eficiente.
    
    - Lowercase
    - Remove espaços extras
    - Remove caracteres especiais comuns
    """
    if not name:
        return ""
    
    normalized = name.lower().strip()
    
    # Remover sufixos comuns de forma/dosagem
    for suffix in [" oral", " inj", " iv", " im", " sc", " gel", " cream", " tab", " cap"]:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
    
    # Manter apenas alfanuméricos e espaços
    normalized = "".join(c for c in normalized if c.isalnum() or c == " ")
    normalized = " ".join(normalized.split())  # Normalizar espaços
    
    return normalized


def parse_csv_row(row: Dict[str, str]) -> Optional[Dict]:
    """
    Parseia uma linha do CSV para formato do banco.
    
    Retorna None se a linha for inválida.
    
    Suporta dois formatos de CSV:
    - "Drug 1", "Drug 2", "Interaction Description" (formato atual)
    - "Drug A", "Drug B", "Description" (formato alternativo)
    """
    try:
        # Suportar ambos os formatos de coluna
        drug_a = row.get("Drug 1", row.get("Drug A", "")).strip()
        drug_b = row.get("Drug 2", row.get("Drug B", "")).strip()
        
        if not drug_a or not drug_b:
            return None
        
        # Normalizar nomes para busca
        drug_a_norm = normalize_drug_name(drug_a)
        drug_b_norm = normalize_drug_name(drug_b)
        
        if not drug_a_norm or not drug_b_norm:
            return None
        
        # Ordenar alfabeticamente para evitar duplicatas (A-B == B-A)
        if drug_a_norm > drug_b_norm:
            drug_a, drug_b = drug_b, drug_a
            drug_a_norm, drug_b_norm = drug_b_norm, drug_a_norm
        
        # Mapear severidade
        severity_raw = row.get("Severity", "").lower().strip()
        severity_map = {
            "major": "grave",
            "moderate": "moderada",
            "minor": "leve",
            "grave": "grave",
            "moderada": "moderada",
            "leve": "leve",
            "critical": "grave",
            "high": "grave",
            "medium": "moderada",
            "low": "leve",
        }
        
        if severity_raw:
            severity = severity_map.get(severity_raw, "moderada")
        else:
            # Inferir severidade da descrição se não fornecida
            desc_lower = description.lower() if description else ""
            if any(w in desc_lower for w in ["contraindicated", "fatal", "death", "severe", "life-threatening", "avoid"]):
                severity = "grave"
            elif any(w in desc_lower for w in ["increase", "decrease", "may affect", "caution"]):
                severity = "moderada"
            else:
                severity = "leve"
        
        # Extrair campos opcionais (suportando múltiplos formatos)
        description = row.get("Interaction Description", row.get("Description", row.get("Interaction", ""))).strip()[:500]
        mechanism = row.get("Mechanism", "").strip()[:500]
        source = row.get("Source", "csv_import").strip()[:100]
        
        return {
            "drug_a": drug_a[:200],
            "drug_b": drug_b[:200],
            "drug_a_norm": drug_a_norm[:200],
            "drug_b_norm": drug_b_norm[:200],
            "severity": severity,
            "clinical_effect": description if description else None,  # Map to clinical_effect column
            "mechanism": mechanism if mechanism else None,
            "source": source,
        }
        
    except Exception as e:
        logger.warning(f"Erro ao parsear linha: {e}")
        return None


def get_database_url() -> str:
    """Obtém URL do banco de dados."""
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        return db_url
    
    # Tentar construir a partir de variáveis individuais
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5433")
    user = os.getenv("POSTGRES_USER", "medsafe")
    password = os.getenv("POSTGRES_PASSWORD", "medsafe_secret")
    db = os.getenv("POSTGRES_DB", "medsafe")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def create_table_if_not_exists(engine):
    """
    Cria a tabela drug_interactions se não existir.
    
    NOTA: Em produção, usar Alembic migrations (005_add_drug_interactions_table.py).
    Este método é para desenvolvimento/testes rápidos.
    """
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS drug_interactions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        drug_a VARCHAR(200) NOT NULL,
        drug_b VARCHAR(200) NOT NULL,
        drug_a_norm VARCHAR(200) NOT NULL,
        drug_b_norm VARCHAR(200) NOT NULL,
        interaction_type VARCHAR(100),
        severity VARCHAR(50),
        mechanism TEXT,
        clinical_effect TEXT,
        recommendation TEXT,
        source VARCHAR(100),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Índice composto para busca rápida (principal)
    CREATE INDEX IF NOT EXISTS idx_drug_interactions_pair 
    ON drug_interactions (drug_a_norm, drug_b_norm);
    
    -- Índices individuais para filtros
    CREATE INDEX IF NOT EXISTS idx_drug_interactions_a
    ON drug_interactions (drug_a_norm);
    
    CREATE INDEX IF NOT EXISTS idx_drug_interactions_b
    ON drug_interactions (drug_b_norm);
    
    -- Índice parcial para interações graves
    CREATE INDEX IF NOT EXISTS idx_drug_interactions_severe 
    ON drug_interactions (drug_a_norm, drug_b_norm) 
    WHERE severity IN ('grave', 'major', 'critical');
    
    -- GIN index para busca por texto
    CREATE INDEX IF NOT EXISTS idx_drug_interactions_effect_gin
    ON drug_interactions USING gin (to_tsvector('english', coalesce(clinical_effect, '')));
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
    
    logger.info("✅ Tabela drug_interactions verificada/criada")


def count_existing_records(session) -> int:
    """Conta registros existentes na tabela."""
    result = session.execute(text("SELECT COUNT(*) FROM drug_interactions"))
    return result.scalar()


def insert_batch(session, records: List[Dict]) -> int:
    """
    Insere um lote de registros no banco.
    
    Usa ON CONFLICT para ignorar duplicatas.
    Retorna número de registros inseridos.
    """
    if not records:
        return 0
    
    insert_sql = """
    INSERT INTO drug_interactions 
    (drug_a, drug_b, drug_a_norm, drug_b_norm, severity, clinical_effect, mechanism, source)
    VALUES (:drug_a, :drug_b, :drug_a_norm, :drug_b_norm, :severity, :clinical_effect, :mechanism, :source)
    ON CONFLICT (drug_a_norm, drug_b_norm) DO NOTHING
    """
    
    result = session.execute(text(insert_sql), records)
    return result.rowcount


def migrate_csv_to_db(
    csv_path: Path,
    batch_size: int = BATCH_SIZE_DEFAULT,
    dry_run: bool = False,
    max_records: Optional[int] = None,
) -> Dict:
    """
    Migra interações do CSV para o banco de dados.
    
    Args:
        csv_path: Caminho para o arquivo CSV
        batch_size: Tamanho do lote para inserção
        dry_run: Se True, apenas simula a migração
        max_records: Limite máximo de registros (None = todos)
    
    Returns:
        Dicionário com estatísticas da migração
    """
    stats = {
        "start_time": datetime.now().isoformat(),
        "csv_path": str(csv_path),
        "total_csv_rows": 0,
        "valid_records": 0,
        "inserted_records": 0,
        "skipped_duplicates": 0,
        "invalid_rows": 0,
        "batches_processed": 0,
        "duration_seconds": 0,
        "dry_run": dry_run,
    }
    
    start_time = time.time()
    
    # Verificar arquivo CSV
    if not csv_path.exists():
        logger.error(f"❌ Arquivo CSV não encontrado: {csv_path}")
        stats["error"] = "CSV file not found"
        return stats
    
    logger.info(f"📂 Lendo CSV: {csv_path}")
    
    # Conectar ao banco
    db_url = get_database_url()
    logger.info(f"🔗 Conectando ao banco: {db_url.split('@')[-1]}")  # Ocultar senha
    
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    
    # Criar tabela se necessário
    if not dry_run:
        create_table_if_not_exists(engine)
    
    session = Session()
    
    try:
        # Contar registros existentes
        existing_count = count_existing_records(session) if not dry_run else 0
        logger.info(f"📊 Registros existentes no banco: {existing_count}")
        
        # Ler CSV
        batch = []
        seen_pairs = set()  # Para deduplicar dentro do CSV
        
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                stats["total_csv_rows"] += 1
                
                # Limite de registros
                if max_records and stats["valid_records"] >= max_records:
                    break
                
                # Parsear linha
                record = parse_csv_row(row)
                
                if record is None:
                    stats["invalid_rows"] += 1
                    continue
                
                # Verificar duplicata no CSV
                pair_key = (record["drug_a_norm"], record["drug_b_norm"])
                if pair_key in seen_pairs:
                    stats["skipped_duplicates"] += 1
                    continue
                
                seen_pairs.add(pair_key)
                batch.append(record)
                stats["valid_records"] += 1
                
                # Inserir batch
                if len(batch) >= batch_size:
                    if not dry_run:
                        inserted = insert_batch(session, batch)
                        stats["inserted_records"] += inserted
                        session.commit()
                    else:
                        stats["inserted_records"] += len(batch)
                    
                    stats["batches_processed"] += 1
                    
                    if stats["batches_processed"] % 10 == 0:
                        logger.info(
                            f"   📦 Batch {stats['batches_processed']}: "
                            f"{stats['valid_records']} registros válidos, "
                            f"{stats['inserted_records']} inseridos"
                        )
                    
                    batch = []
        
        # Inserir batch final
        if batch:
            if not dry_run:
                inserted = insert_batch(session, batch)
                stats["inserted_records"] += inserted
                session.commit()
            else:
                stats["inserted_records"] += len(batch)
            
            stats["batches_processed"] += 1
        
        # Contar total final
        final_count = count_existing_records(session) if not dry_run else stats["inserted_records"]
        stats["final_db_count"] = final_count
        
    except Exception as e:
        logger.error(f"❌ Erro durante migração: {e}")
        session.rollback()
        stats["error"] = str(e)
        raise
        
    finally:
        session.close()
    
    stats["duration_seconds"] = round(time.time() - start_time, 2)
    stats["end_time"] = datetime.now().isoformat()
    
    return stats


def print_summary(stats: Dict):
    """Imprime resumo da migração."""
    
    print("\n" + "=" * 60)
    print("📊 RESUMO DA MIGRAÇÃO")
    print("=" * 60)
    
    if stats.get("dry_run"):
        print("⚠️  MODO DRY-RUN (nenhuma alteração foi feita)")
    
    print(f"""
    📂 Arquivo CSV:        {stats.get('csv_path', 'N/A')}
    📑 Total linhas CSV:   {stats.get('total_csv_rows', 0):,}
    ✅ Registros válidos:  {stats.get('valid_records', 0):,}
    ❌ Linhas inválidas:   {stats.get('invalid_rows', 0):,}
    🔄 Duplicatas no CSV:  {stats.get('skipped_duplicates', 0):,}
    
    📦 Batches processados: {stats.get('batches_processed', 0)}
    ✨ Registros inseridos: {stats.get('inserted_records', 0):,}
    📊 Total final no DB:   {stats.get('final_db_count', 'N/A')}
    
    ⏱️  Duração:            {stats.get('duration_seconds', 0)}s
    """)
    
    if stats.get("error"):
        print(f"❌ ERRO: {stats['error']}")
    else:
        print("✅ Migração concluída com sucesso!")
    
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Migra interações medicamentosas do CSV para PostgreSQL"
    )
    
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=CSV_PATH,
        help=f"Caminho do arquivo CSV (default: {CSV_PATH})"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE_DEFAULT,
        help=f"Tamanho do batch para inserção (default: {BATCH_SIZE_DEFAULT})"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a migração sem modificar o banco"
    )
    
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Limite máximo de registros a migrar"
    )
    
    args = parser.parse_args()
    
    logger.info("🚀 Iniciando migração de interações medicamentosas")
    logger.info(f"   CSV: {args.csv_path}")
    logger.info(f"   Batch size: {args.batch_size}")
    logger.info(f"   Dry run: {args.dry_run}")
    
    try:
        stats = migrate_csv_to_db(
            csv_path=args.csv_path,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            max_records=args.max_records,
        )
        
        print_summary(stats)
        
        return 0 if not stats.get("error") else 1
        
    except Exception as e:
        logger.exception(f"❌ Falha na migração: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

