"""Tests for JSON pipeline extraction and standardization."""
import pytest
import json
from json_pipeline import (
    extract_json_from_text,
    fix_malformed_json,
    standardize_to_json,
    validate_json_output,
    merge_json_outputs
)


class TestFixMalformedJSON:
    """Test JSON fixing capabilities."""

    def test_fix_trailing_commas(self):
        """Test removal of trailing commas."""
        malformed = '{"key": "value",}'
        fixed = fix_malformed_json(malformed)
        assert json.loads(fixed) == {"key": "value"}

    def test_fix_single_quotes(self):
        """Test conversion of single quotes to double quotes."""
        malformed = "{'key': 'value'}"
        fixed = fix_malformed_json(malformed)
        assert json.loads(fixed) == {"key": "value"}

    def test_fix_unquoted_keys(self):
        """Test quoting of unquoted keys."""
        malformed = '{key: "value"}'
        fixed = fix_malformed_json(malformed)
        result = json.loads(fixed)
        assert "key" in result


class TestExtractJSONFromText:
    """Test JSON extraction from various text formats."""

    def test_extract_from_json_code_block(self):
        """Test extraction from ```json code block."""
        text = '```json\n{"key": "value"}\n```'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_from_plain_code_block(self):
        """Test extraction from ``` code block."""
        text = '```\n{"key": "value"}\n```'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_from_plain_text(self):
        """Test extraction from plain JSON."""
        text = '{"key": "value"}'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_from_mixed_text(self):
        """Test extraction from text with JSON embedded."""
        text = 'Here is the result: {"key": "value"} and more text'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_nested_json(self):
        """Test extraction of nested JSON objects."""
        text = '{"outer": {"inner": "value"}}'
        result = extract_json_from_text(text)
        assert result == {"outer": {"inner": "value"}}

    def test_extract_json_array(self):
        """Test extraction of JSON arrays."""
        text = '[{"key": "value1"}, {"key": "value2"}]'
        result = extract_json_from_text(text)
        assert result == [{"key": "value1"}, {"key": "value2"}]

    def test_extract_malformed_json(self):
        """Test extraction and fixing of malformed JSON."""
        text = "{'key': 'value',}"
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_returns_none_for_invalid(self):
        """Test that invalid text returns None."""
        text = "This is just plain text with no JSON"
        result = extract_json_from_text(text)
        assert result is None


class TestStandardizeToJSON:
    """Test standardization of agent outputs."""

    def test_standardize_valid_json(self):
        """Test standardization of valid JSON output."""
        raw_output = '{"analysis": "test"}'
        result = standardize_to_json("TestAgent", raw_output)

        assert result["agent"] == "TestAgent"
        assert result["status"] == "success"
        assert result["format"] == "json"
        assert result["data"] == {"analysis": "test"}

    def test_standardize_plain_text(self):
        """Test standardization of plain text output."""
        raw_output = "This is plain text output"
        result = standardize_to_json("TestAgent", raw_output)

        assert result["agent"] == "TestAgent"
        assert result["status"] == "success"
        assert result["format"] == "text"
        assert result["data"]["content"] == "This is plain text output"

    def test_standardize_json_in_markdown(self):
        """Test standardization of JSON in markdown blocks."""
        raw_output = '```json\n{"key": "value"}\n```'
        result = standardize_to_json("TestAgent", raw_output)

        assert result["format"] == "json"
        assert result["data"] == {"key": "value"}


class TestValidateJSONOutput:
    """Test JSON output validation."""

    def test_validate_valid_output(self):
        """Test validation of valid output."""
        valid_output = {
            "agent": "TestAgent",
            "status": "success",
            "format": "json",
            "data": {"key": "value"}
        }
        assert validate_json_output(valid_output) is True

    def test_validate_missing_field(self):
        """Test validation fails with missing field."""
        invalid_output = {
            "agent": "TestAgent",
            "status": "success",
            "format": "json"
            # Missing 'data' field
        }
        assert validate_json_output(invalid_output) is False

    def test_validate_invalid_data_type(self):
        """Test validation fails with invalid data type."""
        invalid_output = {
            "agent": "TestAgent",
            "status": "success",
            "format": "json",
            "data": "should be dict not string"
        }
        assert validate_json_output(invalid_output) is False

    def test_validate_not_dict(self):
        """Test validation fails for non-dict input."""
        assert validate_json_output("not a dict") is False
        assert validate_json_output([]) is False
        assert validate_json_output(None) is False


class TestMergeJSONOutputs:
    """Test merging of multiple agent outputs."""

    def test_merge_multiple_outputs(self):
        """Test merging multiple agent outputs."""
        outputs = [
            {
                "agent": "Agent1",
                "status": "success",
                "format": "json",
                "data": {"key1": "value1"}
            },
            {
                "agent": "Agent2",
                "status": "success",
                "format": "json",
                "data": {"key2": "value2"}
            }
        ]

        result = merge_json_outputs(outputs)

        assert result["pipeline"] == "SynapticLlamas"
        assert result["agent_count"] == 2
        assert result["agents"] == ["Agent1", "Agent2"]
        assert result["outputs"] == outputs

    def test_merge_single_output(self):
        """Test merging single output."""
        outputs = [
            {
                "agent": "Agent1",
                "status": "success",
                "format": "json",
                "data": {"key": "value"}
            }
        ]

        result = merge_json_outputs(outputs)

        assert result["agent_count"] == 1
        assert result["agents"] == ["Agent1"]

    def test_merge_empty_list(self):
        """Test merging empty list."""
        result = merge_json_outputs([])

        assert result["agent_count"] == 0
        assert result["agents"] == []
        assert result["outputs"] == []
