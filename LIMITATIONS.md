# Known limitations

This release candidate supports structured inquiry; it does not establish truth, fairness, legality, validity, or an appropriate enforcement outcome.

## Decision limits

- AI does not make the final decision about good or bad, legality, adoption, rejection, enforcement, or punishment.
- Human review is mandatory.
- The output is not legal advice and does not replace domain experts, affected participants, safety reviewers, or accountable decision-makers.
- The tool cannot verify facts that are absent from the input and must not fill them in by speculation.
- A `reviewed` state confirms review of the audit report only; it does not approve the underlying proposal.

## Technical limits

- This is a Windows PowerShell-oriented, offline, manual-handoff MVP.
- No AI model is bundled. Users transfer the packet and JSON response manually.
- No API, web service, server, browser automation, Git integration, Technocore integration, DID operation, wallet connection, or external posting is included.
- The schema and deterministic validation can reject malformed or prohibited output patterns, but cannot guarantee semantic correctness or completeness.
- Secret and identity pattern checks are defensive filters, not comprehensive data-loss-prevention controls.
- The PowerShell verification and three-perspective demo use fixed fixtures. They demonstrate reproducible mechanics, not semantic audit accuracy or independent reasoning.

## Anonymity limits

The privacy-hardened package removes direct identity markers detected by the release checks and normalizes public archive timestamps. It does not guarantee that a contributor cannot be identified. Publication services and network operators may retain account, IP, access-log, and upload-time data. Reusing a DID, pseudonym, file hash, or distinctive text across services may allow correlation.

## Evaluation limits

The release records 9 cases, three perspectives, and 27 evaluation units reported PASS. Phase 3.3 records 11 axes and 99 comparison units: `consistent: 37`, `complementary: 32`, `tension: 18`, `direct_conflict: 0`, and `cannot_compare: 12`. Six high-priority cases were reviewed by a human and all six were recorded as `acceptable_for_release`.

The following metadata remains unresolved:

- `model_display_name: null`
- `reasoning_setting: null`
- `configuration_comparability: not_demonstrated`

Version 0.2 work can record a model display name or reasoning setting only when an operator explicitly identifies its source. A missing value remains `null` and is not inferred. Even if the recorded display names and reasoning settings match, other unrecorded configuration can differ, so complete configuration comparability remains `not_demonstrated`.

Comparison-review records can distinguish self-attested `independent`, `not_independent`, and `unknown` reviewers and bind those records to comparison hashes. The software does not verify the reviewer's identity, independence, expertise, or separation from generation and comparison work. A recorded independent review remains evidence supplied by the reviewer, not a guarantee by the tool.

The four additional evaluation scenarios cover missing information, justified asymmetry, conflicts of interest, and undefined enforcement. They are regression fixtures, not a representative benchmark, and do not establish semantic accuracy or performance on other contracts and rules.

Phase 3.3 was an operator semantic comparison, not an independent human evaluation. The evidence does not establish that the same model and reasoning settings were used, and it does not establish independent heterogeneous-model evaluation. The 27/27 PASS result is bounded to the recorded evaluation units and does not mean 100% general performance, 100% audit accuracy, proof of complete fairness, or reliable judgment for every contract.

See [`evaluation/README.md`](evaluation/README.md) for the included records.

## Reproducibility limits

[`Verify-LocalWorkflow.ps1`](Verify-LocalWorkflow.ps1) verifies the local state transition with a fixed fixture. The three-perspective demo deliberately supplies the same structured analysis to all three roles and therefore cannot measure whether Justice, Reversal, and Tower produce meaningfully distinct or independently generated findings. Reproduction of files and hashes establishes procedural consistency only.
