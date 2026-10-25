"""
Comprehensive Automated Tests for Document Scan Management
Tests Projects CRUD, Person Batch Creation with Scans, Azure Storage,
Azure Content Understanding, and AI Agent.
"""

import io
import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db

init_db()
client = TestClient(app)


def create_dummy_image(text="SAMPLE"):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (300, 300), color=(240, 240, 240))
    d = ImageDraw.Draw(img)
    d.text((20, 20), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.getvalue()


class DocumentScanManagementTests(unittest.TestCase):

    def test_01_system_status(self):
        """Verify system status reports cloud connectivity"""
        response = client.get("/api/system/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("database", data)
        self.assertIn("storage", data)
        self.assertIn("content_understanding", data)
        self.assertIn("ai_agent", data)

    def test_02_projects_crud(self):
        """Test Create, Read, Update, Delete for Projects with custom Person Types"""
        # 1. Create Project
        create_payload = {
            "title": "Hospital Staff & Medical Credentialing",
            "description": "Verification of doctors, nurses, medical licenses, and police certificates.",
            "person_types": ["Doctor", "Nurse", "Pharmacist", "Technician"]
        }
        res = client.post("/api/projects", json=create_payload)
        self.assertEqual(res.status_code, 201)
        proj_data = res.json()
        project_id = proj_data["id"]
        self.assertEqual(proj_data["title"], create_payload["title"])
        self.assertEqual(proj_data["person_types"], ["Doctor", "Nurse", "Pharmacist", "Technician"])

        # 2. List Projects
        list_res = client.get("/api/projects")
        self.assertEqual(list_res.status_code, 200)
        all_projects = list_res.json()
        self.assertTrue(any(p["id"] == project_id for p in all_projects))

        # 3. Get Project Detail
        detail_res = client.get(f"/api/projects/{project_id}")
        self.assertEqual(detail_res.status_code, 200)
        self.assertEqual(detail_res.json()["title"], create_payload["title"])

        # 4. Update Project
        update_res = client.put(f"/api/projects/{project_id}", json={
            "title": "Hospital Medical Staff Onboarding 2026",
            "person_types": ["Doctor", "Nurse", "Surgeon"]
        })
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.json()["title"], "Hospital Medical Staff Onboarding 2026")
        self.assertEqual(update_res.json()["person_types"], ["Doctor", "Nurse", "Surgeon"])

        # Cleanup at end
        del_res = client.delete(f"/api/projects/{project_id}")
        self.assertEqual(del_res.status_code, 204)

    def test_03_person_creation_with_batch_scans(self):
        """Test creating a person via basic info form + batch pictures of scanned documents"""
        # Create project first
        proj_res = client.post("/api/projects", json={
            "title": "Bank Account Opening Verification",
            "person_types": ["Account Holder", "Guarantor", "Signatory"]
        })
        self.assertEqual(proj_res.status_code, 201)
        project_id = proj_res.json()["id"]

        # Prepare dummy scanned images: Fee voucher and ID document
        voucher_bytes = create_dummy_image("BANK FEE CHALLAN PAID")
        id_bytes = create_dummy_image("NATIONAL IDENTITY CARD")

        # Multipart form data
        data = {
            "full_name": "Alexander Hayes",
            "person_type": "Account Holder",
            "national_id": "42101-7890123-5",
            "email": "alex.hayes@example.com",
            "phone": "+1-555-8910",
            "date_of_birth": "1994-03-12",
            "address": "456 Market St, Financial District",
            "notes": "Verified in branch.",
            "categories_json": '["Fee Voucher", "ID Document"]'
        }

        files = [
            ("files", ("fee_voucher.jpg", voucher_bytes, "image/jpeg")),
            ("files", ("national_id_front.jpg", id_bytes, "image/jpeg")),
        ]

        res = client.post(f"/api/projects/{project_id}/persons", data=data, files=files)
        self.assertEqual(res.status_code, 201)
        person = res.json()
        person_id = person["id"]
        self.assertEqual(person["full_name"], "Alexander Hayes")
        self.assertEqual(person["person_type"], "Account Holder")
        self.assertEqual(person["documents_count"], 2)
        self.assertEqual(len(person["documents"]), 2)

        # Check that storage references and Content Understanding analyses were populated
        doc1 = person["documents"][0]
        self.assertNotEqual(doc1["storage_reference"], "")
        self.assertNotEqual(doc1["blob_name"], "")
        self.assertIsNotNone(doc1["analysis"])
        self.assertEqual(doc1["analysis"]["status"], "completed")

        # Test file retrieval from storage
        file_res = client.get(f"/api/documents/{doc1['id']}/file")
        self.assertEqual(file_res.status_code, 200)
        self.assertGreater(len(file_res.content), 0)

        # Test additional batch upload for this person
        cert_bytes = create_dummy_image("CERTIFICATE OF REGISTRATION")
        add_files = [
            ("files", ("tax_certificate.jpg", cert_bytes, "image/jpeg"))
        ]
        add_data = {
            "categories_json": '["Certificate"]'
        }
        batch_res = client.post(f"/api/documents/batch/{person_id}", data=add_data, files=add_files)
        self.assertEqual(batch_res.status_code, 201)
        self.assertEqual(len(batch_res.json()), 1)

        # Verify updated dossier
        dossier_res = client.get(f"/api/persons/{person_id}")
        self.assertEqual(dossier_res.status_code, 200)
        self.assertEqual(dossier_res.json()["documents_count"], 3)

        # Test AI Agent Audit on this person
        audit_res = client.get(f"/api/agent/audit/person/{person_id}")
        self.assertEqual(audit_res.status_code, 200)
        audit_data = audit_res.json()
        self.assertIn("compliance_status", audit_data)
        self.assertIn("findings", audit_data)
        self.assertGreater(len(audit_data["findings"]), 0)

        # Test AI Agent Chat
        chat_res = client.post("/api/agent/chat", json={
            "query": "Did Alexander Hayes pay his fee voucher?",
            "person_id": person_id,
            "project_id": project_id
        })
        self.assertEqual(chat_res.status_code, 200)
        chat_data = chat_res.json()
        self.assertIn("answer", chat_data)

        # Clean up
        client.delete(f"/api/projects/{project_id}")


if __name__ == "__main__":
    unittest.main()
