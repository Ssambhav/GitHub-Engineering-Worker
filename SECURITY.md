# Security Policy

## Reporting a Vulnerability

We take the security of the GitHub Engineering Worker project seriously. If you discover a security vulnerability, we encourage you to report it to us immediately.

Please DO NOT open a public GitHub Issue. Instead, send an email to [security@example.com](mailto:security@example.com) with a detailed description of the vulnerability, including:

- Type of vulnerability (e.g., XSS, SQLi, authentication bypass, data leakage)
- Steps to reproduce the vulnerability
- Potential impact
- Any suggested mitigations

We will acknowledge receipt of your report within 48 hours and provide a more detailed response within 5 business days, outlining our plan to address the issue. We aim to fix critical vulnerabilities as quickly as possible.

## Responsible Disclosure

We kindly request that you adhere to the principles of responsible disclosure:

- Do not disclose the vulnerability publicly until it has been patched.
- Do not exploit the vulnerability beyond what is necessary to prove its existence.
- Do not access, modify, or destroy any user data without explicit permission.

## Security Best Practices for Development

All contributors and developers are expected to follow these security best practices:

- **Principle of Least Privilege:** Agents and tools should only have the minimum necessary permissions.
- **Input Validation:** All inputs, especially from external sources like GitHub Issue descriptions, must be thoroughly validated.
- **Secure Credential Management:** API tokens and other sensitive information must be stored and accessed securely, preferably via environment variables or a secrets management system.
- **Dependency Scanning:** Regularly scan for vulnerabilities in third-party libraries and dependencies.
- **Code Review:** All code changes should undergo thorough security review.
- **Logging and Monitoring:** Implement comprehensive logging for security-relevant events and monitor for suspicious activity.

## Our Commitment

We are committed to:

- Protecting the data and integrity of the GitHub Engineering Worker and its users.
- Addressing security vulnerabilities in a timely and transparent manner.
- Continuously improving our security posture through ongoing reviews and updates.

---
