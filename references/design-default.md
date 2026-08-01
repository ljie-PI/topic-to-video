---
version: alpha
name: Frag Note Design System
description: A calm, light-first desktop interface for fragmented note capture, retrieval, and organization. The system pairs a warm off-white canvas with a restrained lavender accent, warm-neutral text, quiet surfaces, and minimal elevation.
reference: https://raw.githubusercontent.com/VoltAgent/awesome-design-md/refs/heads/main/design-md/claude/DESIGN.md

colors:
  primary: "#6F5BD3"
  primary-hover: "#604CC3"
  primary-active: "#513EAD"
  primary-soft: "#EEEAFE"
  primary-soft-strong: "#DED7F7"
  primary-ink: "#49399B"
  primary-disabled: "#D7D1E4"
  on-primary: "#FFFFFF"
  canvas: "#FAF9F5"
  surface-soft: "#F6F3EE"
  surface-card: "#F0ECE6"
  surface-raised: "#FFFEFB"
  surface-selected: "#EEEAFE"
  surface-hover: "#F5F1FB"
  sidebar: "#F3F0EA"
  surface-dark: "#211F26"
  surface-dark-elevated: "#2C2932"
  surface-dark-soft: "#37333E"
  overlay: "#1E1B24"
  ink: "#1F1D24"
  body-strong: "#333039"
  body: "#4D4954"
  muted: "#716C79"
  muted-soft: "#8A8491"
  on-dark: "#FAF9F5"
  on-dark-soft: "#B9B4C0"
  hairline: "#E3DED8"
  hairline-strong: "#D4CEC7"
  focus-ring: "#7965DD"
  info: "#3D6FA8"
  info-soft: "#EAF2FB"
  success: "#397352"
  success-soft: "#EAF5ED"
  warning: "#916019"
  warning-soft: "#FBF1DC"
  error: "#AD414A"
  error-soft: "#FBEAEC"

typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 32px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.5px
  heading-lg:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 24px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: -0.25px
  heading-md:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: -0.1px
  heading-sm:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0
  body-compact:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.35
    letterSpacing: 0
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0
  button:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1
    letterSpacing: 0
  code:
    fontFamily: "ui-monospace, SFMono-Regular, Consolas, Liberation Mono, monospace"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0

rounded:
  xs: 4px
  sm: 6px
  control: 8px
  card: 12px
  feature: 16px
  pill: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px

components:
  app-shell:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
  sidebar:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.body}"
    borderColor: "{colors.hairline}"
  navigation-item-active:
    backgroundColor: "{colors.surface-selected}"
    textColor: "{colors.primary-ink}"
    rounded: "{rounded.control}"
  capture-composer:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    borderColor: "{colors.hairline}"
    rounded: "{rounded.feature}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.control}"
    height: 40px
  button-secondary:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.body-strong}"
    borderColor: "{colors.hairline-strong}"
    rounded: "{rounded.control}"
    height: 40px
  text-input:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    borderColor: "{colors.hairline-strong}"
    rounded: "{rounded.control}"
    height: 40px
  content-card:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.body}"
    borderColor: "{colors.hairline}"
    rounded: "{rounded.card}"
  badge-accent:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-ink}"
    rounded: "{rounded.pill}"
  notice-error:
    backgroundColor: "{colors.error-soft}"
    textColor: "{colors.error}"
    rounded: "{rounded.control}"
---

# Frag Note Design System

> **Topic-to-video adapter.** This complete Frag Note design system is the default visual reference when no theme is specified. For video authoring, `references/composition-rules.md` remains the binding authority for narration timing, layout, media, subtitles, and QA.

## Overview

Frag Note is a quiet workspace for capturing incomplete thoughts and returning
to them later. The interface should reduce visual competition with the user's
writing. It uses a warm off-white canvas, a single lavender brand accent, and a
unified warm-neutral scale.

The light canvas is inspired by Claude's restrained cream background, but the
system is adapted for a desktop product rather than a marketing site. Anthropic
branding, coral accents, licensed typefaces, and marketing-specific components
are not part of this system.

### Design read

- **Mode:** Redesign-preserve
- **Audience:** People capturing and organizing personal notes
- **Language:** Calm, focused, humane, and lightly editorial
- **Design variance:** 4/10
- **Motion intensity:** 3/10
- **Visual density:** 5/10

