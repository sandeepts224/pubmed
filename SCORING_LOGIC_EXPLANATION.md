# Scoring Logic: Traditional DB Query + RAG Rerank Scoring

## Overview

The scoring system uses **two complementary approaches** that work together:
1. **Traditional DB Query Scoring** - Exact matches from structured database
2. **RAG Rerank Scoring** - Semantic similarity using vector search + reranking

Both scores are **added together** to create a comprehensive safety signal score.

---

## Complete Scoring Flow

```
Extraction (from paper)
    ↓
score_extraction()
    ↓
┌─────────────────────────────────────────────────────────┐
│  TRADITIONAL DB QUERY SCORING (5 checks)                │
├─────────────────────────────────────────────────────────┤
│  1. Novelty Check (0-35 points)                         │
│  2. Incidence Delta (0-30 points)                       │
│  3. Subpopulation (0-15 points)                        │
│  4. Temporal (0-10 points)                             │
│  5. Combination (0-10 points)                          │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  RAG RERANK SCORING (1 check)                          │
├─────────────────────────────────────────────────────────┤
│  6. Semantic Similarity (0-40 points)                  │
│     - Vector search → Rerank → Relevance score         │
└─────────────────────────────────────────────────────────┘
    ↓
Combine: base_sum = sum(all 6 scores)
    ↓
Apply Evidence Multiplier (1.0 - 2.0x)
    ↓
composite_score = base_sum × multiplier
    ↓
Alert if composite_score >= 50.0
```

---

## 1. Traditional DB Query Scoring

### Check 1: Novelty (0-35 points)
**Logic:** Is the adverse event term in the label database?

```python
on_label = term in label_terms_from_db

if not on_label:
    novelty = 25.0  # Not on label = novel
    if authors_claim_novel and (case_report or small_sample):
        novelty = 35.0  # Extra points for claimed novelty
else:
    novelty = 0.0  # Already on label = not novel
```

**Method:** Direct database query - exact string matching
- Query: `SELECT meddra_preferred_term FROM label_events WHERE label_version_id = X`
- Result: Set of normalized terms
- Match: Case-insensitive string comparison

---

### Check 2: Incidence Delta (0-30 points)
**Logic:** If on label, compare paper incidence vs label incidence

```python
if on_label and paper_incidence_pct:
    label_incidence = get_from_db(term)
    ratio = paper_incidence / label_incidence
    
    if ratio >= threshold:  # 2.0x or 2.5x depending on study type
        incidence_delta = min(30.0, 10.0 * (ratio - threshold + 1.0))
```

**Method:** Database lookup + mathematical comparison
- Query: `SELECT incidence_pct FROM label_events WHERE meddra_term = X`
- Calculation: Ratio-based scoring

---

### Check 3: Subpopulation (0-15 points)
**Logic:** Is the subgroup mentioned in label special populations?

```python
if extraction.subgroup_risk:
    label_subpops = get_special_populations_from_db()
    if subgroup not in label_subpops:
        subpop = 15.0  # Novel subgroup
```

**Method:** Database query + set membership check
- Query: `SELECT special_populations_json FROM label_events`
- Parse JSON and check if subgroup exists

---

### Check 4: Temporal (0-10 points)
**Logic:** Compare time-to-onset with label median

```python
if on_label and paper_time_to_onset:
    label_days = label_median_onset_months * 30
    ratio = paper_days / label_days
    
    if ratio >= 1.5 or ratio <= 0.67:  # 50% difference
        temporal = 10.0
```

**Method:** Database lookup + ratio calculation

---

### Check 5: Combination (0-10 points)
**Logic:** Is the drug combination mentioned in label interactions?

```python
if extraction.combination:
    label_interactions = get_interactions_from_db()
    if combination not in label_interactions:
        combo_score = 10.0  # Novel combination
```

**Method:** Database query + string matching

---

## 2. RAG Rerank Scoring

