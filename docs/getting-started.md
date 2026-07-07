# Getting Started Guide

Welcome to the GitHub Engineering Worker! This guide will help you set up and get started with your autonomous AI engineering system.

## Prerequisites

Before you begin, ensure you have the following installed:

- **OpenClaw:** Follow the official OpenClaw installation guide.
- **Git:** For version control.
- **Python 3.9+:** Recommended for development.
- **GitHub Account:** With appropriate permissions for the repositories you intend to manage.
- **(Optional) Docker / Docker Compose:** For containerized development and deployment.

## 1. Clone the Repository

First, clone the GitHub Engineering Worker repository to your local machine:

```bash
git clone https://github.com/your-org/github-engineering-worker.git
cd github-engineering-worker
```

## 2. Configure OpenClaw

Place your OpenClaw agent configuration within the `.openclaw/` directory. A basic `config.yaml` might look like this:

```yaml
agents:
  github-engineering-worker:
    model: openai/gpt-5.4 # Uses your active OpenClaw/Codex-authenticated model by default
    # Further agent-specific configurations

plugins:
  # Configure any necessary OpenClaw plugins, e.g., for GitHub API access
  github:
    token: "${OPENCLAW_GITHUB_TOKEN}"
```

**Important:** Always use environment variables for sensitive information like API tokens.
If you already authenticated OpenClaw with Codex/OpenAI OAuth, you do not need a Gemini API key for the Discord worker.

## 3. Configure Project Settings

Edit `configuration/settings.yaml` to define global project parameters, such as GitHub organization details, database connections, and default agent behaviors. Remember to use environment variables for secrets.

```yaml
github:
  api_token: "${GITHUB_API_TOKEN}"  # Your GitHub Personal Access Token
  organization: "your-github-org"

# ... other settings
```

## 4. Install Dependencies

If your agents or tools have specific Python dependencies, install them. You might have `requirements.txt` files within `agents/`, `tools/`, or `utilities/` subdirectories.

```bash
pip install -r requirements.txt # Example for a project-level requirements file
```

## 5. Running the System

Once configured, you can start the GitHub Engineering Worker. The exact command will depend on your OpenClaw setup and how you intend to run the main agent. Typically, this involves launching the OpenClaw gateway and activating your agent.

Consult the OpenClaw documentation for details on running agents and workflows.

## 6. Monitoring and Debugging

- **Logs:** Check the `logs/` directory for runtime output and error information.
- **Audit Trails:** Review `audit/` for detailed records of agent decisions and actions.
- **States:** Inspect `states/` to understand the current progress of ongoing tasks.

## Next Steps

- Explore the `agents/`, `workflows/`, and `tools/` directories to understand the available components.
- Refer to `docs/architecture.md` for an in-depth understanding of the system's design.
- Start by creating a test GitHub Issue and observe how the system responds.

---
