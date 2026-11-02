import unittest

from agent.nodes import _build_system_prompt

KB = "Dhaka Active-Active Cluster: three (3) data centers.\n\nISO 27001:2022 certified."


class PromptTests(unittest.TestCase):
    def test_chat_prompt_uses_search_tool_and_reasoning_tags(self):
        p = _build_system_prompt("", "English")
        self.assertIn("ALWAYS call the `search_knowledge_base` tool first", p)
        self.assertIn("<thought>", p)
        self.assertNotIn("KNOWLEDGE BASE (authoritative", p)

    def test_no_unfilled_placeholders(self):
        for kb in (None, KB):
            p = _build_system_prompt("sum", "English", kb_text=kb)
            for name in ("kb_enquiry_rule", "kb_data_rule", "reasoning_rule", "{today}", "{language}"):
                self.assertNotIn("{" + name.strip("{}") + "}", p)

    def test_inline_prompt_has_kb_and_no_tool_or_thought_rules(self):
        p = _build_system_prompt("", "English", kb_text=KB)
        self.assertIn("--- KNOWLEDGE BASE", p)
        self.assertIn("three (3) data centers", p)
        self.assertIn("ISO 27001:2022", p)
        self.assertNotIn("search_knowledge_base", p)
        self.assertNotIn("<thought>", p)
        self.assertNotIn("<context>", p)
        self.assertIn("do NOT say you are searching", p)

    def test_inline_kb_comes_after_summary(self):
        p = _build_system_prompt("PREV-SUMMARY-XYZ", "English", kb_text=KB)
        self.assertLess(p.index("PREV-SUMMARY-XYZ"), p.index("--- KNOWLEDGE BASE"))

    def test_other_rules_untouched_in_both_modes(self):
        for kb in (None, KB):
            p = _build_system_prompt("", "Bengali", kb_text=kb)
            self.assertIn("ALWAYS reply in Bengali", p)
            self.assertIn("SECURITY (non-negotiable)", p)
            self.assertIn("save_collected_information", p)
            self.assertIn("COMPANY IDENTITY & USPS", p)


if __name__ == "__main__":
    unittest.main()