### Check 6: Semantic Similarity (0-40 points)
**Logic:** How semantically similar is the extraction to label content?

### Step-by-Step RAG Process:

#### Step 1: Build Query Text
```python
query_parts = [
    extraction.adverse_event,
    extraction.meddra_term,
    f"subgroup: {extraction.subgroup_risk}",
    f"combination: {extraction.combination}"
]
query_text = " ".join(query_parts)
# Example: "pneumonitis immune-mediated pneumonitis subgroup: elderly combination: pembrolizumab + chemotherapy"
```

#### Step 2: Vector Search (Initial Retrieval)
```python
# Pinecone vector search - gets top 15 candidates
matches = query_label_vectors(query_text, top_k=15)
# Returns: List of label chunks with vector similarity scores
```

**What happens:**
- Query text → Pinecone embedding (OpenAI text-embedding-3-small)
- Vector similarity search in Pinecone index
- Returns top-15 most similar label chunks

#### Step 3: Reranking (Cohere Rerank v3.5)
```python
# Extract document texts from matches
documents = [match.metadata['text'] for match in matches]

# Rerank using Cohere Rerank v3.5
reranked = rerank_label_results(query_text, documents, top_n=5)
# Returns: Top 5 most relevant chunks with relevance scores (0-1+)
```

**What happens:**
- Cohere Rerank analyzes query-document relationships
- Cross-encoder model understands semantic relevance better than vector similarity
- Reorders results: most relevant first
- Returns relevance scores (higher = more relevant to query)

#### Step 4: Calculate RAG Score
```python
top_relevance = max(rerank_scores)  # Best relevance score

# Convert relevance to novelty score (inverse relationship)
if top_relevance < 0.3:
    rag_score = 40.0  # Low relevance = high novelty = high score
elif top_relevance < 0.5:
    rag_score = 25.0
elif top_relevance < 0.7:
    rag_score = 10.0
else:
    rag_score = 0.0  # High relevance = well-documented = low novelty

# Penalty if multiple high-relevance matches
if high_relevance_matches >= 3:
    rag_score = max(0.0, rag_score - 10.0)
```

**Key Insight:** 
- **High Rerank Score** = Very relevant to label = Already documented = **Low Novelty** = **Low Score**
- **Low Rerank Score** = Not relevant to label = Novel finding = **High Novelty** = **High Score**

---

## 3. Combining Scores

### Base Sum Calculation
```python
base_sum = (
    novelty +           # 0-35 points (DB)
    incidence_delta +   # 0-30 points (DB)
    subpop +            # 0-15 points (DB)
    temporal +          # 0-10 points (DB)
    combo_score +       # 0-10 points (DB)
    rag_score           # 0-40 points (RAG)
)
# Total possible: 0-140 points
```

### Evidence Multiplier
```python
multiplier = 1.0

# Study type multiplier
if "retrospective" in study_type:
    multiplier *= 1.5
elif "registry" in study_type:
    multiplier *= 1.4

# Sample size multiplier
if sample_size >= 2000:
    multiplier *= 1.3
elif sample_size >= 500:
    multiplier *= 1.2

composite_score = base_sum × multiplier
```

### Alert Threshold
```python
if composite_score >= 50.0:
    create_alert(status="pending_review")
```

---

## Why Both Approaches Work Together

### Traditional DB Scoring Strengths:
✅ **Exact matches** - Precise term matching
✅ **Structured data** - Incidence, temporal, combinations
✅ **Fast** - Direct database queries
✅ **Deterministic** - Same input = same output

### Traditional DB Scoring Limitations:
❌ **Exact matching only** - Misses semantic variations
❌ **No context** - Doesn't understand meaning
❌ **Misses related concepts** - "pneumonitis" vs "interstitial lung disease"

