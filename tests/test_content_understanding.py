import base64
import unittest
from unittest.mock import MagicMock, patch

from backend.services.content_understanding_service import ContentUnderstandingService
from backend.schemas import ExtractedPersonOut


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
        request = http_client.__enter__.return_value.post.call_args
        self.assertEqual(
            request.kwargs["json"],
            {"inputs": [{"data": base64.b64encode(b"image-bytes").decode("ascii")}]},
        )
        self.assertEqual(request.kwargs["headers"]["Content-Type"], "application/json")

    def test_rest_request_wraps_document_url_in_inputs(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"contents": []}
        http_client = MagicMock()
        http_client.__enter__.return_value.post.return_value = response

        with patch(
            "backend.services.content_understanding_service.httpx.Client",
            return_value=http_client,
        ):
            self.service._analyze_with_content_understanding_rest(
                b"", "invoice.png", "Invoice", "https://example.test/invoice.png"
            )

        request = http_client.__enter__.return_value.post.call_args
        self.assertEqual(
            request.kwargs["json"],
            {"inputs": [{"url": "https://example.test/invoice.png"}]},
        )

    def test_rest_poll_accepts_late_case_insensitive_success(self):
        response = MagicMock()
        response.status_code = 202
        response.headers = {"Operation-Location": "https://example.test/operation/1"}

        pending = MagicMock()
        pending.status_code = 200
        pending.json.return_value = {"status": "Running"}
        succeeded = MagicMock()
        succeeded.status_code = 200
        succeeded.json.return_value = {
            "status": "Succeeded",
            "result": {"contents": [{"markdown": "Invoice text"}]},
        }
        http_client = MagicMock()
        http_client.__enter__.return_value.post.return_value = response
        http_client.__enter__.return_value.get.side_effect = [pending] * 26 + [succeeded]

        with (
            patch(
                "backend.services.content_understanding_service.httpx.Client",
                return_value=http_client,
            ),
            patch("backend.services.content_understanding_service.time.sleep"),
        ):
            result = self.service._analyze_with_content_understanding_rest(
                b"image-bytes", "invoice.png", "Invoice"
            )

        self.assertEqual(result["extracted_text"], "Invoice text")
        self.assertEqual(http_client.__enter__.return_value.get.call_count, 27)

    def test_invoice_analyzer_fields_map_customer_and_keep_invoice_values(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "contents": [{
                "markdown": "Invoice # INV-2048\nCustomer: Example Customer",
                "fields": {
                    "CustomerName": {
                        "type": "string",
                        "valueString": "Example Customer",
                        "confidence": 0.97,
                    },
                    "CustomerTaxId": {
                        "type": "string",
                        "valueString": "TAX-98765",
                    },
                    "CustomerAddress": {
                        "type": "string",
                        "valueString": "10 Example Street",
                    },
                    "InvoiceId": {
                        "type": "string",
                        "valueString": "INV-2048",
                    },
                    "InvoiceDate": {
                        "type": "date",
                        "valueDate": "2026-10-24",
                    },
                    "AmountDue": {
                        "type": "object",
                        "valueObject": {
                            "Amount": {
                                "type": "number",
                                "valueNumber": 125.5,
                            },
                            "CurrencyCode": {
                                "type": "string",
                                "valueString": "USD",
                            },
                        },
                    },
                    "LineItems": {
                        "type": "array",
                        "valueArray": [{
                            "type": "object",
                            "valueObject": {
                                "Description": {
                                    "type": "string",
                                    "valueString": "Service",
                                },
                                "Quantity": {
                                    "type": "number",
                                    "valueNumber": 2,
                                },
                            },
                        }],
                    },
                },
            }]
        }
        http_client = MagicMock()
        http_client.__enter__.return_value.post.return_value = response

        with patch(
            "backend.services.content_understanding_service.httpx.Client",
            return_value=http_client,
        ):
            result = self.service._analyze_with_content_understanding_rest(
                b"image-bytes", "invoice.png", "Invoice"
            )

        fields = result["extracted_fields"]
        person = fields["extracted_person"]
        self.assertEqual(person["full_name"], "Example Customer")
        self.assertEqual(person["national_id"], "TAX-98765")
        self.assertEqual(person["address"], "10 Example Street")
        self.assertIsNone(person["date_of_birth"])
        self.assertEqual(fields["InvoiceId"], "INV-2048")
        self.assertEqual(fields["InvoiceDate"], "2026-10-24")
        self.assertEqual(fields["AmountDue"], {"Amount": 125.5, "CurrencyCode": "USD"})
        self.assertEqual(
            fields["LineItems"],
            [{"Description": "Service", "Quantity": 2}],
        )

    def test_unavailable_configured_azure_service_does_not_return_demo_data(self):
        with patch.object(
            self.service, "_analyze_with_content_understanding_rest", return_value=None
        ):
            result = self.service.analyze_document(b"image-bytes", "scan.png", "ID Document")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["extracted_fields"], {})
        self.assertEqual(result["extracted_person"], {})
        self.assertEqual(result["extracted_text"], "")

    def test_azure_http_error_is_retained_for_diagnostics(self):
        response = MagicMock()
        response.status_code = 400
        response.text = '{"error":{"code":"InvalidSource","message":"Invalid JSON."}}'
        http_client = MagicMock()
        http_client.__enter__.return_value.post.return_value = response

        with patch(
            "backend.services.content_understanding_service.httpx.Client",
            return_value=http_client,
        ):
            result = self.service.analyze_document(b"image-bytes", "scan.png", "Invoice")

        self.assertEqual(result["status"], "failed")
        self.assertIn("HTTP 400", result["analysis_raw"]["error"])
        self.assertIn("InvalidSource", result["analysis_raw"]["error"])

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

    def test_person_mapping_converts_nested_fields_to_database_safe_text(self):
        extracted_person = self.service._extract_person_from_data(
            {
                "CustomerName": "Example Customer",
                "CustomerTaxId": {},
                "CustomerAddress": {
                    "StreetAddress": "10 Example Street",
                    "City": "Example City",
                },
            },
            "",
            "Invoice",
            "invoice.png",
        )

        self.assertEqual(extracted_person["full_name"], "Example Customer")
        self.assertIsNone(extracted_person["national_id"])
        self.assertEqual(
            extracted_person["address"],
            "10 Example Street, Example City",
        )
        for value in extracted_person.values():
            self.assertFalse(isinstance(value, (dict, list)))

    def test_extracted_person_response_accepts_legacy_nested_values(self):
        extracted_person = ExtractedPersonOut.model_validate({
            "full_name": "Example Customer",
            "national_id": {},
            "address": {"StreetAddress": "10 Example Street", "City": "Example City"},
        })

        self.assertEqual(extracted_person.full_name, "Example Customer")
        self.assertIsNone(extracted_person.national_id)
        self.assertEqual(extracted_person.address, "10 Example Street, Example City")


if __name__ == "__main__":
    unittest.main()
