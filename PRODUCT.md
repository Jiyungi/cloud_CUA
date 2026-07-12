# Product

## Register

product

## Users

Cloud CUA is for developers who have finished building an app in a local repo and want to deploy it to AWS or GCP without becoming cloud-console experts. They are already working in an IDE or with Codex, and they need a supervised deployment run that is fast enough for hackathon/demo use but honest about account, permission, cost, and reliability risks.

## Product Purpose

Cloud CUA lets Codex start a local deployment run through MCP, lets H Company CUA operate the logged-in cloud console, and uses independent verifiers to prove what happened. Success means the user can see the current run, approve risky actions, switch between Vibe/Teach/Expert modes, verify cloud identity/resources/live URL, and get a report without trusting the CUA's word alone.

## Brand Personality

Calm, technical, accountable.

## Anti-references

This should not look like a generic SaaS landing page, a form-heavy admin settings panel, or a flashy AI agent demo that hides risk. Avoid giant marketing heroes, decorative gradients, fake success states, excessive inputs, and visual claims that imply cloud deployment is solved when the verifier has not passed.

## Design Principles

1. Supervision over configuration: the dashboard should show run state, evidence, approvals, and intervention controls before raw setup fields.
2. Actor/proof separation: H CUA actions, Codex plans, user approvals, and verifier results must be visually distinct.
3. Fail closed: missing tools, failed logins, unverified resources, and blocked CUA steps must be obvious and non-successful.
4. Progressive detail: normal users see the run and proof first; developer/debug controls stay available but secondary.
5. Teach without slowing control: Teach Mode explains decisions, while fast commands like pause and verifier remain direct.

## Accessibility & Inclusion

Target WCAG AA contrast for text and controls. Keep keyboard focus visible, touch targets at least 44px, and motion limited to short state transitions with reduced-motion support. Do not rely on color alone for run status.
