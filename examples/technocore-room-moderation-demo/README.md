# Hypothetical Technocore Room-Moderation Audit

This directory is a worked example of Reciprocity Auditor applied to a fictional public-room moderation rule.

The proposal is **not an official Technocore rule**, is not in force, and is not presented as a recommendation. It was designed to demonstrate how Justice, Reversal, and Tower-style questions can surface governance trade-offs while leaving final decisions to humans.

## What the example examines

The fictional draft combines rapid safety intervention with public action records, private evidence retention, an appeal window, and possible permanent exclusion. The audit highlights:

- potential conflict when a room owner can both enforce and decide appeals;
- undefined thresholds for urgent action and repeated violations;
- missing restoration and outage procedures;
- burdens placed on affected authors;
- possible effects on third parties named in retained content; and
- evidence needed before necessity and proportionality can be assessed.

The audit also records the countervailing reason for asymmetry: moderators may need delegated authority to respond quickly to credential requests, malicious instructions, threats, or spam.

## Files

- [`proposal.txt`](proposal.txt) — fictional input rule.
- [`analysis-packet.md`](analysis-packet.md) — isolated manual-handoff packet.
- [`analysis.json`](analysis.json) — Schema-valid structured analysis.
- [`audit-report-ja.md`](audit-report-ja.md) — rendered Japanese report.
- [`HUMAN-REVIEW-NOTE-JA.md`](HUMAN-REVIEW-NOTE-JA.md) — separate record of human review.
- [`PUBLICATION-MANIFEST.json`](PUBLICATION-MANIFEST.json) — provenance, privacy transformations, and limitations.
- [`SHA256SUMS.txt`](SHA256SUMS.txt) — checksums for this public example.

## Reproduce locally

From the Reciprocity Auditor repository root in Windows PowerShell:

```powershell
.\Run-ReciprocityAuditor.ps1 prepare --input '.\examples\technocore-room-moderation-demo\proposal.txt' --output '.\work\technocore-room-moderation-demo' --case-id 'technocore-room-moderation-demo'
Copy-Item '.\examples\technocore-room-moderation-demo\analysis.json' '.\work\technocore-room-moderation-demo\analysis.json'
.\Run-ReciprocityAuditor.ps1 validate --input '.\work\technocore-room-moderation-demo\analysis.json'
.\Run-ReciprocityAuditor.ps1 render --input '.\work\technocore-room-moderation-demo\analysis.json'
```

A fresh render creates a runtime timestamp and begins in `draft` review state. Human review must be recorded separately with the `review` command.

## Validation and review

- Proposal SHA-256: `7c40b9a1a24c1ad22df90c79d305cbc192097098ffcf52311faf99b06297fe47`
- JSON validation: pass
- Human review: reviewed for inclusion as a public demonstration
- Meaning: the audit report was inspected; the fictional proposal itself was not approved.

## Privacy treatment

Precise runtime timestamps in the packet and rendered report were replaced with the fixed synthetic value `1980-01-01T00:00:00Z`. No real DID, seed, private key, email address, wallet information, or Windows absolute path is included.

## Limitations

The analysis was generated through a manual AI handoff. The model display name and reasoning setting were unavailable, and configuration comparability was not demonstrated. This single example does not establish general audit accuracy, complete fairness, legal validity, or suitability for automatic enforcement.

