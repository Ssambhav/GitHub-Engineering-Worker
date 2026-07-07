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

Future versions will focus on:

- Multi-agent collaboration
- Parallel issue solving
- Automatic regression testing
- CI/CD integration
- Semantic repository memory
- Long-term engineering learning
- Repository-wide reasoning
- Continuous engineering workflows

---

# 🏗 System Architecture
```
(continue with the architecture section here...)
```
