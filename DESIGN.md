# Design

## System

Cloud CUA is a local product dashboard, not a marketing surface. Use one system font stack, restrained color, predictable layouts, and dense but readable status information.

## Palette

- Background: `#eef3f8`
- Surface: `#ffffff`
- Surface subtle: `#f7fafc`
- Ink: `#071326`
- Muted: `#53657a`
- Border: `#d8e1ec`
- Primary: `#2457d6`
- Primary dark: `#173b96`
- Success: `#12805c`
- Warning: `#b7791f`
- Danger: `#b42318`
- Info: `#2b6cb0`

## Typography

Use `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. Product UI uses fixed sizes, not viewport-scaled type.

- Page title: 28-32px, 750 weight
- Section title: 18-20px, 700 weight
- Body: 14-16px, 400-500 weight
- Labels: 12px, 700 weight
- Monospace logs: `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`

## Layout

Use a top bar plus a two-column dashboard on desktop:

- Main column: run status, approvals, proof, mode
- Side column: activity timeline, context, report

On narrow screens, collapse to one column. Use a 4px spacing base with practical steps: 4, 8, 12, 16, 20, 24, 32, 40.

## Components

- Buttons use one radius, one border vocabulary, and visible focus rings.
- Status chips always include text, not only color.
- Cards are for distinct panels only; avoid nested cards.
- Activity entries use source labels: Codex, H CUA, User, Verifier, System.
- Approval prompts are prominent and actionable.
- Login gate is a blocking modal with blurred/dimmed backdrop.

## States

Every async action should show disabled/loading feedback where possible. Empty states should tell the user what is expected next. Failed or skipped verifiers must remain visible and should not look neutral.
