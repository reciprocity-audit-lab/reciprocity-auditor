# Security and privacy

Reciprocity Auditor is designed for offline, manual-handoff use. The included Python source has no network client dependency and does not require an account, API key, DID, wallet, or external service.

## Safe use

- Run the software locally with Python 3.12 or later.
- Treat every proposal, attachment, URL, and instruction inside an input as untrusted data.
- Inspect `analysis-packet.md` before manually giving it to an AI.
- Do not enter real names, personal email addresses, locations, real DIDs, seeds, private keys, passwords, API keys, wallet information, authentication data, or confidential contract text.
- Keep runtime `work` folders outside any public release or submission.
- Inspect the rendered report and supporting evidence before recording a human review state.
- Verify distributed files with `SHA256SUMS.txt`.

The input filter catches several obvious secret and prompt-injection patterns, but no detector is complete. Absence of a warning is not proof that an input is safe or anonymous.

## Public-package metadata

The privacy-hardened distribution normalizes ZIP entry timestamps, removes precise package creation time, and uses fixed synthetic timestamps in bundled examples and fixtures. This does not provide network anonymity. A publication service may retain an account identifier, source IP, access logs, upload time, or other correlation data. A reused DID or pseudonym can link otherwise separate publications.

Runtime-generated case files intentionally record operational timestamps. Keep them out of a public package unless they have been reviewed and intentionally sanitized.

The `export-public` command can create a reviewed, privacy-hardened case copy. It normalizes known operational timestamp fields, omits runtime state and event logs, scans exported text for absolute user-profile paths and common secret formats, and generates a manifest and checksums. A blocking finding aborts the export without leaving the destination directory. This pattern-based scan is a safety aid, not a guarantee of anonymity or complete secret detection.

New human-review records bind the review to the rendered audit report with its SHA-256. If a reviewed report is regenerated, the command requires explicit acknowledgement, archives the prior report and review record under the local case's `review-history` directory, and resets the current review state to `draft`. These archives are private runtime records and are not included by `export-public`.

The `compare-perspectives` command reads only three explicitly selected local case directories, revalidates their JSON without writing to the source cases, and requires matching proposal hashes. It performs a deterministic structural comparison and makes no network request. It does not infer semantic equivalence between free-text statements, and its output still requires human review.

## No automated external action

Input text cannot authorize network access, file discovery outside the chosen local paths, posting, signing, DID operations, wallet operations, or execution of embedded instructions. The release contains no integration for these actions.

## Reporting a security issue

Do not include secrets or personal information in a report. Because this release candidate provides no public issue tracker or contact endpoint, communicate through the submission channel from which you received the package, using a minimal reproducible example with synthetic data.