### RAG Rerank Scoring Strengths:
✅ **Semantic understanding** - Captures meaning, not just words
✅ **Context-aware** - Understands relationships
✅ **Catches variations** - "pneumonitis" matches "interstitial lung disease"
✅ **Reranking improves precision** - Better relevance than vector search alone

### RAG Rerank Scoring Limitations:
❌ **Slower** - Requires API calls (vector search + rerank)
❌ **Less precise for exact matches** - May miss exact term matches
❌ **Requires indexed data** - Needs Pinecone to be populated

---

## Example Scenario

### Extraction:
- Adverse Event: "severe pneumonitis"
- MedDRA Term: "Pneumonitis"
- Incidence: 5.2%
- Subgroup: "elderly patients with COPD"
- Study Type: "retrospective_cohort"
- Sample Size: 1500

### Traditional DB Scoring:
1. **Novelty:** "Pneumonitis" found in DB → `on_label = True` → `novelty = 0`
2. **Incidence:** Label says 2.1%, paper says 5.2% → ratio = 2.48x → `incidence_delta = 20.0`
3. **Subpopulation:** "elderly COPD" not in label → `subpop = 15.0`
4. **Temporal:** No time-to-onset data → `temporal = 0`
5. **Combination:** No combination → `combo_score = 0`
   
**DB Total: 35.0 points**

### RAG Rerank Scoring:
1. **Query:** "severe pneumonitis Pneumonitis subgroup: elderly patients with COPD"
2. **Vector Search:** Finds 15 label chunks about pneumonitis
3. **Rerank:** Cohere identifies most relevant chunks:
   - Chunk 1: "Pneumonitis in elderly patients" → relevance: 0.85
   - Chunk 2: "Pneumonitis general" → relevance: 0.72
   - Chunk 3: "COPD-related adverse events" → relevance: 0.65
4. **Score Calculation:**
   - Top relevance: 0.85 (high relevance)
   - High relevance = well-documented = low novelty
   - `rag_score = 0.0`
   - But 3 high-relevance matches → penalty → `rag_score = 0.0` (already at 0)

**RAG Total: 0.0 points**

### Final Score:
```
base_sum = 35.0 + 0.0 = 35.0
multiplier = 1.5 (retrospective) × 1.2 (sample_size >= 500) = 1.8
composite_score = 35.0 × 1.8 = 63.0

Result: Alert created (63.0 >= 50.0)
```

---

## Key Differences

| Aspect | Traditional DB | RAG Rerank |
|--------|---------------|------------|
| **Method** | Exact string matching | Semantic similarity |
| **Data Source** | Structured database | Vector embeddings |
| **Matching** | Term-by-term | Context-aware |
| **Speed** | Fast (DB query) | Slower (API calls) |
| **Precision** | High for exact matches | High for semantic matches |
| **Coverage** | Structured fields only | Full text context |
| **Example** | "pneumonitis" = "pneumonitis" | "pneumonitis" ≈ "interstitial lung disease" |

---

## Why Reranking Matters

### Without Reranking:
- Vector search might return semantically similar but not actually relevant results
- Example: Query "pneumonitis in elderly" might match "pneumonitis in children" (similar vectors, different context)

### With Reranking:
- Cohere Rerank understands query-document relationships
- Reorders results: most relevant first
- Example: "pneumonitis in elderly" correctly prioritizes "pneumonitis in elderly patients" over "pneumonitis in children"

---

## Summary

**The scoring system is additive and complementary:**

1. **DB Scoring** catches exact matches and structured differences
2. **RAG Scoring** catches semantic variations and contextual relevance
3. **Together** they provide comprehensive coverage:
   - DB finds what's explicitly documented
   - RAG finds what's semantically related
   - Combined score reflects both explicit and implicit novelty

**The final score = DB Score + RAG Score × Evidence Multiplier**

This dual approach ensures we don't miss safety signals that might be:
- Explicitly novel (caught by DB)
- Semantically novel (caught by RAG)
- Or both (higher combined score)

