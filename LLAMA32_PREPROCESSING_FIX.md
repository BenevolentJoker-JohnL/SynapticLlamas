# llama3.2 Response Preprocessing Fix

**Date**: 2025-10-15
**Issue**: llama3.2:3b on CPU generating malformed JSON responses (60% failure rate)
**Solution**: Aggressive preprocessing layer before TrustCall validation

## Problem

llama3.2:3b running on CPU was producing unreliable JSON outputs during long-form generation:

1. **Literal schema copying**: Model would return `{"context": str}` instead of `{"context": "actual content"}`
2. **Markdown wrapping**: Responses wrapped in ` ```json ... ``` ` code blocks
3. **Mixed content**: JSON mixed with explanatory text before/after
4. **Format confusion**: Adding explanations instead of just returning JSON

This caused 3 out of 5 chunks to fail during long-form generation, resulting in very short final output.

### Example Failures

```json
// Instead of actual content:
{"context": str}

// Or wrapped in markdown:
```json
{"context": "content"}
```

// Or with explanations:
Here's the answer: {"context": "content"}
```

## Solution

Implemented **aggressive preprocessing** specifically for llama3.2 responses that runs BEFORE TrustCall validation.

### Implementation

**Location**: `/home/joker/SynapticLlamas/agents/base_agent.py`

**New function**: `preprocess_llama32_response()` at lines 20-170

**Integration points**:
- HybridRouter path: lines 522-531 (preprocesses before TrustCall)
- Regular Ollama path: lines 678-687 (preprocesses before TrustCall)

### Preprocessing Steps

The function performs these operations in order:

1. **Strip markdown code blocks**
   - Detects and removes ` ```json ... ``` ` wrappers
   - Extracts content from code blocks

2. **Detect literal schema copies**
   - Checks if field values are Python type names (`str`, `dict`, `list`, etc.)
   - Falls through to content extraction if detected

3. **Extract actual content**
   - Uses multiple regex patterns to find substantive text:
     - JSON field content (>100 chars)
     - Text after keywords like "explanation:", "answer:", etc.
     - Substantial paragraphs (>200 chars)
   - Filters out JSON syntax and schema keywords
   - Extracts content words (>20 words minimum)

4. **Force into proper schema**
   - Maps extracted content to appropriate schema fields
   - For `str` fields: uses extracted content
   - For `list` fields: provides empty list (TrustCall can repair)
   - For `dict` fields: provides empty dict
   - Builds valid JSON structure

5. **Fallback extraction**
   - Tries to extract any JSON object from response
   - Returns minimal valid JSON with error indicator if all else fails

### Example Transformations

#### Before (literal schema):
```json
{"context": str}
```

#### After (minimal valid JSON):
```json
{"context": "[Failed to extract content - see raw output]"}
```

---

#### Before (markdown wrapped):
```json
```json
{"context": "Quantum entanglement is a phenomenon..."}
```
```

#### After (clean JSON):
```json
{"context": "Quantum entanglement is a phenomenon..."}
```

---

#### Before (mixed content):
```
Here's the answer:

Quantum entanglement is a phenomenon that occurs when particles become correlated...
```

#### After (forced into schema):
```json
{"context": "Quantum entanglement is a phenomenon that occurs when particles become correlated..."}
```

## Testing

Created test script: `/home/joker/SynapticLlamas/test_llama32_preprocessing.py`

Tested 5 scenarios:
1. ✅ Literal schema copy detection
2. ✅ Markdown stripping
3. ✅ Mixed content extraction
4. ✅ Valid JSON pass-through
5. ✅ Plain text extraction and forcing

All tests passed successfully.

## Expected Impact

This preprocessing layer should significantly improve llama3.2 reliability:

**Before**:
- 60% of chunks failing (returning `{"context": str}`)
- TrustCall regeneration making it worse (model copies schema examples)
- Final output only 2/5 chunks

**After**:
- Preprocessing extracts actual content before TrustCall validation
- Even if model returns malformed JSON, content is extracted and forced into schema
- TrustCall receives clean JSON to work with
- Should increase success rate from 40% to 90%+

## Integration with Existing Systems

- Works with HybridRouter RPC backend
- Works with regular Ollama API
- Runs BEFORE TrustCall validation (not replacing it)
- Only activates for models with 'llama3.2' in name
- Transparent to rest of system (still returns valid JSON)

## Related Fixes

This complements other recent fixes:
- Citation injection (now working)
- Synthesis preservation (skip when >15K chars)
- Chunk filtering (skip "str", "dict", <50 chars)
- Unusable synthesis detection

Together, these fixes should resolve the "skimpy length" and "lack of citations" issues for long-form generation.

## Future Improvements

1. **Extend to other small models**: Could apply same preprocessing to llama3.1:3b, phi-3, etc.
2. **Content extraction refinement**: Could improve regex patterns for better content detection
3. **Schema-aware extraction**: Could use schema structure to better map extracted content
4. **Telemetry**: Track preprocessing success rate and most common failure modes

## Files Modified

- `/home/joker/SynapticLlamas/agents/base_agent.py` - Added preprocessing function and integration

## Files Created

- `/home/joker/SynapticLlamas/test_llama32_preprocessing.py` - Test script
- `/home/joker/SynapticLlamas/LLAMA32_PREPROCESSING_FIX.md` - This documentation
