"""
Test script to verify RAG API implementations are working correctly.

Tests:
1. Pinecone connection and index access
2. Label indexing into Pinecone
3. RAG retrieval with reranking
4. RAG scoring integration
"""

import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from backend.app.clients.vector import get_pinecone_index, rerank_label_results
from backend.app.services.label_rag import retrieve_label_for_alert, index_label_into_pinecone
from backend.app.core.settings import settings
from sqlmodel import Session, create_engine, select
from backend.app.models.label import LabelVersion


def test_pinecone_connection():
    """Test if Pinecone connection works."""
    print("=" * 60)
    print("Test 1: Pinecone Connection")
    print("=" * 60)
    try:
        index = get_pinecone_index()
        print(f"✅ Pinecone connection successful")
        print(f"   Index: {settings.pinecone_index}")
        return True
    except Exception as e:
        print(f"❌ Pinecone connection failed: {e}")
        return False


def test_rerank_api():
    """Test Cohere Rerank API through Pinecone."""
    print("\n" + "=" * 60)
    print("Test 2: Cohere Rerank API")
    print("=" * 60)
    try:
        query = "pneumonitis in pembrolizumab patients"
        documents = [
            "Pembrolizumab can cause immune-mediated pneumonitis. Monitor patients for signs and symptoms.",
            "Apples are a popular fruit known for their sweetness.",
            "Pneumonitis is a serious adverse event that may occur with pembrolizumab treatment.",
            "The weather today is sunny and warm.",
            "Keytruda (pembrolizumab) has been associated with pneumonitis in clinical trials.",
        ]
        
        results = rerank_label_results(query, documents, top_n=3)
        
        if results:
            print(f"✅ Rerank API working - returned {len(results)} results")
            for i, r in enumerate(results, 1):
                print(f"   {i}. Score: {r.get('score', 0):.4f}")
                print(f"      Doc: {r.get('document', '')[:80]}...")
            return True
        else:
            print("❌ Rerank API returned no results")
            return False
    except Exception as e:
        print(f"❌ Rerank API failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_retrieval():
    """Test RAG retrieval with reranking."""
    print("\n" + "=" * 60)
    print("Test 3: RAG Retrieval with Reranking")
    print("=" * 60)
    try:
        query = "pneumonitis adverse event pembrolizumab"
        matches = retrieve_label_for_alert(query, top_k=3, use_rerank=True)
        
        if matches:
            print(f"✅ RAG retrieval working - returned {len(matches)} matches")
            for i, match in enumerate(matches, 1):
                score = getattr(match, 'score', 0.0)
                metadata = getattr(match, 'metadata', {}) or {}
                match_type = metadata.get('type', 'unknown')
                print(f"   {i}. Score: {score:.4f}, Type: {match_type}")
                text = metadata.get('text', '')[:100]
                if text:
                    print(f"      Text: {text}...")
            return True
        else:
            print("⚠️  RAG retrieval returned no matches (index may be empty)")
            print("   Run POST /api/v1/jobs/index_label to index labels first")
            return None  # Not a failure, just empty index
    except Exception as e:
        print(f"❌ RAG retrieval failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_label_indexing():
    """Test label indexing into Pinecone."""
    print("\n" + "=" * 60)
    print("Test 4: Label Indexing")
    print("=" * 60)
    try:
        # Get database session
        engine = create_engine(settings.database_url)
        with Session(engine) as session:
            result = index_label_into_pinecone(session, drug="pembrolizumab")
            
            if result.get("indexed", 0) > 0:
                print(f"✅ Label indexing successful")
                print(f"   Indexed {result['indexed']} vectors")
                print(f"   Label version ID: {result.get('label_version_id')}")
                return True
            else:
                print(f"⚠️  No labels indexed: {result.get('detail', 'unknown reason')}")
                print("   This is OK if no labels exist in database")
                return None
    except Exception as e:
        print(f"❌ Label indexing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("RAG API Implementation Tests")
    print("=" * 60)
    print(f"Pinecone Index: {settings.pinecone_index}")
    print(f"Database: {settings.database_url}")
    print()
    
    results = []
    
    # Test 1: Pinecone connection
    results.append(("Pinecone Connection", test_pinecone_connection()))
    
    # Test 2: Rerank API
    results.append(("Cohere Rerank API", test_rerank_api()))
    
    # Test 3: RAG retrieval
    results.append(("RAG Retrieval", test_rag_retrieval()))
    
    # Test 4: Label indexing
    results.append(("Label Indexing", test_label_indexing()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = 0
    failed = 0
    skipped = 0
    
    for name, result in results:
        if result is True:
            print(f"✅ {name}: PASSED")
            passed += 1
        elif result is False:
            print(f"❌ {name}: FAILED")
            failed += 1
        else:
            print(f"⚠️  {name}: SKIPPED (no data)")
            skipped += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0:
        print("\n✅ All critical tests passed! RAG implementation is working.")
    else:
        print(f"\n❌ {failed} test(s) failed. Please check the errors above.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

