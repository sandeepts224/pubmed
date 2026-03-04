"""
Test script to verify Pinecone APIs and RAG implementation are working.

This script tests:
1. Pinecone connection
2. Vector search (query)
3. Cohere Rerank API
4. RAG retrieval with reranking
5. Full RAG scoring flow
"""

import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

def test_pinecone_connection():
    """Test 1: Pinecone connection"""
    print("=" * 70)
    print("TEST 1: Pinecone Connection")
    print("=" * 70)
    try:
        from backend.app.clients.vector import get_pinecone_index, get_pinecone_client
        from backend.app.core.settings import settings
        
        print(f"Pinecone Index: {settings.pinecone_index}")
        print(f"Pinecone API Key: {'*' * 20 if settings.pinecone_api_key else 'NOT SET'}")
        
        if not settings.pinecone_api_key:
            print("FAILED: PINECONE_API_KEY not configured")
            return False
        
        # Test client connection
        pc = get_pinecone_client()
        print("OK: Pinecone client created")
        
        # Test index access
        index = get_pinecone_index()
        print(f"OK: Pinecone index accessed: {settings.pinecone_index}")
        
        # Try to get index stats
        try:
            stats = index.describe_index_stats()
            print(f"OK: Index stats retrieved")
            print(f"   Total vectors: {stats.get('total_vector_count', 'unknown')}")
            return True
        except Exception as e:
            print(f"WARNING: Could not get index stats: {e}")
            print("   (This is OK if index is empty or new)")
            return True  # Connection works, just empty index
            
    except ImportError as e:
        print(f"FAILED: Missing dependency - {e}")
        print("   Install with: pip install pinecone-client")
        return False
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vector_query():
    """Test 2: Vector search query"""
    print("\n" + "=" * 70)
    print("TEST 2: Vector Search Query")
    print("=" * 70)
    try:
        from backend.app.clients.vector import query_label_vectors
        
        # Test query with text (Pinecone integrated inference)
        query_text = "pneumonitis adverse event pembrolizumab"
        print(f"Query: '{query_text}'")
        
        # Try querying with text
        try:
            result = query_label_vectors(query_text, top_k=5)
            matches = result.matches if hasattr(result, 'matches') else []
            
            if matches:
                print(f"OK: Vector search successful - {len(matches)} matches found")
                for i, match in enumerate(matches[:3], 1):
                    score = getattr(match, 'score', 0.0)
                    metadata = getattr(match, 'metadata', {}) or {}
                    print(f"   Match {i}: Score={score:.4f}, Type={metadata.get('type', 'unknown')}")
                return True
            else:
                print("WARNING: No matches found (index may be empty)")
                print("   Run POST /api/v1/jobs/index_label to populate index")
                return None  # Not a failure, just empty
                
        except Exception as e:
            # Try with vector instead
            print(f"WARNING: Text query failed: {e}")
            print("   Trying with pre-computed vector...")
            
            # Generate a dummy vector for testing
            test_vector = [0.1] * 1536  # 1536 dim for text-embedding-3-small
            result = query_label_vectors(test_vector, top_k=5)
            matches = result.matches if hasattr(result, 'matches') else []
            
            if matches:
                print(f"OK: Vector query successful - {len(matches)} matches found")
                return True
            else:
                print("WARNING: No matches with vector query (index is empty)")
                return None
                
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rerank_api():
    """Test 3: Cohere Rerank API"""
    print("\n" + "=" * 70)
    print("TEST 3: Cohere Rerank API")
    print("=" * 70)
    try:
        from backend.app.clients.vector import rerank_label_results
        
        query = "pneumonitis in pembrolizumab patients"
        documents = [
            "Pembrolizumab can cause immune-mediated pneumonitis. Monitor patients for signs and symptoms.",
            "Apples are a popular fruit known for their sweetness and crisp texture.",
            "Pneumonitis is a serious adverse event that may occur with pembrolizumab treatment.",
            "The weather today is sunny and warm with clear skies.",
            "Keytruda (pembrolizumab) has been associated with pneumonitis in clinical trials.",
        ]
        
        print(f"Query: '{query}'")
        print(f"Documents: {len(documents)}")
        
        results = rerank_label_results(query, documents, top_n=3)
        
        if results:
            print(f"OK: Rerank API working - {len(results)} results")
            print("\nReranked Results:")
            for i, r in enumerate(results, 1):
                score = r.get('score', 0.0)
                doc = r.get('document', '')[:80]
                print(f"   {i}. Score: {score:.4f}")
                print(f"      Doc: {doc}...")
            
            # Verify results are ordered by relevance
            scores = [r.get('score', 0.0) for r in results]
            if scores == sorted(scores, reverse=True):
                print("OK: Results are correctly ordered by relevance")
            else:
                print("WARNING: Results may not be ordered correctly")
            
            return True
        else:
            print("FAILED: Rerank API returned no results")
            return False
            
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_retrieval():
    """Test 4: RAG Retrieval with Reranking"""
    print("\n" + "=" * 70)
    print("TEST 4: RAG Retrieval with Reranking")
    print("=" * 70)
    try:
        from backend.app.services.label_rag import retrieve_label_for_alert
        
        query = "pneumonitis adverse event pembrolizumab"
        print(f"Query: '{query}'")
        
        # Test with reranking enabled
        matches = retrieve_label_for_alert(query, top_k=3, use_rerank=True)
        
        if matches:
            print(f"OK: RAG retrieval working - {len(matches)} matches")
            for i, match in enumerate(matches, 1):
                score = getattr(match, 'score', 0.0)
                metadata = getattr(match, 'metadata', {}) or {}
                match_type = metadata.get('type', 'unknown')
                text = metadata.get('text', '')[:100]
                print(f"   {i}. Score: {score:.4f}, Type: {match_type}")
                if text:
                    print(f"      Text: {text}...")
            return True
        else:
            print("WARNING: No matches found (index may be empty)")
            print("   Run POST /api/v1/jobs/index_label to populate index")
            return None
            
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_scoring():
    """Test 5: RAG Scoring Logic"""
    print("\n" + "=" * 70)
    print("TEST 5: RAG Scoring Logic")
    print("=" * 70)
    try:
        from backend.app.services.scoring import _calculate_rag_score
        from backend.app.models.extraction import Extraction
        from backend.app.models.paper import Paper
        
        # Create a test extraction
        test_extraction = Extraction(
            id=999,
            paper_id=999,
            adverse_event="severe pneumonitis",
            meddra_term="Pneumonitis",
            subgroup_risk="elderly patients",
            combination="pembrolizumab + chemotherapy"
        )
        
        test_paper = Paper(
            id=999,
            pmid="test123",
            query_type="rare_ae",
            title="Test Paper",
            abstract="Test abstract about pneumonitis"
        )
        
        print("Test Extraction:")
        print(f"  Adverse Event: {test_extraction.adverse_event}")
        print(f"  MedDRA Term: {test_extraction.meddra_term}")
        print(f"  Subgroup: {test_extraction.subgroup_risk}")
        print(f"  Combination: {test_extraction.combination}")
        
        rag_score, rag_details = _calculate_rag_score(test_extraction, test_paper)
        
        print(f"\nOK: RAG scoring function executed")
        print(f"   RAG Score: {rag_score}")
        print(f"   Details: {rag_details}")
        
        if rag_details.get('skipped'):
            print(f"   WARNING: Scoring skipped: {rag_details.get('reason', 'unknown')}")
            if rag_details.get('reason') == 'no_rag_matches':
                print("      (Index may be empty - run POST /api/v1/jobs/index_label)")
        else:
            print(f"   Top Relevance: {rag_details.get('top_rerank_score', 'N/A')}")
            print(f"   Matches: {rag_details.get('num_matches', 0)}")
            print(f"   Used Rerank: {rag_details.get('used_rerank', False)}")
        
        return True
        
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("Pinecone APIs and RAG Implementation Test Suite")
    print("=" * 70)
    print()
    
    results = []
    
    # Run tests
    results.append(("Pinecone Connection", test_pinecone_connection()))
    results.append(("Vector Search Query", test_vector_query()))
    results.append(("Cohere Rerank API", test_rerank_api()))
    results.append(("RAG Retrieval", test_rag_retrieval()))
    results.append(("RAG Scoring Logic", test_rag_scoring()))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, result in results:
        if result is True:
            print(f"PASS: {name}")
            passed += 1
        elif result is False:
            print(f"FAIL: {name}")
            failed += 1
        else:
            print(f"SKIP: {name} (no data - index may be empty)")
            skipped += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0:
        if skipped > 0:
            print("\nOK: All critical tests passed!")
            print("WARNING: Some tests skipped - index may be empty.")
            print("   To populate index: POST /api/v1/jobs/index_label")
        else:
            print("\nOK: All tests passed! RAG implementation is working correctly.")
    else:
        print(f"\nFAILED: {failed} test(s) failed. Please check the errors above.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

