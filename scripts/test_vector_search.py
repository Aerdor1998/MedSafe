#!/usr/bin/env python3
"""
Vector Store Search Tester

PATTERN: Interactive testing tool for RAG system
SKILLS: @ultrathink, @debugging-strategies

This script allows you to interactively test the vector store search
capabilities to verify RAG is working correctly.

Usage:
    # Interactive search
    python scripts/test_vector_search.py

    # Search for specific drug
    python scripts/test_vector_search.py --query "aspirin interactions"

    # Semantic search only
    python scripts/test_vector_search.py --query "warfarin" --mode semantic

    # Hybrid search
    python scripts/test_vector_search.py --query "lithium toxicity" --mode hybrid

    # Search by drug name
    python scripts/test_vector_search.py --drug "metformin" --section "contraindications"
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import logging
from typing import List, Dict, Any

from backend.app.db.vector_store import get_vector_store
from backend.app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def print_search_results(results: List[Dict[str, Any]], mode: str = "semantic"):
    """
    Pretty print search results

    Args:
        results: List of search result dicts
        mode: Search mode (semantic, hybrid, drug)
    """
    if not results:
        print("\nNo results found.\n")
        return

    print(f"\nFound {len(results)} results ({mode} search):\n")
    print("=" * 80)

    for i, result in enumerate(results, 1):
        metadata = result.get('metadata', {})
        score = result.get('score', 0.0)
        relevance = result.get('relevance', 'UNKNOWN')
        content = result.get('content', '')

        # Header
        print(f"\n📄 Result #{i} - Relevance: {relevance} (score: {score:.4f})")
        print("-" * 80)

        # Metadata
        print(f"   Drug: {metadata.get('drug_name', 'N/A')}")
        print(f"   Section: {metadata.get('section', 'N/A')}")
        print(f"   Source: {metadata.get('source', 'N/A')}")

        if metadata.get('source_url'):
            print(f"   URL: {metadata.get('source_url')}")

        # Content (truncated)
        content_preview = content[:300] if len(content) > 300 else content
        if len(content) > 300:
            content_preview += "... [truncated]"

        print(f"\n   Content:\n   {content_preview}\n")

    print("=" * 80)


def semantic_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Perform semantic search

    Args:
        query: Search query
        k: Number of results

    Returns:
        List of results
    """
    print(f"\nSemantic search for: '{query}' (top {k})\n")

    vector_store = get_vector_store()
    results = vector_store.semantic_search(query=query, k=k)

    return results


def hybrid_search(query: str, k: int = 5, semantic_weight: float = 0.7) -> List[Dict[str, Any]]:
    """
    Perform hybrid search (semantic + keyword)

    Args:
        query: Search query
        k: Number of results
        semantic_weight: Weight for semantic component

    Returns:
        List of results
    """
    print(f"\nHybrid search for: '{query}' (semantic_weight={semantic_weight}, top {k})\n")

    vector_store = get_vector_store()
    results = vector_store.hybrid_search(
        query=query,
        k=k,
        semantic_weight=semantic_weight
    )

    return results


def search_by_drug(drug_name: str, section: str = None, k: int = 5) -> List[Dict[str, Any]]:
    """
    Search for specific drug

    Args:
        drug_name: Drug name
        section: Optional section filter
        k: Number of results

    Returns:
        List of results
    """
    section_str = f" (section: {section})" if section else ""
    print(f"\nDrug search for: '{drug_name}'{section_str} (top {k})\n")

    vector_store = get_vector_store()
    results = vector_store.search_by_drug(
        drug_name=drug_name,
        section=section,
        k=k
    )

    return results


