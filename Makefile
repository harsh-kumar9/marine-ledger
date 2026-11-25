PYTHON ?= python3
.PHONY: test replay verify

test:
	$(PYTHON) -m unittest discover -s tests -v

replay:
	$(PYTHON) pilot.py replay --out results

verify: test
	@set -eu; tmp=$$(mktemp -d); trap 'rm -r "$$tmp"' EXIT; \
	$(PYTHON) pilot.py replay --out "$$tmp"; \
	for file in "$$tmp"/*; do diff -r "$$file" "results/$$(basename "$$file")"; done; \
	$(PYTHON) agents/review.py plan --packet "$$tmp/review_packet.json"
