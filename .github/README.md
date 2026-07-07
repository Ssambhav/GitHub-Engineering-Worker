# 🧠 GitHub Engineering Worker

> An autonomous AI Software Engineer that understands GitHub issues, investigates repositories, writes production code, and creates Pull Requests through Discord.

---

# 🎯 Project Goal

GitHub Engineering Worker is **not a chatbot**.

It is an autonomous engineering system designed to own the complete software engineering workflow—from issue understanding to pull request creation—with minimal human intervention.

Instead of asking an AI to write code manually, users simply ask:

```text
Fix issue #12
```

The worker performs repository investigation, engineering reasoning, source-code modification, Git operations, and GitHub automation autonomously.

---

# 📖 Engineering Specification

This repository contains several specification documents that define the worker's behaviour.

---

## 📄 CLAW.md

Defines how the OpenClaw engineering agent should operate.

Includes:

- Engineering philosophy
- Repository investigation strategy
- Root-cause analysis rules
- Code modification principles
- Safety constraints
- Engineering workflow
- Pull Request expectations

---

## 🤖 AGENTS.md

Defines every autonomous agent inside the system.

Contains:

- Agent responsibilities
- Execution boundaries
- Collaboration model
- Ownership of tasks
- Runtime expectations

---

## ❤️ SOUL.md

Defines the long-term identity of the engineering worker.

Contains:

- Project vision
- Decision-making principles
- Autonomy philosophy
- Engineering values
- Behavioural rules

---

## 🛠 TOOLS.md

Documents every runtime capability available to the worker.

Examples include:

- GitHub
- Git
- Filesystem
- Repository Search
- Browser
- Engineering Pipeline
- Queue Management
- Memory
- Scheduling

Each tool documents:

- Purpose
- Inputs
- Outputs
- Safety requirements
- Expected behaviour

---

# 📥 Inputs

The worker consumes structured engineering context including:

- GitHub Issues
- Repository source code
- Repository metadata
- Project specification files
- Runtime memory
- Previous engineering reports
- Tool outputs

---

# 📤 Outputs

Each engineering execution produces structured outputs such as:

- Source code modifications
- Git commits
- Pull Requests
- Engineering reports
- Audit logs
- Retry decisions
- Escalation reports
- Execution summaries

---

# 🔌 Tool Contracts

Every runtime capability follows a common contract.

Input

- Repository
- Issue
- Context
- Runtime configuration

Output

- Engineering result
- Metadata
- Logs
- GitHub actions (optional)

This allows tools to remain modular and independently replaceable.

---

# 🔄 Workflow States

Every issue progresses through defined engineering states.

```text
Queued
    │
Running
    │
Repository Investigation
    │
Issue Understanding
    │
Engineering
    │
Repository Modification
    │
Commit
    │
Push
    │
Pull Request
    │
Completed
```

Possible terminal states:

- completed
- retry
- retry_or_escalate
- escalated
- cancelled

---

# 🧠 Memory Strategy

The worker maintains engineering memory instead of conversational memory.

Stored information includes:

- Previous engineering attempts
- Retry history
- Repository context
- Execution reports
- Engineering summaries
- Issue history

Memory is used to improve future engineering decisions and avoid repeating failed approaches.

---

# 🔁 Exception Handling & Retry Strategy

Engineering failures are classified rather than treated uniformly.

Depending on the failure, the worker may:

- Retry automatically
- Retry with additional engineering context
- Retry after repository refresh
- Escalate for human review

Retries preserve execution history to improve subsequent attempts.

---

# 🚨 Escalation Policy

Human escalation occurs only when autonomous engineering cannot safely continue.

Examples include:

- Missing credentials
- External production systems
- Human approvals
- Repository limitations
- Insufficient engineering evidence
- Unsupported workflows

---

# 📝 Audit & Logging

Every engineering execution records:

- Repository
- Issue
- Branch
- Commit
- Files modified
- Execution mode
- Engineering summary
- Retry history
- Escalation reason
- Timeline
- Runtime metadata

This provides complete traceability for every engineering decision.

---

# 🤖 Current Autonomous Capabilities

The current worker can autonomously:

- Understand GitHub Issues
- Investigate repositories
- Search source code
- Build repository context
- Modify source code
- Create commits
- Push branches
- Create Pull Requests
- Maintain engineering memory
- Retry failed engineering runs
- Escalate when required
- Generate engineering reports
- Operate entirely through Discord

---

# 🚀 Future Improvements

The current version requires a user to manually trigger the engineering workflow using a command like:

```text
Fix issue #12
```

Future versions aim to make the worker **fully autonomous**, allowing it to continuously monitor repositories and respond without manual intervention.

Planned improvements include:

- 🔄 **Automatic GitHub Issue Monitoring**  
  Periodically check repositories (e.g., every 30 minutes using a scheduler or cron job). When a new issue is detected, automatically begin the engineering workflow.

- 🤖 **Hands-Free Issue Resolution**  
  Remove the need for manual Discord commands by allowing the worker to detect, prioritize, and work on new issues autonomously.

- 👥 **Multi-Agent Collaboration**  
  Introduce specialized AI agents (Issue Analyzer, Repository Investigator, Code Engineer, Reviewer) that collaborate to solve complex engineering tasks.

- 🧪 **Automatic Validation Pipeline**  
  Execute project-specific tests, linting, or build commands when available before creating a Pull Request.

- 🧠 **Long-Term Engineering Memory**  
  Learn from previous engineering attempts to avoid repeating failed solutions and improve future decisions.

- 📊 **Smarter Issue Prioritization**  
  Automatically prioritize issues based on severity, labels, or repository rules.

- 🔔 **Proactive Notifications**  
  Notify maintainers when engineering work starts, finishes, requires human review, or encounters blockers.

- 🌐 **Multi-Repository Support**  
  Allow a single worker to manage and engineer across multiple GitHub repositories simultaneously.

- 🚀 **CI/CD Integration**  
  Automatically trigger engineering workflows after CI failures or merge completed Pull Requests once all checks succeed.

# 🏗 System Architecture
```
(continue with the architecture section here...)
```
