# Historical marine-record protocol

Use the commands in the README to replay the frozen extracts and reference queries before extending the corpus. Treat a named organism at a documented collection or observation event as the unit of review.

* The data worker owns edition, page IDs, original scans or text, query times, bounds and coverage. Keep OBIS API access serial, including across agent jobs. Give investigators cached results to review concurrently.
* The calibration worker freezes control passages and their expected decisions outside the extractor. Include actual events, non-local mentions and difficult negatives. On rule revision, seek a new volume, author or taxon for a transfer check.
* After calibration, an investigator and skeptic independently interpret the same packet. Quote the page and retain historical spelling, uncertainty and station information. Keep publication date distinct from event date. See [the review worker](agents/README.md).
* The coordinator reconciles against the scan, accepted names and synonyms, station records, specimen identifiers and the deep link to a possible catalog match. Distinguish locality agreement from evidence for the same event.
* Record proposed, verified, duplicate, rejected and unresolved counts. Document search filters and coverage for every unmatched record. Keep coordinates, dates and specimen numbers unknown when the evidence cannot substantiate them.

## Publishing results for general readers

For a new scientific result, explain the question in everyday language, why its answer matters and what earlier expeditions, archives or catalogs already established. Show the specific obstacle using a real example. When a graphic helps, make it legible at phone width, give it descriptive alternative text and link the underlying page, data and comparison. Close with what the evidence establishes and what observation could change the conclusion.

When methods disagree, preserve each original output, identify a competing explanation and name an independent source or observation that can distinguish them. Record whether the check resolved a reading, identified a known event, or left a testable question. Audit some agreements when the methods share inputs. Count candidates and catalog coverage before making a novelty claim. [Worked Siboga cases](experiments/full-page-transfer/DISAGREEMENTS.md)