### Core principles

1. **The note is the strongest visual element.** Product chrome remains quiet.
2. **One accent family.** Lavender communicates action, focus, and selection.
3. **Warm canvas, clear surfaces.** Use `canvas` as the default floor and
   surface tokens for hierarchy. Do not decorate the background with bokeh,
   mesh gradients, or unrelated accent colors.
4. **Color has a job.** Green, blue, amber, and red are reserved for semantic
   feedback, never decoration.
5. **Depth is mostly color.** Prefer surface shifts and hairlines. Use shadows
   only for floating or transient UI.
6. **Accessibility is a token constraint.** Approved text and control pairings
   must meet WCAG AA.

## Color system

All product code should consume semantic tokens. Do not use raw Tailwind color
names in component contracts.

### Brand and interaction

| Token | Value | Meaning and approved use |
|---|---:|---|
| `primary` | `#6F5BD3` | Primary button fill, active controls, key links, and brand mark. White text passes WCAG AA at 5.11:1. |
| `primary-hover` | `#604CC3` | Pointer hover for primary controls. |
| `primary-active` | `#513EAD` | Pressed state for primary controls. |
| `primary-soft` | `#EEEAFE` | Selected navigation, accent badges, and low-emphasis lavender fills. |
| `primary-soft-strong` | `#DED7F7` | Stronger selected or count background when `primary-soft` is too subtle. |
| `primary-ink` | `#49399B` | Text and icons on pale lavender surfaces. |
| `primary-disabled` | `#D7D1E4` | Disabled primary control fill. Do not use for active content. |
| `on-primary` | `#FFFFFF` | Text and icons on `primary`, `primary-hover`, and `primary-active`. |

`primary` is intentionally deeper than the surrounding lavender surfaces.
Making the button fill as pale as `primary-soft` would fail contrast with white
labels. The overall impression remains light purple because pale lavender is
used for selection and focus context, while the deeper value is limited to
small interactive areas.

### Surfaces

| Token | Value | Meaning and approved use |
|---|---:|---|
| `canvas` | `#FAF9F5` | Default app window, page floor, capture background, and empty breathing space. |
| `surface-soft` | `#F6F3EE` | Subtle grouped region or read-only inset. |
| `surface-card` | `#F0ECE6` | Tonal card or emphasized grouping without elevation. |
| `surface-raised` | `#FFFEFB` | Inputs, capture composer, content cards, menus, and dialogs above the canvas. |
| `surface-selected` | `#EEEAFE` | Selected navigation and selected list rows. Same value as `primary-soft`, with a surface-specific role. |
| `surface-hover` | `#F5F1FB` | Hover fill for neutral rows and icon controls. |
| `sidebar` | `#F3F0EA` | Persistent app sidebar. It should be distinct from the canvas without becoming a separate theme. |
| `surface-dark` | `#211F26` | Rare dark surface for overlays or media tools. Not a page-section background. |
| `surface-dark-elevated` | `#2C2932` | Elevated control inside a dark surface. |
| `surface-dark-soft` | `#37333E` | Hover or nested region inside a dark surface. |
| `overlay` | `#1E1B24` | Modal or screenshot scrim at 72% opacity. Never use as opaque body text. |

The normal desktop experience is light-first. Dark tokens exist for screenshot
selection, modal scrims, and other media contexts, not for alternating page
themes.

### Text

| Token | Value | Meaning and approved use |
|---|---:|---|
| `ink` | `#1F1D24` | Headings, note content, entered form values, and high-priority labels. |
| `body-strong` | `#333039` | Emphasized body copy and secondary headings. |
| `body` | `#4D4954` | Default interface and descriptive text. |
| `muted` | `#716C79` | Metadata, helper text, inactive navigation, and timestamps. It passes AA on `canvas` at 4.83:1. |
| `muted-soft` | `#8A8491` | Disabled labels, decorative icons, and nonessential captions only. Do not use for normal body text. |
| `on-dark` | `#FAF9F5` | Primary text and icons on dark surfaces. |
| `on-dark-soft` | `#B9B4C0` | Secondary text on dark surfaces. |

### Borders and focus

