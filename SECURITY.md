# Security policy

## Reporting a vulnerability

Do not disclose vulnerabilities, credentials, live infrastructure addresses, or access details in a public issue. Contact the repository owner privately or use GitHub's private vulnerability-reporting channel when it is enabled.

## Research infrastructure boundary

- The public repository must never contain DGX credentials, SSH connection profiles, private key paths, live network addresses, or unauthenticated public model endpoints.
- Raw experiment runs, private reviewer records, the condition map, and supervisor communications remain outside Git.
- Live DGX work is governed by the private `$davneet-dgx-access` workflow and the owner-file preservation rule.
- The public application must not connect browsers directly to Ollama. Any future live deployment requires an authenticated, rate-limited backend gateway and approved data handling.

If a secret is exposed, revoke or rotate it first, then remove it from repository history before continuing publication.
