# Retry Configuration

Retry configuration provides default values for future runtime implementations. It is declarative and must not contain secrets or executable behavior.

## Files

- [retry-policy.template.yaml](retry-policy.template.yaml): default retry settings and thresholds.

## Configuration Ownership

Global project settings live in [../../configuration/settings.yaml](../../configuration/settings.yaml). This directory owns retry-specific policy templates and should be referenced from global settings rather than duplicating unrelated project configuration.
