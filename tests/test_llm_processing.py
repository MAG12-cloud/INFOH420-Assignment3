import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.llm_processing import (
    MetadataGenerationError,
    MetadataValidationError,
    generate_metadata,
    validate_metadata,
)


VALID_METADATA = {
    "title": "A Paper",
    "summary": "A useful summary.",
    "keywords": ["Airflow", "SQLite"],
    "category": "Data Engineering",
}


class FakeCompletions:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = next(self.responses)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content)
                )
            ]
        )


def fake_client(*responses):
    completions = FakeCompletions(responses)
    return SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )


class ValidateMetadataTests(unittest.TestCase):
    def test_normalizes_values_and_removes_duplicate_keywords(self):
        result = validate_metadata(
            {
                "title": "  A Paper  ",
                "summary": " Summary ",
                "keywords": ["Airflow", " airflow ", "SQLite"],
                "category": " Data Engineering ",
            }
        )

        self.assertEqual(result["title"], "A Paper")
        self.assertEqual(result["keywords"], ["Airflow", "SQLite"])

    def test_rejects_missing_field(self):
        invalid = dict(VALID_METADATA)
        del invalid["category"]

        with self.assertRaisesRegex(MetadataValidationError, "category"):
            validate_metadata(invalid)

    def test_rejects_wrong_keyword_type(self):
        invalid = dict(VALID_METADATA, keywords="Airflow")

        with self.assertRaisesRegex(MetadataValidationError, "keywords"):
            validate_metadata(invalid)


class GenerateMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.markdown_path = Path(self.temp_directory.name) / "paper.md"
        self.markdown_path.write_text(
            "# A Paper\n\nThis paper studies reliable data pipelines.",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    @patch.dict("os.environ", {"LOCAL_LLM_JSON_MODE": "true"})
    def test_generates_metadata_using_json_mode(self):
        client = fake_client(json.dumps(VALID_METADATA))

        result = generate_metadata(
            str(self.markdown_path),
            client=client,
            model="test-model",
        )

        self.assertEqual(result, VALID_METADATA)
        call = client.chat.completions.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertEqual(call["response_format"], {"type": "json_object"})
        self.assertEqual(call["temperature"], 0)

    def test_retries_once_after_invalid_json(self):
        client = fake_client("not json", json.dumps(VALID_METADATA))

        result = generate_metadata(
            str(self.markdown_path),
            client=client,
            model="test-model",
        )

        self.assertEqual(result, VALID_METADATA)
        self.assertEqual(len(client.chat.completions.calls), 2)

    def test_fails_after_two_invalid_responses(self):
        client = fake_client("not json", "still not json")

        with self.assertRaises(MetadataGenerationError):
            generate_metadata(
                str(self.markdown_path),
                client=client,
                model="test-model",
            )

        self.assertEqual(len(client.chat.completions.calls), 2)

    def test_requires_a_configured_model(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "LOCAL_LLM_MODEL"):
                generate_metadata(
                    str(self.markdown_path),
                    client=fake_client(json.dumps(VALID_METADATA)),
                )


if __name__ == "__main__":
    unittest.main()
