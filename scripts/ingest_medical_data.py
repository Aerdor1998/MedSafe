#!/usr/bin/env python3
"""
Medical Data Ingestion CLI Tool

PATTERN: Command-line tool for ingesting medical literature into vector store
SKILLS: @ultrathink, @api-design-principles, @python-performance-optimization

This script provides a convenient CLI for ingesting medical data from multiple sources
into the pgvector-backed knowledge base.

Usage:
    # Ingest from FDA for specific drug
    python scripts/ingest_medical_data.py --source FDA --query "aspirin" --max 50

    # Ingest from PubMed
    python scripts/ingest_medical_data.py --source PubMed --query "warfarin interactions" --max 100

    # Ingest from local JSON file
    python scripts/ingest_medical_data.py --source local_file --file data/drugs/aspirin.json

    # Bulk ingest multiple drugs from FDA
    python scripts/ingest_medical_data.py --bulk --source FDA --drugs aspirin,warfarin,lithium

    # Get vector store stats
    python scripts/ingest_medical_data.py --stats

REFERENCE: Antonio Gulli "Agentic Design Patterns" Chapter 14 (RAG), pg 281-310
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import logging
from typing import List
import json

from backend.app.services.literature_ingestion import (
    get_ingestion_service,
    DataSource
)
from backend.app.db.vector_store import get_vector_store
from backend.app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def ingest_single_source(
    source: DataSource,
    query: str,
    max_results: int,
    file_path: str = None,
    url: str = None
) -> dict:
    """
    Ingest from a single source

    Args:
        source: Data source to ingest from
        query: Search query (for FDA, PubMed, etc.)
        max_results: Maximum results to retrieve
        file_path: Path to local file (for local_file source)
        url: URL to scrape (for custom_url source)

    Returns:
        Ingestion results dict
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Starting ingestion from {source.value}")
    logger.info(f"{'='*60}\n")

    ingestion_service = get_ingestion_service()

    kwargs = {}
    if file_path:
        kwargs['file_path'] = file_path
    if url:
        kwargs['url'] = url

    result = ingestion_service.ingest_from_source(
        source=source,
        query=query,
        max_results=max_results,
        **kwargs
    )

    # Print results
    print_ingestion_results(result)

    return result


