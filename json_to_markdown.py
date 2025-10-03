"""
Convert structured JSON output to beautiful markdown for display.
"""


def json_to_markdown(json_data: dict) -> str:
    """
    Convert editor JSON output to formatted markdown.

    Args:
        json_data: Structured JSON from editor with fields:
            - summary
            - key_points
            - detailed_explanation
            - examples
            - practical_applications

    Returns:
        Formatted markdown string
    """
    markdown = []

    # Extract data, handling both direct fields and nested data structures
    if isinstance(json_data, dict):
        # Handle wrapped format
        if "data" in json_data:
            data = json_data["data"]
        else:
            data = json_data

        # Summary section
        if "summary" in data:
            markdown.append(f"## Summary\n")
            markdown.append(f"{data['summary']}\n")

        # Key Points
        if "key_points" in data and data["key_points"]:
            markdown.append(f"## Key Points\n")
            for point in data["key_points"]:
                markdown.append(f"- **{point}**")
            markdown.append("")

        # Detailed Explanation
        if "detailed_explanation" in data:
            markdown.append(f"## Detailed Explanation\n")
            markdown.append(f"{data['detailed_explanation']}\n")

        # Examples
        if "examples" in data and data["examples"]:
            markdown.append(f"## Examples\n")
            for i, example in enumerate(data["examples"], 1):
                markdown.append(f"{i}. {example}")
            markdown.append("")

        # Practical Applications
        if "practical_applications" in data and data["practical_applications"]:
            markdown.append(f"## Practical Applications\n")
            for app in data["practical_applications"]:
                markdown.append(f"- {app}")
            markdown.append("")

    return "\n".join(markdown)


def agent_outputs_to_markdown(researcher_output: dict, critic_output: dict, editor_output: dict) -> str:
    """
    Convert all agent outputs to a comprehensive markdown report.

    Args:
        researcher_output: Research findings JSON
        critic_output: Critique JSON
        editor_output: Synthesized editor JSON

    Returns:
        Full markdown report
    """
    markdown = []

    # Main content from editor
    markdown.append(json_to_markdown(editor_output))

    # Optional: Add research details section
    # markdown.append("\n---\n")
    # markdown.append("## Research Details\n")
    # if "data" in researcher_output and "key_facts" in researcher_output["data"]:
    #     for fact in researcher_output["data"]["key_facts"]:
    #         markdown.append(f"- {fact}")

    return "\n".join(markdown)
