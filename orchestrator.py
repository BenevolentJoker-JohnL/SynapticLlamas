from concurrent.futures import ThreadPoolExecutor, as_completed
from agents.researcher import Researcher
from agents.critic import Critic
from agents.editor import Editor
from aggregator import aggregate_metrics
from json_pipeline import merge_json_outputs, validate_json_output
from json_to_markdown import json_to_markdown
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_parallel_agents(input_data, model="llama3.2", max_workers=3):
    """
    Run agents in parallel and aggregate their outputs.

    Args:
        input_data: Input text/prompt for agents to process
        model: Ollama model to use (default: llama3.2)
        max_workers: Maximum number of parallel workers

    Returns:
        dict with 'result' (final markdown), 'metrics', and 'raw_json'
    """
    logger.info(f"Starting parallel agent execution with model: {model}")

    # Initialize agents
    researcher = Researcher(model)
    critic = Critic(model)

    json_outputs = []
    metrics = []
    node_info = []  # Track which nodes agents used

    # Execute researcher and critic in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_agent = {
            executor.submit(researcher.process, input_data): researcher,
            executor.submit(critic.process, input_data): critic
        }

        for future in as_completed(future_to_agent):
            agent = future_to_agent[future]
            try:
                json_result = future.result()

                # Validate JSON output
                if validate_json_output(json_result):
                    json_outputs.append(json_result)
                    logger.info(f"{agent.name} completed in {agent.execution_time:.2f}s [JSON validated]")
                else:
                    logger.warning(f"{agent.name} output did not pass validation")
                    json_outputs.append(json_result)

                metrics.append(agent.get_metrics())

                # Track node usage
                node_info.append({
                    'agent': agent.name,
                    'node': agent.ollama_url,
                    'time': agent.execution_time
                })
            except Exception as e:
                error_output = {
                    "agent": agent.name,
                    "status": "error",
                    "format": "text",
                    "data": {"error": str(e)}
                }
                json_outputs.append(error_output)
                logger.error(f"{agent.name} failed: {str(e)}")

    # Prepare editor input with researcher + critic outputs
    editor_input = f"""Original Query: {input_data}

Researcher Output:
{json.dumps(json_outputs[0], indent=2)}

Critic Output:
{json.dumps(json_outputs[1], indent=2) if len(json_outputs) > 1 else 'N/A'}"""

    # Run editor to synthesize final markdown
    editor = Editor(model)
    try:
        editor_output = editor.process(editor_input)
        json_outputs.append(editor_output)
        metrics.append(editor.get_metrics())
        logger.info(f"Editor completed in {editor.execution_time:.2f}s [JSON validated]")

        # Track editor node usage
        node_info.append({
            'agent': editor.name,
            'node': editor.ollama_url,
            'time': editor.execution_time
        })
    except Exception as e:
        error_output = {
            "agent": "Editor",
            "status": "error",
            "format": "text",
            "data": {"error": str(e)}
        }
        json_outputs.append(error_output)
        logger.error(f"Editor failed: {str(e)}")

    # Convert editor JSON to markdown
    final_markdown = json_to_markdown(editor_output)

    # Merge JSON outputs for history
    final_metrics = aggregate_metrics(metrics)
    final_metrics['node_attribution'] = node_info

    logger.info(f"All agents completed. Total time: {final_metrics['total_execution_time']}s")

    return {
        'result': {
            'final_output': final_markdown,
            'agent_outputs': json_outputs
        },
        'metrics': final_metrics,
        'raw_json': json_outputs
    }


def _extract_markdown_from_editor(editor_output):
    """Extract markdown content from editor's output."""
    if isinstance(editor_output, dict):
        # Try to get the actual text content from the data field
        if "data" in editor_output:
            data = editor_output["data"]
            if isinstance(data, str):
                return data
            elif isinstance(data, dict):
                # Look for common text fields
                for key in ["content", "text", "answer", "output", "markdown", "result", "polished_output"]:
                    if key in data and isinstance(data[key], str):
                        return data[key]
                # If nothing found, convert to readable text
                return json.dumps(data, indent=2)
        # Try other common fields
        for key in ["content", "text", "answer", "output", "markdown", "result"]:
            if key in editor_output and isinstance(editor_output[key], str):
                return editor_output[key]

    # Fallback: convert to string
    return str(editor_output)