def bulk_ingest_drugs(
    drug_names: List[str],
    sources: List[DataSource],
    max_results_per_drug: int = 10
) -> dict:
    """
    Bulk ingest multiple drugs from multiple sources

    Args:
        drug_names: List of drug names
        sources: List of data sources
        max_results_per_drug: Max results per drug per source

    Returns:
        Aggregated results dict
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Bulk ingestion: {len(drug_names)} drugs × {len(sources)} sources")
    logger.info(f"{'='*60}\n")

    ingestion_service = get_ingestion_service()

    result = ingestion_service.bulk_ingest_drugs(
        drug_names=drug_names,
        sources=sources,
        max_results_per_drug=max_results_per_drug
    )

    # Print results
    print_bulk_results(result)

    return result


def get_stats() -> dict:
    """Get vector store statistics"""
    logger.info(f"\n{'='*60}")
    logger.info("Vector Store Statistics")
    logger.info(f"{'='*60}\n")

    vector_store = get_vector_store()
    stats = vector_store.get_collection_stats()

    # Print stats
    print("\nVector Store Stats:")
    print(f"   Collection: {stats.get('collection_name', 'N/A')}")
    print(f"   Total Embeddings: {stats.get('total_embeddings', 0):,}")
    print(f"   Unique Drugs: {stats.get('unique_drugs', 0):,}")
    print(f"   Unique Sources: {stats.get('unique_sources', 0):,}")
    print(f"   Embedding Model: {stats.get('embedding_model', 'N/A')}")
    print(f"   Distance Strategy: {stats.get('distance_strategy', 'N/A')}")
    print()

    return stats


def print_ingestion_results(result: dict):
    """Pretty print ingestion results"""
    status = result.get('status', 'unknown')

    if status == 'completed':
        print("\nIngestion completed successfully!\n")
        print(f"   Source: {result.get('source', 'N/A')}")
        print(f"   Query: {result.get('query', 'N/A')}")
        print(f"   Total Fetched: {result.get('total_fetched', 0)}")
        print(f"   Unique Documents: {result.get('unique_documents', 0)}")
        print(f"   Chunks Created: {result.get('chunks_created', 0):,}")
        print(f"   Duration: {result.get('duration_seconds', 0):.2f}s")
        print(f"   Job ID: {result.get('job_id', 'N/A')}")
        print()
    else:
        print("\nIngestion failed!\n")
        print(f"   Error: {result.get('error', 'Unknown error')}")
        print()


def print_bulk_results(result: dict):
    """Pretty print bulk ingestion results"""
    print("\nBulk ingestion completed!\n")
    print(f"   Total Drugs: {result.get('total_drugs', 0)}")
    print(f"   Total Sources: {result.get('total_sources', 0)}")
    print(f"   Total Documents: {result['aggregated'].get('total_documents', 0):,}")
    print(f"   Total Chunks: {result['aggregated'].get('total_chunks', 0):,}")
    print(f"   Duration: {result['aggregated'].get('duration_seconds', 0):.2f}s")
    print()

    # Print per-drug breakdown
    print("📋 Per-Drug Results:")
    for drug_name, drug_results in result.get('per_drug_results', {}).items():
        total_docs = sum(r.get('unique_documents', 0) for r in drug_results)
        total_chunks = sum(r.get('chunks_created', 0) for r in drug_results)
        print(f"   {drug_name}: {total_docs} docs, {total_chunks} chunks")
    print()


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="MedSafe Medical Data Ingestion Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Ingest from FDA
    python scripts/ingest_medical_data.py --source FDA --query "aspirin" --max 50

    # Ingest from PubMed
    python scripts/ingest_medical_data.py --source PubMed --query "warfarin" --max 100

    # Ingest from local file
    python scripts/ingest_medical_data.py --source local_file --file data/drugs/aspirin.json

    # Bulk ingest
    python scripts/ingest_medical_data.py --bulk --source FDA --drugs aspirin,warfarin,lithium

    # Get stats
    python scripts/ingest_medical_data.py --stats
        """
    )

    # Mode selection
    parser.add_argument('--bulk', action='store_true', help='Bulk ingest multiple drugs')
    parser.add_argument('--stats', action='store_true', help='Show vector store statistics')

    # Data source
    parser.add_argument(
        '--source',
        type=str,
        choices=['FDA', 'PubMed', 'ANVISA', 'DrugBank', 'local_file', 'custom_url'],
        help='Data source to ingest from'
    )

    # Query parameters
    parser.add_argument('--query', type=str, help='Search query (drug name or keywords)')
    parser.add_argument('--max', type=int, default=10, help='Maximum results to fetch (default: 10)')

    # File/URL parameters
    parser.add_argument('--file', type=str, help='Path to local file (for local_file source)')
    parser.add_argument('--url', type=str, help='URL to scrape (for custom_url source)')

    # Bulk ingest parameters
    parser.add_argument(
        '--drugs',
        type=str,
        help='Comma-separated list of drug names (for bulk mode)'
    )
    parser.add_argument(
        '--sources',
        type=str,
        help='Comma-separated list of sources for bulk mode (default: FDA,PubMed)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not (args.stats or args.source or args.bulk):
        parser.error("Must specify --stats, --source, or --bulk")

    # Handle stats mode
    if args.stats:
        get_stats()
        return

    # Handle bulk mode
    if args.bulk:
        if not args.drugs:
            parser.error("--bulk requires --drugs")

        drug_names = [d.strip() for d in args.drugs.split(',')]

        # Parse sources (default to FDA,PubMed)
        if args.sources:
            source_names = [s.strip() for s in args.sources.split(',')]
        else:
            source_names = ['FDA', 'PubMed']

        sources = [DataSource(s.upper()) for s in source_names]

        bulk_ingest_drugs(
            drug_names=drug_names,
            sources=sources,
            max_results_per_drug=args.max
        )
        return

    # Handle single source mode
    if not args.source:
        parser.error("Must specify --source for single ingestion")

    source = DataSource(args.source.lower())

    # Validate source-specific parameters
    if source == DataSource.LOCAL_FILE and not args.file:
        parser.error("--source local_file requires --file")

    if source == DataSource.CUSTOM_URL and not args.url:
        parser.error("--source custom_url requires --url")

    if source in [DataSource.FDA, DataSource.PUBMED, DataSource.ANVISA] and not args.query:
        parser.error(f"--source {source.value} requires --query")

    ingest_single_source(
        source=source,
        query=args.query,
        max_results=args.max,
        file_path=args.file,
        url=args.url
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n Interrupted by user. Exiting...")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        logger.exception("Unhandled exception in main:")
        sys.exit(1)