def interactive_mode():
    """Interactive search mode"""
    print("\n" + "=" * 80)
    print("MedSafe Vector Store - Interactive Search Mode")
    print("=" * 80)
    print("\nCommands:")
    print("  search <query>          - Semantic search")
    print("  hybrid <query>          - Hybrid search (semantic + keyword)")
    print("  drug <name> [section]   - Search by drug name")
    print("  stats                   - Show vector store statistics")
    print("  quit / exit             - Exit interactive mode")
    print("\nExample:")
    print("  > search aspirin drug interactions")
    print("  > hybrid warfarin toxicity")
    print("  > drug metformin contraindications")
    print("=" * 80 + "\n")

    vector_store = get_vector_store()

    while True:
        try:
            user_input = input("\n> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit']:
                print("\nExiting interactive mode. Goodbye!\n")
                break

            # Parse command
            parts = user_input.split(maxsplit=1)
            command = parts[0].lower()

            if command == 'search':
                if len(parts) < 2:
                    print("Usage: search <query>")
                    continue

                query = parts[1]
                results = semantic_search(query)
                print_search_results(results, mode="semantic")

            elif command == 'hybrid':
                if len(parts) < 2:
                    print("Usage: hybrid <query>")
                    continue

                query = parts[1]
                results = hybrid_search(query)
                print_search_results(results, mode="hybrid")

            elif command == 'drug':
                if len(parts) < 2:
                    print("Usage: drug <name> [section]")
                    continue

                args = parts[1].split(maxsplit=1)
                drug_name = args[0]
                section = args[1] if len(args) > 1 else None

                results = search_by_drug(drug_name, section)
                print_search_results(results, mode="drug")

            elif command == 'stats':
                stats = vector_store.get_collection_stats()

                print("\nVector Store Statistics:")
                print("-" * 80)
                print(f"   Collection: {stats.get('collection_name', 'N/A')}")
                print(f"   Total Embeddings: {stats.get('total_embeddings', 0):,}")
                print(f"   Unique Drugs: {stats.get('unique_drugs', 0):,}")
                print(f"   Unique Sources: {stats.get('unique_sources', 0):,}")
                print(f"   Embedding Model: {stats.get('embedding_model', 'N/A')}")
                print(f"   Distance Strategy: {stats.get('distance_strategy', 'N/A')}")
                print("-" * 80)

            else:
                print(f"Unknown command: {command}")
                print("   Type 'search', 'hybrid', 'drug', 'stats', or 'quit'")

        except KeyboardInterrupt:
            print("\n\nExiting interactive mode. Goodbye!\n")
            break
        except Exception as e:
            print(f"\nError: {e}\n")
            logger.exception("Error in interactive mode:")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="MedSafe Vector Store Search Tester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive mode
    python scripts/test_vector_search.py

    # Semantic search
    python scripts/test_vector_search.py --query "aspirin interactions" --mode semantic

    # Hybrid search
    python scripts/test_vector_search.py --query "warfarin toxicity" --mode hybrid

    # Search by drug
    python scripts/test_vector_search.py --drug "metformin" --section "contraindications"
        """
    )

    # Search parameters
    parser.add_argument('--query', type=str, help='Search query')
    parser.add_argument(
        '--mode',
        type=str,
        choices=['semantic', 'hybrid', 'drug'],
        default='semantic',
        help='Search mode (default: semantic)'
    )
    parser.add_argument('--drug', type=str, help='Drug name (for drug mode)')
    parser.add_argument('--section', type=str, help='Section filter (for drug mode)')
    parser.add_argument('-k', '--top-k', type=int, default=5, help='Number of results (default: 5)')
    parser.add_argument(
        '--semantic-weight',
        type=float,
        default=0.7,
        help='Semantic weight for hybrid search (default: 0.7)'
    )

    args = parser.parse_args()

    # If no arguments, start interactive mode
    if not (args.query or args.drug):
        interactive_mode()
        return

    # Handle different modes
    if args.mode == 'semantic' and args.query:
        results = semantic_search(args.query, k=args.top_k)
        print_search_results(results, mode="semantic")

    elif args.mode == 'hybrid' and args.query:
        results = hybrid_search(args.query, k=args.top_k, semantic_weight=args.semantic_weight)
        print_search_results(results, mode="hybrid")

    elif args.mode == 'drug' or args.drug:
        if not args.drug:
            print("--drug is required for drug search mode")
            sys.exit(1)

        results = search_by_drug(args.drug, args.section, k=args.top_k)
        print_search_results(results, mode="drug")

    else:
        print("Invalid arguments. Use --help for usage information.")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n Interrupted by user. Exiting...")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        logger.exception("Unhandled exception:")
        sys.exit(1)
