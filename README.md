## A small tool for a very large question

Could people with different histories, values, and interests build shared rules together—not by hiding disagreement, but by making it visible, structured, and open to review?

Reciprocity Auditor began with that question.

When I first imagined this project, I pictured a science-fiction decision system in which several distinct intelligences examine the same problem, challenge one another’s conclusions, and leave the final choice to humans.

In this prototype, that idea is expressed through three complementary review perspectives:

* **Justice** — Who benefits, who carries the burden, and what remedies exist?
* **Reversal** — Would the reasoning still hold if the parties changed places?
* **Tower** — Who enforces the rule, who oversees them, and what happens when the system fails?

Together, these perspectives help surface hidden asymmetries, overlooked stakeholders, unclear enforcement, missing appeals, and evidence gaps before a decision is made.

This is not a single all-knowing AI that decides what is fair. It is a small, offline first step toward a deliberative system where different perspectives expose one another’s blind spots and people retain responsibility for the final decision.

### What this release includes

* An offline Python 3.12+ CLI with no third-party packages
* A Windows PowerShell launcher
* Source code, tests, fixtures, and worked examples
* An audit protocol and JSON schema
* Evaluation records from Phases 3–3.3
* MIT License and reproducible checksums

The workflow uses a manual AI handoff and makes no API calls. Every substantive report requires human review.

### What was tested

The release candidate was exercised across **9 cases and 27 evaluation units** using the Justice, Reversal, and Tower perspectives. All 27 units passed the defined holdout checks.

A cross-perspective review then examined **99 comparison units across 11 axes**:

* 37 consistent
* 32 complementary
* 18 in tension
* 0 direct conflicts
* 12 that could not be compared

Six high-priority cases were subsequently reviewed by a human and recorded as acceptable for this release candidate.

### What this does not prove

This is not a fairness oracle, legal adviser, or automatic decision-maker.

The recorded model name and reasoning setting are unavailable, configuration comparability was not demonstrated, and the cross-perspective review was not an independent human evaluation. The 27/27 result does **not** mean 100% general accuracy.

This is not an official Technocore deliverable and does not guarantee an airdrop or reward.

Archive timestamps are normalized and bundled example timestamps are synthetic. This reduces incidental metadata exposure but does not guarantee anonymity from network or platform operators.

### Archive integrity

SHA-256:

`8f957ad300b2f4779ab906b00828a7af2a2214e9f81428fc8adbd5e7a8c0f4ca`
