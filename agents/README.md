# Evidence review

Run the repository's replay first. Its calibration result controls which cases can reach this stage. From the repository root, inspect the admitted batch with Python 3 on macOS or Linux.

```sh
python3 agents/review.py plan --limit 5
```

There are two equally valid ways to review a packet.

* **In a Codex chat**, give each worker one case from `results/review_packet.json` and one of the two role descriptions in `review.py`. Ask each for its assessment, evidence IDs, strongest competing explanation, follow-up check and action. Keep their first passes independent. Have the coordinator compare both and verify the citations against the original measurements or scan. This route uses the existing chat session.
* **Through the Responses API**, export `OPENAI_API_KEY` and set `REVIEW_MODEL` to a model available to that account with Structured Outputs support.

```sh
python3 agents/review.py run --model "$REVIEW_MODEL" --limit 1 --max-calls 2
```

The API workers receive the same quoted evidence, different role instructions and no tools. The coordinator checks cited IDs against that case and flags disagreement for review. Citation validation checks that an ID exists. A human or source-checking agent still has to decide whether its contents support the inference.

Each invocation defaults to one case, two calls and at most 1,600 output tokens per call. Requests use at most 32,000 bytes of case data each. These are request bounds, and dollar cost depends on the selected model. Increase the case and call limits together to review a larger batch. `--max-calls 0` reads saved results offline. A batch that consumes its call allowance retains `awaiting_reviews` for unfinished cases.

Validated responses go in `.agent-runs/`. A receipt stores the evidence digest, request digest, role, resolved model, response ID, usage and decision. The same evidence, instructions, settings and model reuse the receipt. A directory lock prevents concurrent runs from spending against the same cache. On an API failure or invalid answer the worker stops. If the connection broke after the server received a request, a manual rerun can incur a second charge. Inspect `latest.json` for the last completed invocation.

For each promoted case, record which source was opened, why the alternative survived or failed, and how much reviewer time the check took. Only count an item as useful after a source-level check. Track that count alongside cases considered, rejections, API usage and elapsed review time as the batch grows.

[Responses API quickstart](https://developers.openai.com/api/docs/quickstart) · [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
