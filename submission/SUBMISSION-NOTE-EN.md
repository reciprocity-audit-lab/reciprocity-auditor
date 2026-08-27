# Reciprocity Auditor RC v0.1 (privacy-hardened package) — Submission note

This package is a minimal offline release candidate for Reciprocity Auditor, a manual-handoff tool that helps people review proposed contracts and coordination rules through Justice, Reversal, and Tower perspectives. It may help Technocore or other coordination systems surface one-sided privileges, missing stakeholders, unclear enforcement, absent appeals, and evidence gaps before accountable people make a decision.

It does not replace human judgment and is not an official Technocore deliverable. It makes no promise of airdrop or reward eligibility. The workflow is reproducible locally with Python 3.12+ and Windows PowerShell, uses no AI API, and includes source, tests, fixtures, examples, protocol/schema materials, evaluation records, and checksums.

Public archive timestamps are normalized and bundled example timestamps are synthetic. This reduces incidental metadata exposure but does not guarantee network or operator anonymity.

Recorded evaluation: 9 cases, 27 evaluation units across three perspectives, all reported PASS; Phase 3.3 compared 11 axes and 99 units (`consistent: 37`, `complementary: 32`, `tension: 18`, `direct_conflict: 0`, `cannot_compare: 12`). A human reviewed six high-priority cases and recorded all six as `acceptable_for_release`.

Known limits: model name and reasoning setting are `null`; configuration comparability is `not_demonstrated`; Phase 3.3 was not an independent human evaluation; 27/27 PASS does not imply 100% general performance or audit accuracy. Every substantive use requires human review.
