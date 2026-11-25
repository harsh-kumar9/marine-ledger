# Two independent Luna readings

Two fresh Codex subagents received the same seven contact sheets, the same task instruction and no parent chat. The selected model was `gpt-6-luna` for both. Each read all 98 crops once, with both expeditions interleaved in a deterministic shuffled order. Blue slot numbers identify fields. The packet shows enlarged pixels for legibility. It omits expedition, page, original order, answer keys, OCR outputs and other readers’ predictions. Each agent wrote one file before evaluation. This is procedural blinding on a previously published corpus. The two runs share a model and the same sheet layout.

The shared instruction asked for the complete printed station identifier, including letters, with one best visual reading per box or an empty string if illegible. It directed the reader to inspect each sheet using the image viewer and excluded OCR tools, other models, web search, the repository, source pages, answer keys and communication with other readers. The readers could inspect neighboring crops on a sheet. Each completed the task independently. Both results are reported without voting or selecting a winner.

Inspect the [packet](packet/) and the [two original submissions](reads/). To rebuild the seven sheets, run the following with Pillow 12 or later. The mapping file records how the anonymized slot numbers join back to the frozen crop IDs.

```sh
python3 packet.py /tmp/luna-sheets --mapping /tmp/luna-slots.json
```
