import unittest
from unittest.mock import MagicMock, patch

from backend.services.content_understanding_service import ContentUnderstandingService


class ContentUnderstandingParsingTests(unittest.TestCase):

    def setUp(self):
        self.service = object.__new__(ContentUnderstandingService)
        self.service.endpoint = "https://example.services.ai.azure.com"
        self.service.analyzer_id = "document_analyzer"
        self.service.api_version = "2025-11-01"
        self.service.key = None
        self.service.use_rest_api = True
        self.service.client = None

    def test_rest_response_unwraps_typed_fields_and_extracts_markdown(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "result": {
                "contents": [{
                    "markdown": "Name: Ayesha Khan\nID Number: 12345",
                    "fields": {
                        "Identity": {
                            "type": "object",
                            "valueObject": {
                                "Full Name": {
                                    "type": "string",
                                    "valueString": "Ayesha Khan",
                                    "confidence": 0.98,
                                },
                                "National ID": {
                                    "type": "string",
                                    "valueString": "12345",
                                }
                            },
                        },
                        "Items": {
                            "type": "array",
                            "valueArray": [
                                {"type": "string", "valueString": "First"},
                                {"type": "string", "valueString": "Second"},
                            ],
                        },
                    },
                }]
            }
        }
        http_client = MagicMock()
        http_client.__enter__.return_value.post.return_value = response

        with patch(
            "backend.services.content_understanding_service.httpx.Client",
            return_value=http_client,
        ):
            result = self.service._analyze_with_content_understanding_rest(
                b"image-bytes", "scan.png", "ID Document"
            )

        self.assertEqual(result["extracted_text"], "Name: Ayesha Khan\nID Number: 12345")
        fields = result["extracted_fields"]
        self.assertEqual(fields["Identity"]["Full Name"], "Ayesha Khan")
        self.assertEqual(fields["Identity"]["National ID"], "12345")
        self.assertEqual(fields["Items"], ["First", "Second"])
        self.assertEqual(fields["extracted_person"]["full_name"], "Ayesha Khan")
        self.assertEqual(fields["extracted_person"]["national_id"], "12345")

    def test_unavailable_configured_azure_service_does_not_return_demo_data(self):
        with patch.object(
            self.service, "_analyze_with_content_understanding_rest", return_value=None
        ):
            result = self.service.analyze_document(b"image-bytes", "scan.png", "ID Document")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["extracted_fields"], {})
        self.assertEqual(result["extracted_person"], {})
        self.assertEqual(result["extracted_text"], "")

    def test_person_extraction_leaves_unobserved_values_empty(self):
        extracted_person = self.service._extract_person_from_data(
            {"Full Name": "Ayesha Khan"},
            "",
            "Other",
            "scan.png",
        )

        self.assertEqual(extracted_person["full_name"], "Ayesha Khan")
        self.assertIsNone(extracted_person["national_id"])
        self.assertIsNone(extracted_person["date_of_birth"])
        self.assertIsNone(extracted_person["email"])
        self.assertIsNone(extracted_person["phone"])
        self.assertIsNone(extracted_person["address"])


if __name__ == "__main__":
    unittest.main()
