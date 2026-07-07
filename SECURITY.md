# 🔒 Security Policy

Thank you for helping keep **GitHub Engineering Worker** secure.

Security is a core part of this project. If you discover a vulnerability, please report it responsibly so it can be investigated and fixed before public disclosure.

---

# 📢 Reporting a Security Vulnerability

**Please do not create a public GitHub Issue for security vulnerabilities.**

Instead, report the issue privately by emailing:

**security@example.com**

Please include as much information as possible:

- Vulnerability type (XSS, RCE, SSRF, Authentication Bypass, Command Injection, Secret Exposure, etc.)
- Detailed description
- Steps to reproduce
- Expected behavior
- Actual behavior
- Potential impact
- Proof of Concept (if applicable)
- Suggested mitigation (optional)

Providing clear reproduction steps helps us investigate and resolve issues much faster.

---

# ⏱ Response Timeline

We aim to respond as quickly as possible.

| Stage | Target Time |
|--------|-------------|
| Initial acknowledgement | Within 48 hours |
| Initial investigation | Within 5 business days |
| Status updates | As progress is made |
| Security fix | As quickly as reasonably possible |

Complex vulnerabilities may require additional investigation time.

---

# 🤝 Responsible Disclosure

We ask all researchers to follow responsible disclosure practices.

Please:

- Do not publicly disclose vulnerabilities until they have been fixed.
- Do not intentionally access, modify, or destroy user data.
- Do not exploit vulnerabilities beyond what is necessary to demonstrate their existence.
- Give us reasonable time to investigate and resolve reported issues.
- Report findings privately before discussing them publicly.

We greatly appreciate responsible security research.

---

# 🛡 Security Principles

GitHub Engineering Worker is designed around the following security principles.

## Least Privilege

Agents, tools, and integrations should operate with only the permissions required to complete their tasks.

---

## Secure Authentication

- Store API keys using environment variables.
- Never hardcode secrets into the repository.
- Rotate credentials when compromise is suspected.
- Limit token permissions whenever possible.

---

## Input Validation

All external input should be treated as untrusted, including:

- GitHub Issues
- Pull Requests
- User prompts
- Repository contents
- Tool outputs
- External API responses

Validate and sanitize all input before processing.

---

## Safe Tool Execution

The engineering worker should:

- Avoid executing untrusted commands.
- Validate tool parameters.
- Restrict filesystem access where appropriate.
- Prevent accidental modification of unrelated repositories or files.

---

## Dependency Security

Regularly:

- Update dependencies
- Review security advisories
- Remove unused packages
- Patch known vulnerabilities

---

## Logging & Auditing

Security-relevant actions should be logged, including:

- Repository operations
- GitHub API actions
- Tool execution
- Agent execution
- Authentication failures
- Unexpected runtime errors

Logs should never expose secrets or sensitive credentials.

---

## AI Agent Safety

Since this project includes autonomous engineering capabilities:

- Agent actions should be traceable.
- High-risk operations should require explicit confirmation when appropriate.
- Sensitive files should not be modified unintentionally.
- Engineering decisions should be transparent and auditable.

---

# 🚫 Out of Scope

The following generally do **not** qualify as security vulnerabilities:

- Feature requests
- Documentation improvements
- Cosmetic UI issues
- Code style suggestions
- Performance optimizations without a security impact
- Missing best practices without an exploitable risk

---

# 📜 Supported Versions

Security fixes are generally provided for the latest maintained version of the project.

Older versions may not receive security updates.

---

# ❤️ Our Commitment

We are committed to:

- Protecting users and repositories
- Responding to security reports professionally
- Investigating reports fairly
- Shipping security fixes as quickly as possible
- Continuously improving the project's security posture

We sincerely appreciate everyone who helps make GitHub Engineering Worker safer.
