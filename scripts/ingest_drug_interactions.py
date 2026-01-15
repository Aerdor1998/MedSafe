"""
Ingere o CSV de interações medicamentosas no vector store.
"""

import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.vector_store import MedicalVectorStore


def ingest_csv_to_vectorstore(limit: int = None):
    """Converte CSV de interações em documentos embedados.
    
    Args:
        limit: Número máximo de documentos a ingerir (None = todos)
    """
    import os
    print(f"OLLAMA_HOST: {os.getenv('OLLAMA_HOST', 'not set')}")
    print(f"EMBEDDING_MODEL: {os.getenv('EMBEDDING_MODEL', 'not set')}")
    print("📖 Lendo CSV...")
    sys.stdout.flush()
    
    df = pd.read_csv("data/db_drug_interactions.csv")
    total_rows = len(df)
    
    if limit:
        df = df.head(limit)
        print(f"Limitado a {limit} de {total_rows} linhas")
    else:
        print(f"Total de linhas no CSV: {total_rows}")
    sys.stdout.flush()

    print("Preparando documentos...")
    sys.stdout.flush()
    
    documents = []
    for idx, row in df.iterrows():
        doc = {
            "text": f"Drug interaction between {row['Drug 1']} and {row['Drug 2']}: {row['Interaction Description']}",
            "metadata": {
                "drug_1": row["Drug 1"],
                "drug_2": row["Drug 2"],
                "drug_name": row["Drug 1"],
                "source": "DrugBank CSV",
                "section": "interactions",
            },
        }
        documents.append(doc)
        if (idx + 1) % 1000 == 0:
            print(f"   Preparados {idx + 1} documentos...")
            sys.stdout.flush()

    print(f"{len(documents)} documentos preparados")
    print("Inicializando vector store...")
    sys.stdout.flush()
    
    vector_store = MedicalVectorStore()
    
    print("📤 Adicionando documentos ao vector store...")
    sys.stdout.flush()
    
    total = vector_store.add_documents(documents)

    print(f"Ingeridos {len(documents)} documentos ({total} chunks)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest drug interactions CSV to vector store")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to ingest")
    args = parser.parse_args()
    
    ingest_csv_to_vectorstore(limit=args.limit)

