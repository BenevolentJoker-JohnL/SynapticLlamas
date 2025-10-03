def aggregate_outputs(outputs):
    """
    Merge agent outputs into a final result.
    Can be enhanced with LLM-based synthesis later.
    """
    separator = "\n" + "=" * 70 + "\n"
    final = separator.join(outputs)
    return f"\n{'=' * 70}\n AGGREGATED RESULTS\n{'=' * 70}\n\n{final}\n\n{'=' * 70}"


def aggregate_metrics(metrics_list):
    """Aggregate performance metrics from all agents."""
    total_time = sum(m['execution_time'] for m in metrics_list)

    metrics_summary = {
        'total_execution_time': round(total_time, 2),
        'agent_count': len(metrics_list),
        'agent_metrics': metrics_list
    }

    return metrics_summary
