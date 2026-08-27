import unittest
from pydantic import ValidationError

from fapi.ai_prep.exceptions import ParseError
from fapi.ai_prep.services.report_validator import validate_report_json

# A valid template of report data matching Contract 3
VALID_REPORT_JSON = """{
  "scores_breakdown_json": {
    "ai_engineering": {
      "score": 85,
      "sub_scores": {
        "llm_knowledge": 80,
        "rag_understanding": 90
      }
    },
    "core_engineering": {
      "score": 75,
      "sub_scores": {
        "system_design": 70,
        "algorithms": 80
      }
    },
    "non_technical": {
      "score": 80,
      "sub_scores": {
        "communication_clarity": 85
      }
    },
    "business_acumen": {
      "score": 70,
      "sub_scores": {
        "problem_framing": 70
      }
    }
  },
  "technical_analysis_json": {
    "summary": "Great AI capabilities.",
    "strengths": ["RAG architecture understanding"],
    "areas_for_improvement": ["Fine-tuning details"]
  },
  "non_technical_analysis_json": {
    "communication_summary": "Paced well.",
    "structure_quality": "Highly structured",
    "confidence_notes": "Very confident"
  },
  "coaching_suggestions_json": [
    {
      "priority": 1,
      "dimension": "AI Engineering",
      "area": "Fine-Tuning",
      "suggestion": "Read about loss curves.",
      "evidence": "Gave thin explanation of fine-tuning."
    }
  ],
  "signal_timeline_json": [
    {
      "question_index": 1,
      "energy": 80,
      "clarity": "high"
    }
  ],
  "transcript_evidence_json": [
    {
      "quote": "I designed it.",
      "timestamp_s": 12.5,
      "dimension": "AI Engineering",
      "observation": "Good quote"
    }
  ],
  "gaps_to_validate_json": [
    {
      "topic": "quantization",
      "reason": "not discussed"
    }
  ],
  "improvements_json": [
    {
      "priority": 1,
      "topic": "quantization basics",
      "effort": "low",
      "rationale": "essential"
    }
  ]
}"""


class TestReportValidator(unittest.TestCase):
    def test_valid_json_passes(self):
        """A valid report JSON conforming to Contract 3 should validate without error."""
        result = validate_report_json(VALID_REPORT_JSON)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["scores_breakdown_json"]["ai_engineering"]["score"], 85)
        self.assertEqual(result["improvements_json"][0]["effort"], "low")

    def test_invalid_json_syntax_raises_parse_error(self):
        """Malformatted JSON syntax should raise ParseError."""
        broken_json = '{"scores_breakdown_json": {'  # missing braces
        with self.assertRaises(ParseError) as ctx:
            validate_report_json(broken_json)
        self.assertIn("not valid JSON", ctx.exception.message)

    def test_missing_required_fields_raises_parse_error(self):
        """JSON missing crucial top-level keys should raise ParseError."""
        # Missing non_technical_analysis_json
        bad_json = """{
          "scores_breakdown_json": {},
          "technical_analysis_json": {},
          "coaching_suggestions_json": [],
          "signal_timeline_json": [],
          "transcript_evidence_json": [],
          "gaps_to_validate_json": [],
          "improvements_json": []
        }"""
        with self.assertRaises(ParseError) as ctx:
            validate_report_json(bad_json)
        self.assertIn("non_technical_analysis_json", ctx.exception.message)

    def test_out_of_bounds_scores_raises_parse_error(self):
        """A score outside the range 0-100 should raise ParseError."""
        import json
        data = json.loads(VALID_REPORT_JSON)
        # Set AI score to 150 (out of bounds)
        data["scores_breakdown_json"]["ai_engineering"]["score"] = 150
        with self.assertRaises(ParseError) as ctx:
            validate_report_json(json.dumps(data))
        self.assertIn("ai_engineering -> score", ctx.exception.message)

    def test_invalid_types_raises_parse_error(self):
        """Passing incorrect data types (e.g. an integer for a list) should raise ParseError."""
        import json
        data = json.loads(VALID_REPORT_JSON)
        # Strengths is supposed to be List[str]
        data["technical_analysis_json"]["strengths"] = 12345
        with self.assertRaises(ParseError) as ctx:
            validate_report_json(json.dumps(data))
        self.assertIn("technical_analysis_json -> strengths", ctx.exception.message)

    def test_effort_literal_values(self):
        """Effort in improvements must be 'low', 'medium', or 'high'."""
        import json
        data = json.loads(VALID_REPORT_JSON)
        data["improvements_json"][0]["effort"] = "extra-high"
        with self.assertRaises(ParseError) as ctx:
            validate_report_json(json.dumps(data))
        self.assertIn("improvements_json -> 0 -> effort", ctx.exception.message)

    def test_type_coercion_flexible_fields(self):
        """Flexible type fields should parse strings, ints, floats, or null properly."""
        import json
        data = json.loads(VALID_REPORT_JSON)
        
        # Test timeline energy/clarity with strings & ints mixed
        data["signal_timeline_json"][0]["energy"] = "strong"
        data["signal_timeline_json"][0]["clarity"] = 80
        
        # Test timestamp_s with null (None) or float or int
        data["transcript_evidence_json"][0]["timestamp_s"] = None
        
        result = validate_report_json(json.dumps(data))
        self.assertEqual(result["signal_timeline_json"][0]["energy"], "strong")
        self.assertEqual(result["signal_timeline_json"][0]["clarity"], 80)
        self.assertIsNone(result["transcript_evidence_json"][0]["timestamp_s"])
        
        # Test timestamp_s as integer
        data["transcript_evidence_json"][0]["timestamp_s"] = 42
        result2 = validate_report_json(json.dumps(data))
        self.assertEqual(result2["transcript_evidence_json"][0]["timestamp_s"], 42)


if __name__ == "__main__":
    unittest.main()