| Token | Value | Meaning and approved use |
|---|---:|---|
| `hairline` | `#E3DED8` | Default divider and low-emphasis border. |
| `hairline-strong` | `#D4CEC7` | Input borders and boundaries that need clearer definition. |
| `focus-ring` | `#7965DD` | Keyboard focus ring and focused input edge. Use a 2px ring plus 2px canvas offset. |

### Semantic feedback

| Token | Value | Meaning and approved use |
|---|---:|---|
| `info` | `#3D6FA8` | Informational icon, text, progress, or strong fill. |
| `info-soft` | `#EAF2FB` | Informational notice background. |
| `success` | `#397352` | Confirmed, synced, ready, or successful action. |
| `success-soft` | `#EAF5ED` | Success notice and status background. |
| `warning` | `#916019` | Delayed, partial, queued, or caution state. |
| `warning-soft` | `#FBF1DC` | Warning notice and status background. |
| `error` | `#AD414A` | Failure, destructive action, validation error, or recording state. |
| `error-soft` | `#FBEAEC` | Error notice and status background. |

Use the strong semantic token as text or icon on its matching soft token. The
approved pairs meet WCAG AA for normal text. Strong semantic tokens may also be
used as button fills with `on-primary`.

### Topic-to-video color semantics

- Keep `canvas` as the continuous light scene floor; use `surface-soft` / `surface-card` for restrained information grouping, not decorative card stacking.
- `primary` / `primary-soft` identify the current conclusion, key number, active process step, or a short source marker. They are not a second body-text color or a full-frame wash.
- For `chart` / `data_table`, use `primary` for the focal series and warm-neutral tones for supporting series; `info`, `success`, `warning`, and `error` only denote their real semantic state.
- For `timeline`, `process_flow`, `list`, and `metric_strip`, use hairlines and warm-neutral labels by default; reserve lavender for the current or emphasized item.

## Typography

Frag Note is a product interface, not a Claude marketing-page replica. It uses
one system sans family for headings and UI to remain native, compact, and
legible across Windows and macOS. Monospace is limited to identifiers, logs,
and technical metadata.

| Token | Size / weight | Use |
|---|---|---|
| `display` | 32px / 600 | Empty-state or onboarding headline, used rarely |
| `heading-lg` | 24px / 600 | Page title |
| `heading-md` | 20px / 600 | Major panel heading |
| `heading-sm` | 16px / 600 | Card and section heading |
| `body` | 14px / 400 | Default product copy and note preview |
| `body-compact` | 13px / 400 | Dense rows and secondary panels |
| `label` | 13px / 500 | Form labels, navigation, tabs, and metadata emphasis |
| `caption` | 12px / 400 | Timestamps and low-priority metadata |
| `button` | 14px / 600 | Standard button labels |
| `code` | 13px / 400 | IDs, technical values, and logs |

### Typography rules

- Use sentence case for headings, buttons, navigation, and badges.
- Do not use uppercase tracking labels as routine section decoration.
- Keep note content at `body` size or larger and use at least 1.55 line height.
- Use weight 600 for hierarchy. Avoid 700+ except for the product wordmark.
- Do not use a serif display face unless a future brand change explicitly adds
  one.

### Topic-to-video font binding

The source system-font stack above describes the desktop product. In a rendered topic-to-video composition, it is overridden by the locally staged fonts:

- Use `NotoSansSC` for Chinese titles, body copy, screen text, and subtitles; use `IBMPlexMono` only for code, numbers, identifiers, and compact source metadata.
- Load only the local WOFF2 assets produced by `scripts/fonts-download.sh <target_dir> default`; do not rely on system font matching or a serif / Song-style CJK fallback.
- Keep the source hierarchy intent: 600 for titles, 400/500 for body text, and no heavy display type.

## Spacing and layout

The spacing system uses a 4px base:

| Token | Value | Typical use |
|---|---:|---|
| `xxs` | 4px | Icon-label micro gap |
| `xs` | 8px | Compact control gap |
| `sm` | 12px | Form field and row gap |
| `md` | 16px | Standard card padding |
| `lg` | 24px | Panel padding and section gap |
| `xl` | 32px | Page gutter |
| `xxl` | 48px | Empty-state and onboarding spacing |

### App shell

