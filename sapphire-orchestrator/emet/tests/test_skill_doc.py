import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / ".claude" / "skills" / "emet-runner" / "SKILL.md"

class TestSkillDoc(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SKILL.exists(), f"missing {SKILL}")
        self.text = SKILL.read_text(encoding="utf-8")

    def test_frontmatter_name_and_description(self):
        self.assertTrue(self.text.startswith("---"))
        head = self.text.split("---", 2)[1]
        self.assertIn("name: emet-runner", head)
        self.assertRegex(head, r"description:\s*\S+")

    def test_references_protocol_and_envelope(self):
        self.assertIn("emet_protocol.md", self.text)
        for key in ["candidate", "emet_workflow", "verdict", "evidence", "chat_url"]:
            self.assertIn(key, self.text)            # documents the envelope it returns

    def test_safety_rules_present(self):
        low = self.text.lower()
        self.assertIn("public identifier", low)       # public-IDs only
        self.assertIn("login", low)                   # login -> stop/escalate
        self.assertIn("login_required", self.text)    # the exact escalation signal the handler detects
        self.assertIn("tab", low)                     # tab discipline

    def test_mentions_workflows(self):
        for wf in ["Drug Safety", "Target Validation", "Pathway Analysis"]:
            self.assertIn(wf, self.text)

if __name__ == "__main__":
    unittest.main()
