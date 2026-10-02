"""Ensure visual cleanup preserves Unicode detection and AI prompt markers."""

import ast
import json
from pathlib import Path
import re
import unittest


class FraudPatternUnicodeTests(unittest.TestCase):
    def test_escaped_pattern_preserves_all_original_symbols_and_weight(self):
        path = Path(__file__).resolve().parents[1] / "src/backend/core/fraud_patterns.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        group = config["patterns"]["suspicious_emojis"]
        symbols = "".join(chr(code) for code in (
            0x1F3B0, 0x1F3B2, 0x1F4B0, 0x1F4B8, 0x1F4B5,
            0x1F4B4, 0x1F4B6, 0x1F4B7, 0x1F911,
        ))
        self.assertEqual(group["weight"], 0.1)
        self.assertEqual(group["patterns"], [f"[{symbols}]"])
        pattern = re.compile(group["patterns"][0], re.IGNORECASE)
        for symbol in symbols:
            with self.subTest(codepoint=ord(symbol)):
                self.assertIsNotNone(pattern.fullmatch(symbol))
        self.assertIsNone(pattern.search("normal conversation"))


class PromptPreservationTests(unittest.TestCase):
    def test_educational_prompt_retains_safe_fraud_and_severity_markers(self):
        path = Path(__file__).resolve().parents[1] / "src/backend/services/gemini_service.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prompt = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "EDUCATIONAL_CONTENT_PROMPT"
                    for target in node.targets)
        )
        self.assertIn(f"**{chr(0x1F7E2)} SAFE MESSAGES", prompt)
        self.assertIn(f"**{chr(0x1F534)} FRAUD/SCAM CATEGORIES", prompt)
        self.assertIn(f'{chr(0x2705)} "ขอเงินหน่อย"', prompt)
        self.assertIn(f'{chr(0x274C)} "กู้เงินด่วน!', prompt)
        self.assertIn("Severity: " + (chr(0x26A0) + chr(0xFE0F)) * 3 + " VERY HIGH", prompt)


if __name__ == "__main__":
    unittest.main()
