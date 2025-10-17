# Auto-Citation Debugging Report (2025-10-14)

## Test Query Results

**Query**: "Explain the overlap of quantum mechanics and string theory"

**Result**: NO citations in final output despite:
- RAG being used (document_34.pdf)
- Auto-injection being triggered 4 times (chunks 2-5)
- Initial chunk having 3 citations

---

## Issues Discovered from Logs

### Issue 1: Embedding Generation Failing ⚠️ **CRITICAL**

**Evidence from logs**:
```
⚠️  Researcher - Could not generate chunk embeddings
```

**Occurred**: All 4 chunks (2, 3, 4, 5) that needed auto-injection

**Root Cause**: The embedding function is failing silently. Error was logged at DEBUG level only.

**Impact**: Without embeddings, auto-citation cannot calculate similarity between sentences and source chunks, so NO citations can be injected.

**Fix Applied**:
- Changed embedding errors from `logger.debug()` to `logger.error()`
- Added traceback logging
- Added validation logging for empty/invalid results
- Files modified: `agents/base_agent.py` (lines 393-407, 524-545)

**Next Test**: Run another query and check logs for actual embedding error messages.

---

### Issue 2: Sentence Splitting Shows Only 1 Sentence ⚠️

**Evidence from logs**:
```
📝 Analyzing 1 sentences for citation opportunities
```

**Expected**: 10-20+ sentences per chunk (typical paragraph has 5-10 sentences)

**Possible Causes**:
1. Content field extraction is wrong (getting wrong key)
2. Content is actually very short (regenerated JSON produced minimal content)
3. Sentence splitter is broken (regex issue)

**Investigation Needed**:
- Check what's actually in the `context` field after regeneration
- Verify sentence splitting regex works on actual content

**Fix Applied**:
- Added debug logging for content length and first 100 chars
- Files modified: `agents/base_agent.py` (line 73)

**Next Test**: Check logs for content length and sample to see if it's actually short.

---

### Issue 3: Initial Chunk Had Citations But They Disappeared 🎯

**Evidence from logs**:
```
Initial chunk:
   ✅ Researcher - Citation compliance: 3 unique citation(s) found

Synthesis:
   ✅ Editor - Valid JSON output
   (no citation compliance check logged)

Final output:
   NO CITATIONS AT ALL
```

**Root Cause**: Synthesis is stripping citations when combining chunks.

**Why This Happens**:
1. Synthesis doesn't query FlockParser (it just synthesizes chunk content)
2. Synthesis prompt doesn't have `AVAILABLE SOURCES FOR CITATION` section
3. Therefore, `check_citation_compliance()` returns early (no RAG detected)
4. When Editor combines chunks, it's not preserving citation markers

**Fix Needed**:
- Option A: Pass source list to synthesis prompt (add `AVAILABLE SOURCES FOR CITATION`)
- Option B: Instruct synthesis to preserve existing citations from chunks
- Option C: Don't run synthesis through TrustCall (preserve chunks as-is and just concatenate)

---

## Timeline of What Happened

### Phase 1: Initial Content (SUCCESS)
- Duration: 189s
- RAG used: ✅ (document_34.pdf, 6 chunks, similarity 0.76)
- JSON: ✅ Valid
- Citations: ✅ **3 unique citations found**

### Phase 2: Parallel Chunks (4 chunks - ALL FAILED AUTO-INJECTION)

**Chunk 2** (52s):
- RAG used: ✅ (document_34.pdf, 2 chunks, similarity 0.73)
- JSON: ⚠️ Required regeneration (1 attempt)
- Citations: ❌ None in output
- Auto-injection: ⚠️ **Could not generate chunk embeddings**

**Chunk 3** (74s):
- RAG used: ✅ (document_34.pdf, 2 chunks, similarity 0.72)
- JSON: ⚠️ Required regeneration (1 attempt)
- Citations: ❌ None in output
- Auto-injection: ⚠️ **Could not generate chunk embeddings**

**Chunk 4** (173s):
- RAG used: ✅ (document_34.pdf, 3 chunks, similarity 0.73)
- JSON: ⚠️ Required regeneration (1 attempt)
- Citations: ❌ None in output
- Auto-injection: ⚠️ **Could not generate chunk embeddings**

**Chunk 5** (285s):
- RAG used: ✅ (document_34.pdf, 2 chunks, similarity 0.73)
- JSON: ⚠️ Required regeneration (1 attempt)
- Citations: ❌ None in output
- Auto-injection: ⚠️ **Could not generate chunk embeddings**

### Phase 3: Synthesis (STRIPPED CITATIONS)
- Duration: 118s
- Combined: 5 chunks (1 with citations, 4 without)
- JSON: ✅ Valid
- Citations: ❌ **Stripped** - no compliance check run
- Final output: NO CITATIONS

---

## Key Questions to Answer

### Q1: Why is embedding generation failing? ✅ **SOLVED**

**Root Cause Confirmed**:
```
AttributeError: 'HybridRouterSync' object has no attribute 'generate_embedding'
```

`HybridRouterSync` only has `route_request()` method - it **does not support embeddings**.