- Window background: `canvas`
- Sidebar width: 240px default, 200px minimum, 400px maximum
- Sidebar background: `sidebar`
- Main content maximum readable width: 896px for lists and detail views
- Main content gutter: 32px desktop, 20px compact window
- Persistent title bar: 32px
- Avoid gradients on the app shell and capture view

### Density

The product uses medium density. Navigation and standard controls are 40px
tall. Dense list rows may be 36px when every row remains keyboard accessible.
Primary touch targets should be at least 40px and preferably 44px on touch
devices.

### Topic-to-video frame semantics

The desktop shell measurements below are reference proportions, not literal video layout. In video, use the 4px spacing rhythm with `references/composition-rules.md` for scene padding, subtitle-safe area, and orientation-specific layout. Preserve intentional warm-white breathing room, but do not use empty space to evade the composition coverage requirements.

## Shapes

| Token | Value | Use |
|---|---:|---|
| `xs` | 4px | Tiny progress or inset element |
| `sm` | 6px | Compact badge or menu item |
| `control` | 8px | Buttons, inputs, tabs, and navigation items |
| `card` | 12px | Standard cards, menus, dialogs, and app window |
| `feature` | 16px | Capture composer and prominent empty state |
| `pill` | 9999px | Badges, status chips, and circular icon buttons only |

Do not mix arbitrary radius values. Controls use 8px, standard containers use
12px, and the capture composer uses 16px.

## Elevation

| Level | Treatment | Use |
|---|---|---|
| Floor | `canvas`, no border or shadow | App window and page |
| Grouped | Tonal surface, optional `hairline` | Sidebar and read-only groups |
| Raised | `surface-raised` plus `hairline` | Cards, inputs, capture composer |
| Floating | `surface-raised`, `hairline`, tinted shadow | Menus, dialogs, and toasts |
| Overlay | `overlay` at 72% | Modal and screenshot scrim |

Approved shadows:

```css
--shadow-raised: 0 1px 2px rgb(31 29 36 / 0.05);
--shadow-floating:
  0 12px 32px rgb(64 52 86 / 0.12),
  0 2px 8px rgb(64 52 86 / 0.08);
```

Do not add outer glows. Focus uses a ring, not a glow.

### Topic-to-video surface semantics

Translate the component recipes into visual hierarchy: `surface-raised` is for a meaningful evidence card or short callout, `surface-soft` / `surface-card` are for grouped context, and `hairline` separates information without adding decoration. Do not reproduce product navigation, form controls, or hover states literally unless the scene depicts the product UI itself.

## Components

### App shell and sidebar

- The app shell uses `canvas`.
- The sidebar uses `sidebar` with a `hairline` right border.
- Inactive navigation uses `body` or `muted`.
- Hovered navigation uses `surface-hover` and `body-strong`.
- Selected navigation uses `surface-selected` and `primary-ink`.
- Count badges use `surface-card` for neutral counts and
  `primary-soft-strong` with `primary-ink` for attention counts.
- The resize handle is transparent by default, `primary-soft-strong` on hover,
  and `focus-ring` when keyboard focused.

### Capture composer

- Use `surface-raised`, a `hairline` border, 16px radius, and
  `shadow-raised`.
- Do not use a translucent white card over a multicolor background.
- The surrounding capture view stays `canvas`.
- Attachments use `surface-soft`; selected attachments use `primary-soft`.
- The submit action uses the primary button recipe.

### Buttons

**Primary**

- Default: `primary` with `on-primary`
- Hover: `primary-hover` with `on-primary`
- Pressed: `primary-active` with `on-primary`
- Focus: 2px `focus-ring`, 2px `canvas` offset
- Disabled: `primary-disabled` with `muted`, no shadow

**Secondary**

- Default: `surface-raised`, `body-strong`, 1px `hairline-strong`
- Hover: `surface-hover`, `ink`, 1px `primary-soft-strong`
- Pressed: `primary-soft`, `primary-ink`
- Focus: same focus recipe as primary

**Ghost and icon**

- Default: transparent with `muted`
- Hover: `surface-hover` with `primary-ink`
- Active: `primary-soft` with `primary-ink`

**Destructive**

- Use `error` with white text only when the action is immediately destructive.
- Use a secondary button with `error` text when confirmation follows.

