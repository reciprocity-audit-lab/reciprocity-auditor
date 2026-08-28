# Reciprocity Auditor — Release Candidate v0.1 (privacy-hardened package)

Reciprocity Auditor is an offline, manual-handoff tool for examining contract terms, community rules, policies, and proposed coordination rules. It structures questions about reciprocity, justified asymmetry, enforcement, remedies, and affected parties. It does not decide whether conduct is good or bad, legal or illegal, acceptable or unacceptable, or deserving of punishment.

This is a minimal public release candidate assembled from Phases 1–3.3. It is not an official Technocore deliverable and does not guarantee eligibility for any airdrop or reward.

This distribution normalizes ZIP entry timestamps and omits the precise package creation time. Timestamps in bundled examples and fixtures are fixed synthetic values. Runtime-generated case files still contain operational timestamps and must be reviewed before publication.

## Three review perspectives

- **Justice** maps actors, rights, benefits, responsibilities, burdens, risks, missing information, and available remedies. It asks whether an asymmetry has a relevant and proportionate reason.
- **Reversal** exchanges the positions of affected actors and tests whether the same rationale remains defensible. It highlights one-sided privileges, exemptions, and obligations while preserving the possibility of reasonable asymmetry.
- **Tower** examines operational enforcement and governance: who decides, who executes, who oversees, whether self-exceptions exist, and whether notice, records, appeal, shutdown, refund, or recovery procedures are defined.

The perspectives are prompts for structured review, not moral scores or final decisions. Human review is required for every report.

## Offline workflow

The MVP makes no API calls. A user prepares a local analysis packet, manually gives that packet to an AI system of their choice, saves only the returned JSON locally, validates it, renders a Markdown report, and records a human review state.

```text
proposal → prepare → manual AI handoff → validate → render → human review → status
```

The software does not contact a web service, Technocore, Git, a DID system, or a wallet. Do not place secrets, personal data, real DIDs, credentials, or wallet information in an input.

## Requirements

- Windows PowerShell 5.1 or PowerShell 7
- Python 3.12 or later
- No third-party Python packages
- No network connection

## Minimal Windows PowerShell run

Open PowerShell in this directory:

```powershell
Copy-Item '.\examples\proposal.txt' '.\proposal.txt'
.\Run-ReciprocityAuditor.ps1 prepare --input '.\proposal.txt' --output '.\work\case-001' --case-id 'case-001'
Copy-Item '.\fixtures\analysis-valid.json' '.\work\case-001\analysis.json'
.\Run-ReciprocityAuditor.ps1 validate --input '.\work\case-001\analysis.json'
.\Run-ReciprocityAuditor.ps1 render --input '.\work\case-001\analysis.json'
.\Run-ReciprocityAuditor.ps1 review --case '.\work\case-001' --state reviewed --reviewer-label 'reviewer-1'
.\Run-ReciprocityAuditor.ps1 status --case '.\work\case-001'
```

The fixture is for reproduction only. In normal use, inspect `analysis-packet.md`, hand it to an AI manually, and save the JSON response as `analysis.json`. The `reviewed` state means a human reviewed the audit report; it does not approve the underlying proposal.

Representative files:

- Input: [`examples/smoke-case/proposal.txt`](examples/smoke-case/proposal.txt)
- Manual handoff packet: [`examples/smoke-case/analysis-packet.md`](examples/smoke-case/analysis-packet.md)
- Structured response: [`examples/smoke-case/analysis.json`](examples/smoke-case/analysis.json)
- Rendered report: [`examples/smoke-case/audit-report-ja.md`](examples/smoke-case/audit-report-ja.md)

For a Japanese walkthrough, see [`QUICKSTART-JA.md`](QUICKSTART-JA.md).

## Explicit three-perspective workflow

`prepare --perspective justice|reversal|tower` records the selected role in both the analysis packet and the local case metadata. Three validated results for the same proposal can then be passed to `compare-perspectives`, which performs a deterministic structural comparison across 11 axes.

The five comparison labels are `consistent`, `complementary`, `tension`, `direct_conflict`, and `cannot_compare`. The comparator does not infer semantic equivalence between free-text statements and uses `direct_conflict` only for explicit opposite values in the same structured Boolean field. Its output supports human review; it does not decide which perspective is correct or make moral, legal, adoption, enforcement, or punishment decisions.

See [`QUICKSTART-JA.md`](QUICKSTART-JA.md) for the complete Windows commands.

## Evaluation records

`record-run-config` binds only explicitly observed model display names and reasoning settings to the SHA-256 of a validated analysis. If a value was unavailable, the record preserves `null`; the tool does not infer it.

Even when all recorded display names and reasoning settings match, full configuration comparability remains `not_demonstrated` because unrecorded settings may differ. The comparison reports the narrower relationship separately as `recorded_fields_match`, `recorded_fields_differ`, or `incomplete`.

`review-comparison` supports multiple hash-bound human review records using anonymous labels. Reviewer independence is recorded as the self-attested value `independent`, `not_independent`, or `unknown`; the tool does not verify identity or organizational independence.

[`fixtures/evaluation-scenarios.json`](fixtures/evaluation-scenarios.json) covers missing information, justified asymmetry, conflicts of interest, and undefined enforcement. These small regression fixtures do not establish general audit accuracy. Positive results continue to be reported with limitations.

## Evaluation record

The Phase 3.2 deterministic aggregation covered 9 cases under Justice, Reversal, and Tower: 27 evaluation units, all reported PASS. Phase 3.3 compared the three perspectives across 11 axes, producing 99 comparison units: `consistent: 37`, `complementary: 32`, `tension: 18`, `direct_conflict: 0`, and `cannot_compare: 12`. Six high-priority cases were subsequently reviewed by a human, and all six were recorded as `acceptable_for_release`.

These results have strict limits:

- `model_display_name: null`
- `reasoning_setting: null`
- `configuration_comparability: not_demonstrated`
- Phase 3.3 was not an independent human evaluation.
- 27/27 PASS does not mean 100% general performance, 100% audit accuracy, or proof of complete fairness.
- The evidence does not demonstrate identical model/reasoning settings or independent heterogeneous-model evaluation.

See [`evaluation/README.md`](evaluation/README.md) and [`LIMITATIONS.md`](LIMITATIONS.md) before interpreting the results.

## Safety and scope

AI output is an aid for inquiry. A human must inspect the source text, evidence, alternative interpretations, missing information, and potential consequences. The tool provides no legal advice and must not automate adoption, rejection, enforcement, or punishment.

Security and privacy guidance is in [`SECURITY.md`](SECURITY.md), [`docs/phase1/PRIVACY-MODEL-JA.md`](docs/phase1/PRIVACY-MODEL-JA.md), and [`docs/phase1/SAFETY-AND-LIMITS-JA.md`](docs/phase1/SAFETY-AND-LIMITS-JA.md).

## License

Released under the [MIT License](LICENSE).