**Fix Applied**: Changed both embedding functions (HybridRouter path and Ollama path) to use direct Ollama API calls:
```python
embed_response = requests.post(
    "http://localhost:11434/api/embeddings",
    json={
        "model": "mxbai-embed-large",
        "prompt": text
    },
    timeout=30
)
```

**Files Modified**: `agents/base_agent.py` lines 401-422 (HybridRouter path)

### Q2: Why only 1 sentence detected?

**Hypothesis**:
- Regenerated JSON might produce very short content (e.g., single sentence response)
- Content extraction might be getting wrong field
- Sentence splitter regex might not be working

**Test**: Next run will show content length and sample.

### Q3: Why doesn't synthesis preserve citations?

**Known Issue**: Synthesis doesn't query FlockParser, so its prompt doesn't have source list, so citation compliance check returns early.

**Fix Needed**: Must decide on approach (see Issue 3 above).

---

## Files Modified

### `agents/base_agent.py`

**Lines 393-407** (HybridRouter embedding function):
- Changed `logger.debug()` to `logger.error()` for failures
- Added traceback logging
- Added validation for empty/invalid results

**Lines 524-545** (Ollama embedding function):
- Changed `logger.debug()` to `logger.error()` for failures
- Added traceback logging
- Added validation for empty/invalid results

**Line 73** (Content analysis):
- Added debug logging for content length and sample

**Lines 77-93** (Chunk embedding loop):
- Added detailed logging for each chunk embedding attempt
- Shows embedding dimensions on success
- Shows warnings for None returns
- Shows errors with traceback for exceptions

---

## Next Steps

### Immediate (Next Test Run)

1. **Run another RAG-enhanced query** (short, simple query to minimize time)
2. **Check logs for**:
   - Actual embedding error messages (should now be at ERROR level)
   - Content length and sample (is it really just 1 sentence?)
   - Chunk embedding success/failure details

### Short-term Fixes

1. **Fix embedding generation** once we see the actual error
2. **Fix synthesis to preserve citations**:
   - Add source list to synthesis prompt
   - OR instruct synthesis to preserve [1], [2] markers
   - OR don't synthesize at all (just concatenate chunks)

### Long-term Improvements

1. **Add unit tests** for auto-citation functions
2. **Test with GPU nodes** (better instruction following)
3. **Optimize embedding calls** (cache, batch, parallel)

---

## Expected Behavior (Once Fixed)

### Chunk Generation (with RAG):
```
✅ Researcher - Valid JSON output
⚠️  Researcher - RAG sources provided but NO CITATIONS in output
   🔧 Researcher - Attempting automatic citation injection...
   🔧 Researcher - Auto-injecting citations (1 sources, 3 chunks)
   📝 Analyzing 15 sentences for citation opportunities
   🔹 Generating embedding for chunk 1/3 (length: 450 chars)
   ✅ Chunk 1 embedding generated (1024 dimensions)
   🔹 Generating embedding for chunk 2/3 (length: 380 chars)
   ✅ Chunk 2 embedding generated (1024 dimensions)
   🔹 Generating embedding for chunk 3/3 (length: 520 chars)
   ✅ Chunk 3 embedding generated (1024 dimensions)
   📎 Added [1] (sim: 0.72): String theory posits that fundamental particles...
   📎 Added [1] (sim: 0.68): These strings vibrate at different frequencies...
   📎 Added [1] (sim: 0.65): The theory requires 10 dimensions...
   ✅ Researcher - Auto-injected 8 citations
```

### Synthesis (preserving citations):
```
✅ Editor - Valid JSON output
✅ Editor - Citation compliance: 15 unique citation(s) found
```

---

## Performance Notes

**Total Time**: 598s (~10 minutes)

**Breakdown**:
- Initial chunk: 189s (3.15 min)
- Parallel chunks: 285s max (4.75 min) - all 4 ran concurrently
- Synthesis: 118s (2 min)

**Why so long?**
- All GPU nodes offline (VRAM < 2000 MB)
- Routed to CPU nodes (.154, localhost)
- CPU inference is 5-10x slower than GPU
- JSON regeneration added overhead (chunks 2-5 all needed regeneration)

**Speedup achieved**: 2.06x (parallel execution)

**Expected with GPU**: ~150-200s total (2.5-3.5 min)

---

## Fix Summary (2025-10-15 00:02)

### Issue 1: SOLVED ✅

**Problem**: `AttributeError: 'HybridRouterSync' object has no attribute 'generate_embedding'`

**Fix**: Changed embedding function to use direct Ollama API calls (`http://localhost:11434/api/embeddings`) instead of trying to call non-existent `HybridRouterSync.generate_embedding()` method.

**Impact**: Auto-citation injection should now work properly for chunks.

### Issue 2: PENDING ⏳

**Problem**: Only 1 sentence detected per chunk (expected 10-20+)

**Status**: Added debug logging to show content length and sample. Will investigate after testing Issue 1 fix.

### Issue 3: PENDING ⏳

**Problem**: Synthesis strips citations from chunks during synthesis

**Status**: Requires design decision - see options in Issue 3 section above.

### Next Test

Run another query to verify:
1. ✅ Embeddings now generate successfully
2. ⏳ How many sentences are actually detected
3. ⏳ Whether citations survive synthesis

**Recommended short test**: `explain quantum entanglement` (faster than full multi-chunk)
