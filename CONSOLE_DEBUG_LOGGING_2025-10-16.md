# Console Output Debug Logging Added

**Date**: 2025-10-16
**Issue**: Raw API response still appearing despite fix
**Status**: 🔍 DEBUGGING - Added logging to diagnose

## Problem

After adding the console output fix, raw API responses are STILL being dumped:

```
╔═══ FINAL ANSWER ═══╗
║ 'choices' 'finish_reason' 'length' 'index' 'message' 'role' 'assistant' 'content' String theory...║
╚═════════════════════╝
```

This suggests that:
1. Either `markdown_output` is empty/false → fallback to `print_json_output()`
2. Or `result['result']` structure is completely malformed

## Debug Logging Added

**File**: `/home/joker/SynapticLlamas/main.py` (lines 1356-1392)

Added comprehensive logging to track:
1. **What's in `markdown_output`** before extraction attempts
2. **What keys exist in `result['result']`** to understand structure
3. **Which extraction path succeeds** (Ollama vs OpenAI vs fallback)
4. **Why fallback happens** if no content extracted

### New Logging

```python
# Debug logging
logger.debug(f"DEBUG: markdown_output type: {type(markdown_output)}")
logger.debug(f"DEBUG: markdown_output length: {len(str(markdown_output)) if markdown_output else 0}")
logger.debug(f"DEBUG: result['result'] keys: {list(result['result'].keys()) if isinstance(result['result'], dict) else 'NOT A DICT'}")

# If no final_output, try to extract from nested structure
if not markdown_output or not isinstance(markdown_output, str):
    # Try common response structures
    result_data = result['result']
    if 'message' in result_data and isinstance(result_data['message'], dict):
        # Ollama response format
        markdown_output = result_data['message'].get('content', '')
        logger.info(f"✅ Extracted content from Ollama format (length: {len(markdown_output)} chars)")
    elif 'choices' in result_data and isinstance(result_data['choices'], list):
        # OpenAI response format
        if len(result_data['choices']) > 0:
            choice = result_data['choices'][0]
            if 'message' in choice:
                markdown_output = choice['message'].get('content', '')
                logger.info(f"✅ Extracted content from OpenAI format (length: {len(markdown_output)} chars)")

if isinstance(markdown_output, str) and markdown_output:
    logger.info(f"📄 Displaying markdown panel (length: {len(markdown_output)} chars)")
    console.print(Panel(...))
else:
    # Fallback to cleaned JSON output
    logger.warning(f"⚠️  No markdown content found, falling back to JSON display")
    logger.warning(f"   markdown_output: {repr(markdown_output)[:100]}")
    print_json_output(result['result'])
```

## What to Look For Next Time

When you run a query, check the logs for:

### Success Path
```
INFO - ✅ Extracted content from OpenAI format (length: 1234 chars)
INFO - 📄 Displaying markdown panel (length: 1234 chars)
```

### Failure Path
```
WARNING - ⚠️  No markdown content found, falling back to JSON display
WARNING -    markdown_output: ''
```

### Debug Info
```
DEBUG - DEBUG: markdown_output type: <class 'str'>
DEBUG - DEBUG: markdown_output length: 0
DEBUG - DEBUG: result['result'] keys: ['choices', 'created', 'model', 'usage', ...]
```

## Possible Root Causes

Based on your output, the likely issue is:

### Hypothesis 1: `result['result']` is Malformed
The orchestrator is returning `result['result']` as a raw API response dict instead of wrapping it properly:

```python
# WRONG (what might be happening):
return {
    'result': raw_api_response,  # This is {'choices': [...], 'usage': {...}}
    'metrics': {...}
}

# RIGHT (what should happen):
return {
    'result': {
        'final_output': extracted_content,
        'metadata': {...}
    },
    'metrics': {...}
}
```

### Hypothesis 2: Orchestrator Not Using Agents Properly
The distributed orchestrator might be bypassing agents and calling LLM APIs directly, returning raw responses without post-processing.

### Hypothesis 3: Agent Response Format Changed
Agents might be returning data in a new format that doesn't match extraction logic.

## Next Steps

1. **Run a test query** and check logs to see which path executes
2. **Check log output** for the DEBUG messages showing `result['result']` keys
3. **Identify where `result['result']` comes from** in distributed_orchestrator.py
4. **Fix the orchestrator** to properly extract/wrap content before returning

## Testing

```bash
cd /home/joker/SynapticLlamas
python main.py --interactive --distributed

# Run a query and check logs:
SynapticLlamas> Explain string theory

# Look for these log lines:
# DEBUG: result['result'] keys: [...]
# WARNING: No markdown content found...
# OR
# ✅ Extracted content from OpenAI format
```

## Files Modified

- `/home/joker/SynapticLlamas/main.py` (lines 1359-1392)
  - Added debug logging before extraction
  - Added info logging for successful extraction
  - Added warning logging for fallback case

## Status

🔍 **DEBUGGING** - Logging added, waiting for next test run to diagnose root cause

The debug logs will tell us exactly why the extraction is failing and what structure `result['result']` actually has.