All buttons keep labels on one line and provide visible focus.

### Inputs

- Background: `surface-raised`
- Text: `ink`
- Placeholder: `muted`
- Border: `hairline-strong`
- Hover border: `primary-soft-strong`
- Focus border and ring: `focus-ring`
- Error border and helper text: `error`
- Disabled background: `surface-soft`
- Labels sit above inputs. Placeholder text never replaces a label.

### Cards and rows

- Default content card: `surface-raised`, `hairline`, 12px radius
- Tonal group: `surface-soft` or `surface-card`, no shadow
- Hoverable row: change only to `surface-hover`; do not lift every row
- Selected row: `surface-selected` with a visible `primary` indicator or
  `primary-ink` icon
- Use spacing instead of cards when content already belongs to one page section

### Status badges

| State | Background | Foreground |
|---|---|---|
| Local only | `surface-card` | `body` |
| Queued or partial | `warning-soft` | `warning` |
| Syncing or processing | `info-soft` | `info` |
| Ready or complete | `success-soft` | `success` |
| Failed | `error-soft` | `error` |
| Selected or generated | `primary-soft` | `primary-ink` |

Status must always include text. Do not rely on color or a decorative dot alone.

### Notices and toasts

- Informational: `info-soft` / `info`
- Success: `success-soft` / `success`
- Warning: `warning-soft` / `warning`
- Error: `error-soft` / `error`
- Toast containers use `surface-raised`, `hairline`, and `shadow-floating`
- Use toasts for transient results. Use inline notices for errors the user must
  act on.

### Dark and overlay contexts

Dark tokens are limited to screenshot selection, media preview, and modal
scrims. Use `on-dark` for primary text and `on-dark-soft` for secondary text.
Do not insert isolated dark cards into normal light content merely for visual
variety.

### Topic-to-video visual roles and icons

- `big_number`, key conclusions, and the current process node may use `primary` or `primary-soft + primary-ink`.
- `callout`, `quote`, `definition`, and source labels stay compact and use raised / soft surfaces only when they clarify hierarchy.
- Use restrained line icons whose color follows `body`, `primary-ink`, or a true semantic state; do not use emoji, 3D icons, sticker packs, or decorative logo walls.

## Interaction and motion

- Default color transition: 120ms ease-out
- Enter or exit transition: 160-200ms ease-out
- Button pressed feedback: translate down 1px or scale to 0.98
- Animate only opacity and transforms
- Do not animate background blobs, gradients, or decorative particles
- Respect `prefers-reduced-motion`; remove transforms and use instant state
  changes when requested
- Focus visibility is mandatory and must not depend on animation

### Topic-to-video motion semantics

- Treat the 160–200ms product transition guidance as a visual character cue, not as a fixed video duration. Video timing must follow R18 and R19.
- Reveal narration-bearing text by its transcript sentence or semantic beat; do not front-load a scene with a uniform stagger or animate non-semantic background activity.
- Prefer opacity and transform for short entrances, but keep the animation deterministic and seek-safe. Do not use animated gradients, blobs, particles, outer glows, or idle decorative drift.

## Responsive behavior

Frag Note is desktop-first but must remain usable in compact windows.

| Width | Behavior |
|---|---|
| Under 720px | Collapse sidebar to an overlay or icon rail; use 20px content gutters; stack action rows |
| 720-1024px | Keep the sidebar near its minimum width; use 24px content gutters |
| Over 1024px | Use the saved sidebar width and 32px content gutters |

- Capture composer width is fluid and capped around 896px.
- Buttons may wrap as a group, but individual button labels never wrap.
- Form grids collapse to one column below 720px.
- Toasts keep 16px viewport clearance and never exceed the viewport width.

## Accessibility

### Approved contrast pairs

| Foreground / background | Contrast | Use |
|---|---:|---|
| `on-primary` / `primary` | 5.11:1 | Primary buttons |
| `primary-ink` / `primary-soft` | 7.62:1 | Selected navigation and badges |
| `ink` / `canvas` | 15.83:1 | Headings and note content |
| `body` / `canvas` | 8.32:1 | Body text |
| `muted` / `canvas` | 4.83:1 | Metadata and helper text |
| `on-dark` / `surface-dark` | 15.47:1 | Overlay primary text |
| `on-dark-soft` / `surface-dark` | 8.03:1 | Overlay secondary text |
| `info` / `info-soft` | 4.60:1 | Informational notice |
| `success` / `success-soft` | 5.01:1 | Success notice |
| `warning` / `warning-soft` | 4.81:1 | Warning notice |
| `error` / `error-soft` | 4.98:1 | Error notice |

