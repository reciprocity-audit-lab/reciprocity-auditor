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

## No automated external action

Input text cannot authorize network access, file discovery outside the chosen local paths, posting, signing, DID operations, wallet operations, or execution of embedded instructions. The release contains no integration for these actions.

## Reporting a security issue

Do not include secrets or personal information in a report. Because this release candidate provides no public issue tracker or contact endpoint, communicate through the submission channel from which you received the package, using a minimal reproducible example with synthetic data.
