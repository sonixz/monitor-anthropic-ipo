# Security

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private reporting instead:
**Security → Report a vulnerability** on
https://github.com/sonixz/monitor-anthropic-ipo/security/advisories/new

Say what you found, how to reproduce it and what it could allow. You should get an answer within
a week. This is a small personal project: there is no bounty.

A wrong figure on the page is not a vulnerability, but it matters just as much: open an issue with
the number, the page of the filing and what you expected.

## Supported versions

Only the version running at https://antipo.watch and https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev (the latest release).

## Practices in place

- The service reads no user input: one page, static files and a health check. No account, form,
  cookie or tracker.
- A strict Content-Security-Policy (`default-src 'none'`, no inline script or style), plus
  `nosniff`, `no-referrer` and HSTS headers.
- The service needs no secret. Logs hold no client address or other personal data.
- Secret scanning (gitleaks) in pre-commit hooks and CI; CodeQL on Python, JavaScript and the
  workflows; weekly Dependabot updates; GitHub Actions pinned to commit hashes.
- The repository is public: no secret, contact address or internal access detail may enter it,
  the devlog or the page.