`muted-soft` and disabled pairings are not approved for body text. Disabled
controls still require readable labels, but they do not need to meet the same
contrast requirement as enabled controls under WCAG.

### Additional requirements

- Never communicate status by color alone.
- Every interactive element has a keyboard focus state.
- Body and form text target at least 4.5:1 contrast.
- Icon-only controls require accessible names.
- Error messages appear next to the affected control and use `role="alert"` when
  newly introduced.
- Maintain a logical heading order and visible labels.

## Migration map from the current UI

| Current pattern | Design token replacement |
|---|---|
| `capture-bg` bokeh and green/yellow/blue gradient | `canvas` |
| `from-purple-50 via-white to-slate-50` | `canvas` |
| `bg-slate-50` | `canvas` |
| `bg-white` or `bg-white/70` cards | `surface-raised` |
| `bg-stone-100` sidebar | `sidebar` |
| `bg-stone-200` hover | `surface-hover` |
| `border-slate-200`, `border-stone-200` | `hairline` |
| `border-slate-300` | `hairline-strong` |
| `bg-purple-600` | `primary` |
| `hover:bg-purple-700` | `primary-hover` |
| `bg-purple-50`, `bg-purple-100` | `primary-soft` |
| `bg-purple-200` | `primary-soft-strong` |
| `text-purple-700`, `text-purple-800` | `primary-ink` |
| `focus:ring-purple-500` | `focus-ring` |
| `text-slate-900`, `text-stone-900` | `ink` |
| `text-slate-700`, `text-stone-700` | `body-strong` |
| `text-slate-600`, `text-stone-600` | `body` |
| `text-slate-500`, `text-stone-500` | `muted` |
| `text-slate-400`, `text-stone-400` | `muted-soft` |
| Blue status utilities | `info` and `info-soft` |
| Green status utilities | `success` and `success-soft` |
| Yellow or amber status utilities | `warning` and `warning-soft` |
| Red status utilities | `error` and `error-soft` |

This mapping is guidance for a future implementation change. The design document
does not require all surfaces to become CSS variables immediately, but migration
should centralize tokens before changing components one by one.

## Do and do not

### Do

- Use `canvas` as the continuous light background.
- Reserve lavender for action, selection, focus, and generated-note context.
- Use warm-neutral surfaces to group related information.
- Keep note content darker than surrounding interface labels.
- Prefer hairlines and tonal changes to large shadows.
- Use semantic colors only when the state has semantic meaning.

### Do not

- Do not restore a multicolor bokeh or mesh background.
- Do not mix slate and stone neutral scales in the same view.
- Do not make every card translucent or glassy.
- Do not use pale lavender with white text.
- Do not use purple gradients or outer glows.
- Do not add dark sections to a light page for decoration.
- Do not use status colors for unrelated icons or category decoration.
- Do not rely on rounded cards when spacing or a divider is sufficient.

## Implementation guidance

1. Define the `colors` section as CSS custom properties in the desktop root.
2. Replace the app shell and `capture-bg` first so every view inherits the new
   canvas.
3. Migrate shared controls and shared status components before page-specific
   routes.
4. Replace direct Tailwind palette utilities with semantic classes or component
   recipes.
5. Test normal, hover, pressed, focus, disabled, loading, empty, success, and
   error states.
6. Validate the desktop app at compact and wide window sizes.

## Reference and attribution

This system was informed by the structure and warm-canvas analysis in the
community-maintained Claude design reference:

<https://raw.githubusercontent.com/VoltAgent/awesome-design-md/refs/heads/main/design-md/claude/DESIGN.md>

Frag Note retains only the relevant high-level principles: a warm light canvas,
restrained surface hierarchy, sparse accent use, and color-led elevation. The
palette, semantic roles, typography, product components, and implementation
mapping are specific to Frag Note.
