"""Issue understanding and classification helpers."""

from __future__ import annotations

import re

from engineering.models import EngineeringIssue, IssueUnderstanding

ISSUE_CATEGORIES: tuple[str, ...] = (
    "Frontend UI",
    "Backend",
    "API",
    "Business Logic",
    "Validation",
    "Database",
    "Authentication",
    "Performance",
    "Documentation",
    "Configuration",
    "Testing",
    "Build/CI",
)

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Frontend UI": ("ui", "frontend", "component", "css", "theme", "layout", "button", "page", "screen", "hook"),
    "Backend": ("backend", "server", "worker", "service", "queue", "job", "runtime"),
    "API": ("api", "endpoint", "request", "response", "graphql", "rest", "route"),
    "Business Logic": ("logic", "rule", "calculation", "workflow", "state", "decision"),
    "Validation": ("validation", "validate", "invalid", "required", "schema", "constraint"),
    "Database": ("database", "db", "sql", "query", "migration", "model", "orm"),
    "Authentication": ("auth", "login", "token", "session", "permission", "oauth", "credential"),
    "Performance": ("performance", "slow", "latency", "timeout", "memory", "cpu"),
    "Documentation": ("docs", "documentation", "readme", "typo", "guide", "example"),
    "Configuration": ("config", "configuration", "env", "yaml", "toml", "json", "setting"),
    "Testing": ("test", "pytest", "spec", "assert", "fixture"),
    "Build/CI": ("build", "ci", "workflow", "github actions", "pipeline", "compile"),
}

_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "issue",
    "bug",
    "fix",
    "error",
    "when",
    "then",
    "into",
    "does",
    "should",
}


def understand_issue(issue: EngineeringIssue) -> IssueUnderstanding:
    """Classify the issue and normalize the engineering problem statement."""

    text = _normalized_text(issue)
    category, category_score = _classify(text)
    problem = (issue.title or "Issue received").strip()
    expected = _extract_after_label(text, ("expected", "should", "wanted", "desired"), fallback="Expected behavior is not explicitly stated.")
    actual = _extract_after_label(text, ("actual", "currently", "instead", "but"), fallback="Actual behavior is not explicitly stated.")
    acceptance = _acceptance_criteria(issue, category, expected, actual)
    terms = _search_terms(issue, category)
    confidence = min(0.95, 0.45 + (0.1 if expected != "Expected behavior is not explicitly stated." else 0.0) + (0.1 if actual != "Actual behavior is not explicitly stated." else 0.0) + min(category_score * 0.08, 0.3))
    return IssueUnderstanding(
        category=category,
        problem=problem,
        expected_behavior=expected,
        actual_behavior=actual,
        acceptance_criteria=acceptance,
        search_terms=terms,
        confidence=confidence,
    )


def _normalized_text(issue: EngineeringIssue) -> str:
    return " ".join(part for part in (issue.title, issue.body or "", " ".join(issue.labels)) if part).strip()


def _classify(text: str) -> tuple[str, int]:
    lowered = text.lower()
    scores = {
        category: sum(1 for keyword in keywords if keyword in lowered)
        for category, keywords in _CATEGORY_KEYWORDS.items()
    }
    category = max(scores, key=lambda item: (scores[item], -ISSUE_CATEGORIES.index(item)))
    if scores[category] == 0:
        return ("Business Logic", 1)
    return (category, scores[category])


def _extract_after_label(text: str, labels: tuple[str, ...], *, fallback: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        lowered = sentence.lower()
        if any(label in lowered for label in labels):
            return sentence.strip()
    return fallback


def _acceptance_criteria(issue: EngineeringIssue, category: str, expected: str, actual: str) -> tuple[str, ...]:
    criteria = [
        f"Fix the reported {category} issue in application code rather than unrelated files.",
        expected,
    ]
    if actual != "Actual behavior is not explicitly stated.":
        criteria.append(f"Prevent recurrence of: {actual}")
    if category != "Documentation":
        criteria.append("Do not modify README or documentation files unless they are directly required for the fix.")
    title_terms = " ".join(re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", issue.title or ""))[:160]
    if title_terms:
        criteria.append(f"Address the behavior described in the title terms: {title_terms}")
    return tuple(dict.fromkeys(item for item in criteria if item))


def _search_terms(issue: EngineeringIssue, category: str) -> tuple[str, ...]:
    raw = f"{issue.title} {issue.body or ''} {' '.join(issue.labels)} {category}"
    words = [term.lower() for term in re.findall(r"[A-Za-z][A-Za-z0-9_/-]{2,}", raw)]
    seeded = list(_CATEGORY_KEYWORDS.get(category, ()))
    terms = list(dict.fromkeys([*seeded, *(term for term in words if term not in _STOP_WORDS)]))
    return tuple(terms[:24])
