# AI Interview Style Redesign Design

## Context

The current construction maintenance system is a Flask, Jinja2, SQLite application with server-rendered pages. The UI already has a dashboard, project ledger, personnel directory, qualifications management, exports, batch import, tables, modals, badges, charts, and a light/dark theme toggle.

The reference project is `RylinXX/ai-interview-boss-mail`. Its frontend uses a restrained enterprise workbench style: warm ivory backgrounds, white elevated surfaces, deep navy text, gold primary actions, compact 8px radii, a fixed light sidebar, sticky translucent header, dense KPI cards, and clear table/form hierarchy.

## Goal

Apply the reference project's visual language to the current system while preserving the existing Flask/Jinja architecture and business behavior.

## Scope

In scope:

- Redesign the global shell in `construction_maintenance/templates/base.html`.
- Redesign global styling in `construction_maintenance/static/app.css`.
- Keep the existing page routes, forms, tables, charts, and modal behavior.
- Update dashboard visual hierarchy to feel like a business workbench.
- Harmonize cards, buttons, tables, tags, forms, side navigation, header, empty states, and dark mode with the reference style.
- Keep responsive behavior for desktop, tablet, and mobile.

Out of scope:

- No migration to React.
- No Ant Design dependency.
- No backend route, database, or service-layer changes unless needed to preserve rendering.
- No redesign of business workflows or data model.
- No new authentication flow.

## Recommended Approach

Use a style-transfer implementation rather than a framework migration.

The current CSS and templates already expose reusable primitives such as `.app-container`, `.sidebar`, `.main-header`, `.panel-card`, `.metric-card`, `.premium-table`, `.btn`, `.badge`, `.modal`, `.form-input`, and `.form-select`. These should be restyled to match the reference workbench instead of replacing the application structure.

## Visual System

Primary palette:

- Page background: `#F7F4EE`
- Surface: `#FFFDF8`
- Elevated surface: `#FFFFFF`
- Muted surface: `#FBF7EF`
- Subtle surface: `#F3ECE0`
- Inset surface: `#EFE6D8`
- Primary text / brand navy: `#142136`
- Secondary text: `#667085`
- Tertiary text: `#9B8D79`
- Accent gold: `#B88A3B`
- Accent blue-grey: `#57708F`
- Border: `#E5DDCF`

Dark mode should map to the reference's slate surfaces and warm gold accent:

- Background: `#0B1020`
- Surface: `#111827`
- Elevated surface: `#162033`
- Border: `#263244`
- Primary text: `#E5E7EB`
- Secondary text: `#94A3B8`
- Gold accent: `#D4A85C`

Radii should be tightened to 6px or 8px for controls, cards, and navigation. Shadows should be subtle by default and only increase on hover for interactive surfaces.

## Layout

The application shell should shift from a dark gradient sidebar to a fixed light workbench sidebar:

- Sidebar fixed at the left on desktop, light surface background, 1px warm border.
- Brand area with a small mark and two-line text: product name plus uppercase subtitle.
- Navigation items with muted text, 8px radius, gold selected state, and soft hover state.
- Sidebar footer/status block with compact system status, similar to the reference project's sidebar status card.

The header should become a sticky translucent workbench header:

- 64px height.
- Warm translucent surface with backdrop blur.
- Left side shows current page title and a short subtitle instead of only breadcrumbs.
- Right side keeps theme toggle and user identity in a compact trigger.

Content should use a constrained center width on wide screens and tighter page margins:

- Desktop content margin around 28px 32px 40px.
- Mobile content margin around 18px 14px 28px.
- Avoid nested decorative cards; use cards only for panels, repeated items, and modals.

## Dashboard

The dashboard should be the strongest first impression:

- Replace the dark blue welcome banner with a warm `dashboard-hero` panel.
- Left side: dashboard title, concise operational subtitle.
- Right side: compact three-cell snapshot panel for core operational numbers.
- KPI cards use reference-style `metric-card` structure with icon chip, label, large number, and muted baseline copy.
- Chart panels retain Chart.js but inherit warm surfaces, border color, and muted axis/legend colors.

No backend metrics need to change. Existing `metrics` values should be reused.

## Components

Cards:

- Use warm surface, 1px warm border, 8px radius, subtle shadow.
- Hover should adjust border/shadow lightly, not lift aggressively.

Buttons:

- Primary actions use gold fill.
- Secondary actions use surface background and border.
- Keep icon/text buttons where the current app already uses emoji, but tighten spacing and size.

Tables:

- Header background uses muted warm surface.
- Header text is uppercase, small, and semibold.
- Rows use warm hover background.
- Keep horizontal overflow behavior for dense data.

Forms:

- Inputs/selects use warm surface, 6px radius, border color from the design tokens.
- Focus ring uses translucent gold.

Badges:

- Keep status meaning but tune background and foreground colors for the warm workbench palette.
- Radius remains compact, not pill-heavy where space is tight.

Modals:

- Keep current modal JavaScript behavior.
- Restyle overlay, modal content, header, body spacing, and close button to match warm elevated surfaces.

## Dark Mode

Keep the current theme toggle behavior, but align variable names and overrides with the reference palette.

The current implementation uses `:root.dark-theme`; this can remain to avoid template changes. CSS variables should be updated so dark mode reads as a dark slate enterprise workbench with gold accents instead of a blue tech theme.

## Testing And Verification

Verification should cover:

- `pytest` for backend route and template safety.
- Run the Flask app locally.
- Browser verification for dashboard, projects, people, qualifications, and at least one modal.
- Check light and dark mode.
- Check responsive desktop and mobile widths.
- Confirm Chart.js canvas renders nonblank where metric data exists, and empty states remain readable where data is absent.

## Risks

- Some templates contain inline styles. The implementation should override or migrate only the inline styles that visibly conflict with the new design.
- Several pages define local `<style>` blocks. Global CSS should cover shared primitives first; local styles should be touched only when required for consistency.
- The project directory is not currently a Git repository, so design and implementation changes cannot be committed from this workspace.

