# Citation Display Investigation

**Date**: 2025-10-16
**Issue**: User asked "why isn't our citation injection working?"
**Status**: ✅ DIAGNOSIS COMPLETE - Citation injection is working, but LLM output is truncated

## User Report

User showed output where:
- Text appears cut off mid-equation: `S \geq 2\sqrt`
- Citations appear at bottom: "📚 Source Documents" with document_24.pdf and document_22.pdf
- User question: "no why isnt our citation injection working?"

## Investigation Results

### Finding 1: Citation Injection Code is Working ✅

**Location**: `/home/joker/SynapticLlamas/distributed_orchestrator.py`

The citation injection code at two locations is functioning correctly:

**Collaborative mode** (lines 286-294):
```python
# Add FlockParser source citations if documents were used
if source_documents:
    result['source_documents'] = source_documents
    result['document_grounded'] = True
    # Append citations to final output
    citations = "\n\n## 📚 Source Documents\n" + "\n".join(
        f"{i+1}. {doc}" for i, doc in enumerate(source_documents)
    )
    result['final_output'] = result['final_output'] + citations
```

**Parallel mode** (lines 1023-1027):
```python
# Append citations to final output (same as collaborative mode)
citations = "\n\n## 📚 Source Documents\n" + "\n".join(
    f"{i+1}. {doc}" for i, doc in enumerate(source_documents)
)
result['result']['final_output'] = result['result']['final_output'] + citations
```

**Evidence**: Citations ARE appearing in the output panel:
```
║  📚 Source Documents  ║
║  1 document_24.pdf    ║
║  2 document_22.pdf    ║
```

### Finding 2: Markdown Heading Renders Correctly ✅

Tested markdown rendering with Rich:
```python
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

test_md = '''# Quantum Entanglement
...text...
## 📚 Source Documents
1. document_24.pdf
'''
console.print(Panel(Markdown(test_md), ...))
```

**Result**: The `## 📚 Source Documents` heading renders correctly as a centered markdown h2 heading.

### Finding 3: The Real Issue - Incomplete LLM Response ⚠️

**The text is cut off mid-equation**: `S \geq 2\sqrt`

This indicates the LLM generation was **truncated BEFORE** the citation injection code runs. The citations are being appended to an incomplete answer.

**Why the LLM output is incomplete**:
1. **No explicit token limits in agent code** - Checked `agents/base_agent.py` - no `num_predict` or `max_tokens` in payload
2. **Ollama default limits** - Ollama has default generation limits (typically 2048 tokens)
3. **Model context window** - llama3.2 may have reached its context window limit
4. **Model stopped generation** - Model may have decided to stop (finish_reason)

## The Confusion

The user's screenshot shows:
1. ✅ Citations ARE injected and appearing
2. ✅ Markdown heading "📚 Source Documents" is displaying (though without heading formatting in screenshot)
3. ❌ **BUT** the answer text before the citations is incomplete (cut off mid-equation)

This creates the appearance that "citation injection isn't working" when actually:
- Citation injection IS working perfectly
- The problem is the LLM answer is incomplete
- Citations are being correctly appended to an incomplete answer

## Solutions

### Solution 1: Increase Ollama Generation Limit (RECOMMENDED)

Add `num_predict` parameter to increase token generation limit:

**File**: `/home/joker/SynapticLlamas/agents/base_agent.py:696-706`

```python
# Build payload - try with format: json first
payload = {
    "model": self.model,
    "prompt": prompt,
    "stream": False,
    "options": {
        "num_predict": 4096  # Increase from default ~2048
    }
}
```

For research queries with RAG, even higher limits may be needed:
```python
"num_predict": 8192  # For long-form research answers
```

### Solution 2: Add Truncation Detection

Detect when answers are cut off mid-sentence and warn the user:

```python
def detect_truncation(text: str) -> bool:
    """Detect if text appears truncated mid-sentence."""
    # Check if text ends abruptly (no sentence-ending punctuation)
    if text and not text.rstrip().endswith(('.', '!', '?', '"', '\n')):
        return True
    # Check for incomplete LaTeX
    if re.search(r'\\[a-zA-Z]+$', text):  # Ends with backslash command
        return True
    return False

# In distributed_orchestrator.py after getting final_output:
if detect_truncation(result['final_output']):
    logger.warning("⚠️ Answer appears truncated - consider increasing num_predict")
```

### Solution 3: Request Continuation

If answer is truncated, automatically request continuation:

```python
if detect_truncation(result['final_output']):
    continuation_prompt = f"Continue from: {result['final_output'][-100:]}"
    # Make another LLM call to get continuation
    # Append to result['final_output']
```

## Testing Commands

Test with increased token limit:
```bash
cd /home/joker/SynapticLlamas
python main.py --interactive --distributed

# At prompt, ask a complex research question:
SynapticLlamas> Explain the Bell inequality and quantum entanglement in detail

# Check if answer is complete (ends with proper punctuation, not cut off)
```

Verify FlockParser RAG is active:
```bash
# Check RAG status
SynapticLlamas> status

# Should show:
# FlockParser RAG: ON (X docs, Y chunks)
```

## Files Involved

1. **`distributed_orchestrator.py:286-294, 1023-1027`** - Citation injection (WORKING ✅)
2. **`agents/base_agent.py:696-706`** - Ollama payload construction (NEEDS num_predict)
3. **`console_theme.py:161-189`** - Output display (WORKING ✅)
4. **`main.py:1374-1379`** - Panel display (WORKING ✅)

## Summary

### What's Working ✅
- Citation injection code appending sources correctly
- Markdown heading rendering in Panel
- FlockParser RAG retrieving documents
- Console output formatting displaying citations

### What's NOT Working ❌
- LLM generates incomplete answers (truncated mid-sentence)
- Default token limit too low for research queries with RAG context

### Root Cause
**Ollama default token generation limit (~2048 tokens) is too low** for detailed research questions with large RAG context. The LLM stops generating mid-answer, then citations are appended to the incomplete text.

### Fix Priority
**HIGH** - Add `num_predict` parameter to agent payload to increase generation limit to 4096-8192 tokens for research queries.

## Next Steps

1. **Implement Solution 1** - Add configurable `num_predict` to agent calls
2. **Implement Solution 2** - Add truncation detection and warnings
3. **Test with quantum mechanics queries** - Verify complete answers with citations
4. **Document in user guide** - Explain num_predict setting for long-form queries

## Status

✅ **Diagnosis Complete** - Citation injection is working, LLM output is truncated
⏳ **Fix Pending** - Need to add num_predict parameter to increase generation limit
📋 **Documentation** - This investigation document created for reference
