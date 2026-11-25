import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from agents import review


def packet():
    return {"gate_passed": True, "cases": [{
        "id": "case1", "question": "What measurement would resolve this?",
        "evidence": [{"id": "e1", "source": "https://example.org/survey/1", "detail": "A measurement."}],
    }]}


def reply(body):
    return {"response_id": "test-response", "actual_model": "test-model", "usage": {},
            "review": {"assessment": "The measurement is inconclusive.", "evidence_ids": ["e1"],
                       "alternative": "Measurement error.", "next_check": "Inspect the raw source.",
                       "action": "follow_up" if "invalidate" in body["instructions"] else "hold"}}


class ReviewTests(unittest.TestCase):
    def test_closed_gate_and_ambiguous_citations(self):
        p = packet()
        p["gate_passed"] = False
        with self.assertRaisesRegex(ValueError, "gate closed"):
            review.get_cases(p)
        p["gate_passed"] = True
        p["cases"][0]["evidence"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            review.get_cases(p)

    def test_roles_are_blind_budgeted_and_resumable(self):
        cases = review.get_cases(packet())
        with TemporaryDirectory() as temp:
            out = Path(temp)
            requests = []

            def transport(body):
                requests.append(body)
                return reply(body)

            one = review.run_reviews(cases, "model", out, 1, transport)
            self.assertEqual(one["cases"][0]["status"], "awaiting_reviews")
            two = review.run_reviews(cases, "model", out, 1, transport)
            self.assertEqual(two["cases"][0]["status"], "review_disagreement")
            self.assertEqual(requests[0]["input"], requests[1]["input"])
            self.assertNotEqual(requests[0]["instructions"], requests[1]["instructions"])
            self.assertEqual(review.run_reviews(cases, "model", out, 2, transport)["new_calls"], 0)
            cases[0]["evidence"][0]["detail"] = "Corrected measurement"
            self.assertEqual(review.run_reviews(cases, "model", out, 2, transport)["new_calls"], 2)
            self.assertEqual(len(requests), 4)
            self.assertEqual(json.loads((out / "latest.json").read_text())["model"], "model")

    def test_invalid_citation_is_never_accepted(self):
        def invalid(body):
            r = reply(body)
            r["review"]["evidence_ids"] = ["other-case"]
            return r

        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "evidence IDs"):
                review.run_reviews(review.get_cases(packet()), "model", Path(temp), 2, invalid)
            self.assertFalse(list(Path(temp).glob("*.json")))

    def test_responses_api_envelope_and_refusal(self):
        body = review.request_for(packet()["cases"][0], "investigator", "test-model")
        approved = reply(body)["review"]
        for content, accepted in [
            ({"type": "output_text", "text": json.dumps(approved)}, True),
            ({"type": "refusal", "refusal": "refused"}, False),
        ]:
            with self.subTest(content_type=content["type"]):
                envelope = {"status": "completed", "model": "test-model", "id": "test-response",
                            "output": [{"type": "reasoning"}, {"type": "message", "content": [content]}]}
                with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), patch.object(
                    review, "urlopen", return_value=io.BytesIO(json.dumps(envelope).encode())
                ) as opened:
                    if accepted:
                        self.assertEqual(review.call_api(body)["review"], approved)
                    else:
                        with self.assertRaisesRegex(ValueError, "refusal"):
                            review.call_api(body)
                request = opened.call_args.args[0]
                self.assertEqual(request.get_method(), "POST")
                self.assertEqual(json.loads(request.data)["text"]["format"]["name"], "case_review")


if __name__ == "__main__":
    unittest.main()
