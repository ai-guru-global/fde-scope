# FDE Scope · Workbench design system

One token system for every shipped surface. The ramp is **IBM-style enterprise
workbench**: a cool near-white light theme and a true dark theme, one saturated
engineering blue, hairline borders, square-ish corners, a shadow only where a
layer genuinely floats, and uppercase reserved for mono micro-labels.

**Source of truth is `fde_scope/web/layout.py` → `THEME_CSS`.** Everything else
either imports it or mirrors it by hand. When the two disagree, `layout.py` wins.

The ramp is layered so a surface can take exactly as much as it renders, without
forking it: `THEME_CSS` (tokens + text/control primitives + the `.dot` mark
vocabulary + `.hint`) ⊂ `COMPONENT_CSS` (adds the shared blocks: `.stats`/`.stat`,
`.sec-head`) ⊂ `BASE_CSS` (console chrome) ⊂ `NOTICE_CSS` (the centred
single-sheet layout used by the share and acknowledgement pages). A generated
portal composes `THEME_CSS` plus its own page chrome; a page with nothing to
invent takes `NOTICE_CSS` whole.

| Surface | File | Page type | Token relationship |
|---|---|---|---|
| Web console + prose pages | `fde_scope/web/layout.py`, `app.py`, `sop.py`, `course.py`, `glossary.py`, `certification.py`, `showcase.py`, `docs_reader.py`, `resources.py`, `share.py` | app / content | defines the ramp |
| Skills handbook portal | `docs/skills-catalog/site/{,en/}index.html` | content | **generated** by `scripts/build_catalog_site.py`, imports `THEME_CSS` |
| GitHub resources portal | `docs/github-resources/site/{,en/}index.html` | content | **generated** by `scripts/build_resources_site.py`, imports `THEME_CSS` |
| GTM board | `GTM/index.bilingual.html` → `GTM/i18n_split.py` → `GTM/{,en/}index.html` | marketing | mirrors the ramp; **light-only** |
| Android shell | `android/res/values[-night]/colors.xml` | native chrome | sRGB mirror of the ramp |
| Android WebView demo | `android/assets/demo/index.html` | content | inlines the ramp (must ship offline) |

Generated files are build artifacts — never hand-edit them; rebuild with
`make build-site` / `make build-resources-site`, or re-run `GTM/i18n_split.py`.

Not on the ramp, by decision: `fde_scope/templates/corpus_report.html.j2` is a
self-contained dark artifact with its own hex `:root` and teal accent, designed to
be emailed or opened standalone rather than beside the console. It is not a
workbench surface and does not inherit the ramp.

## Genre & macrostructure

- Genre: **modern-minimal, enterprise-grade.** No toy or neo-brutalist chrome.
- GTM: a full-bleed live-gate board hero (lanes + T-cards + readout), then
  evidence sections. Keep this IA and all interactive logic.
- Portal: directory listing with search, zone filter, per-page cards.
- Console: `/` is a long document; `/console` is the workbench.
- Diversification is **inverted** — all surfaces share one system and differ
  only in macrostructure within their family.

## Theming

- Light is the default (`:root`, `color-scheme:light`); dark is an explicit
  `html[data-theme="dark"]` override. **Never `prefers-color-scheme`** — that is
  not the app's mechanism and would let the OS fight the in-app toggle.
  Resolution: `localStorage['fde-theme']` → `matchMedia`, inline in `<head>`.
- Console and the Android demo carry the toggle (32px ghost button, sun/moon).
  GTM and both portals are **light-only by decision**, not by omission.
- Android has no per-token dark theme in code; `values-night/colors.xml`
  supplies it and follows system night mode.

## Tokens (light, `:root`)

| Token | Value | Usage |
|---|---|---|
| `--bg` | `oklch(0.967 0.004 258)` | Page background |
| `--bg2` / `--panel` / `--layer-01` | `oklch(1 0 0)` | Cards, elevated panels |
| `--panel2` / `--layer-02` | `oklch(0.931 0.004 258)` | Hover fills, raised groups |
| `--layer-03` | `oklch(0.87 0.004 258)` | Topmost tier: tooltips, popovers |
| `--fg` | `oklch(0.21 0.006 258)` | Primary text |
| `--muted` | `oklch(0.44 0.006 258)` | Secondary text |
| `--faint` | `oklch(0.5 0.006 258)` | De-emphasis; never body copy |
| `--border` | `oklch(0.902 0.004 258)` | Hairline dividers |
| `--border-strong` | `oklch(0.62 0.006 258)` | Component boundary: fields, toasts |
| `--border-ink` | `oklch(0.52 0.006 258)` | Emphasis: hover, selected, ghost button |
| `--accent` | `oklch(0.545 0.243 262)` | Engineering blue (`#0A5EFA`) — primary action |
| `--accent-2` / `--accent-3` | `0.509 0.236 262` / `0.454 0.221 262` | Button **fill** ramp (hover, pressed) |
| `--accent-text` | `oklch(0.509 0.236 262)` | Accent **as text** |
| `--accent-ink` | `oklch(0.99 0.002 258)` | Text on a filled accent surface |
| `--accent-dim` | `oklch(0.545 0.243 262/0.1)` | Accent wash, tag background |
| `--layer-accent` / `-hover` | `0.908 0.044 260` / `0.86 0.06 260` | Selected-row fill |
| `--good` / `-dot` / `-fill` | `0.429 0.117 148` / `0.575 0.166 148` / `0.93 0.05 152` | Passed |
| `--warn` / `-dot` / `-fill` | `0.439 0.09 86` / `0.595 0.132 85` / `0.955 0.07 95` | Warning |
| `--bad` / `-dot` / `-fill` | `0.46 0.171 26` / `0.615 0.209 22` / `0.925 0.045 18` | Blocked |
| `--code` | `oklch(0.955 0.004 258)` | Code / CLI / input wells |
| `--elev` / `--elev-lg` | `0 8px 24px rgba(0,0,0,.16)` / `0 24px 64px rgba(0,0,0,.22)` | Toast / modal — the only floating layers |
| `--z-sticky` / `--z-toast` | `60` / `70` | Semantic z-scale |

## Tokens (dark, `html[data-theme="dark"]`)

`--bg` `0.2 0.004 258` · `--panel`/`--layer-01` `0.269` · `--panel2`/`--layer-02` `0.345` ·
`--layer-03` `0.439` · `--fg` `0.967` · `--muted` `0.827` · `--faint` `0.72` ·
`--border` `0.39` · `--border-strong` `0.55` · `--border-ink` `0.66` ·
`--accent` `0.736 0.136 261` (**`#78A9FF`, IBM Blue 40**) · `--accent-2` `0.828 0.086 260` ·
`--accent-3` `0.68 0.15 261` · `--accent-text` = `--accent` · `--accent-ink` `0.28 0.14 263` ·
`--accent-dim` alpha `0.14` · `--layer-accent` `0.40 0.11 262` · `--code` `0.145 0.004 258`.

Android mirror (sRGB): light `fde_bg #F2F4F7`, `fde_fg #17181B`, `fde_accent #0A5EFA`;
dark `fde_bg #151618`, `fde_panel #252628`, `fde_accent #78A9FF`, `fde_accent_ink #001D6C`.

## Measured rules

These are results, not preferences. They were each measured against real copy in
both themes; re-measure before changing one.

- **Accent-as-text uses `--accent-text`, never `--accent`.** Plain `--accent`
  clears 4.5:1 on `--bg` and `--layer-01` but fails on raised surfaces where text
  actually lands (4.28 light on `--layer-02`; 3.32 dark on `--layer-03`).
  `--accent-text` clears 4.5:1 on every neutral layer in its theme.
  `--accent-2`/`--accent-3` are the button *fill* ramp and must not be reused as text.
- **WCAG 1.4.11's 3:1 bar applies at ≥24px bold**, so plain `--accent` survives on
  the one display figure carrying it (`.kpi .v` at `--fs-num`/700) and nowhere else.
  The overview's `.stat .num` is 20px and takes `--fg`.
- **On an `--accent-dim` wash even `--accent-text` fails** (4.36:1 light on
  `--layer-02`), so a tinted label takes `--fg` and lets the wash carry the hue.
- **On a filled `--accent` surface the ink is `--accent-ink`.** White is 2.35:1 in
  dark and never correct.
- **Border ladder: `--border` → `--border-strong` → `--border-ink`.** Anything
  lighter than 0.62 L in light cannot mark a field (1.4.11 needs 3:1 on the
  component boundary).
- **A case transform may not reach copy that quotes an identifier.**
  `.stat .lab` was uppercase until measured against the real labels, which quote
  live tokens (`可执行 gate` rendered `GATE`, `4 zones` rendered `ZONES`): the
  transform invents acronyms the product never uses. Metric labels are sentence
  case, as in Carbon. Uppercase stays on surfaces whose text is a pure label —
  `.eyebrow`, `.ztag`, `.snav .grp`/`.tall`/`.sgrp`, `.sec-head .n`.
- **Selection is one quiet move off its surface plus hue** (light `--panel` 1.0 →
  `--layer-accent` 0.908; dark `--bg2` 0.269 → 0.40). Dark's hover is 0.345, so
  selection must clear that floor; 0.40 at C 0.11 is the lowest step that beats
  both hover and neutral `--layer-03`.
- **Annotation is for prose only.** A glossary/term marker belongs on explanatory
  text (hero paragraph, section note, card description), never on titles, nav,
  buttons, metric labels or phase rows — the console resolves the same problem by
  moving terms to `/glossary` instead of marking them inline.
- **The contrast floor is a measured number, not an aspiration.** A token sweep of
  every static surface in both themes (each surface served over loopback http, the
  theme written to `localStorage` *before* navigation, because each page applies it
  from an inline head script at load) resolves 19 text pairs per page with a worst
  case of **4.93:1 light / 6.39:1 dark**, and no border or lamp below **3.31:1**.
  Any token change re-measures before it ships; `--accent` on a raised layer is the
  failure mode to look for first.

## Typography

- Console: **zero external fonts.** `-apple-system,"SF Pro Text","Segoe UI",
  "PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif`;
  mono `ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace`.
- GTM / portals: Public Sans + Spline Sans Mono (self-hosted woff2) + CJK fallback.
- Scale is tokenised — **no literal font sizes on any shipped surface.** Every
  step is a token, `.logo` and `.prose h4` included (both `var(--fs-h4)`):
  `--fs-xs .75rem` · `--fs-sm .875rem` · `--fs-body .9375rem` · `--fs-h4 1rem` ·
  `--fs-h3 1.125rem` · `--fs-h2 1.25rem` · `--fs-num 1.7rem` · `--fs-display 2rem`.
- **A surface that copies a subset of the ramp completes the subset.** The GTM
  board and the Android demo inline the tokens by hand (the demo has to, offline),
  and both had picked up a partial ladder. No step may be *referenced* without
  being *declared*, and no literal may stand where the ramp already owns the size:
  the fix is to add the missing canonical step, never to invent a surface-local
  name for it — a divergent `--fs-brand` is how two surfaces silently become two
  systems. A mirror may legitimately omit a step it never uses.
- **Persuasive sizes are named extension steps, not overrides.** GTM's register
  needs a display scale the workbench has no use for, so it declares
  `--fs-base 1rem` (a marketing page is scanned at arm's length; the console keeps
  15px because a workbench is read at it), `--fs-h3d 1.5rem`, `--fs-lead 1.0625rem`,
  the fluid `--fs-hero`/`--fs-h2d`/`--fs-close`, and the CJK twins
  `--fs-h1zh`/`--fs-closezh`. They live in one commented extension block and
  `--fs-display` keeps its product meaning of 2rem. A fluid size goes there, never
  inline. The board's `.brand` sits on `--fs-h3` (18px) where the console's `.logo`
  sits on `--fs-h4` (16px): a canonical step each, one ladder, two registers.
- `code` is `max(.85em, var(--fs-xs))` so a machine string is never the smallest
  thing on the page.
- Three tracking jobs, not five magic numbers: `--track-kicker .14em` (uppercase
  mono eyebrow), `--track-label .08em` (mono micro-label — table headers,
  counters, language toggle), `--track-tight -.01em` (display).
  **`html:lang(zh)` sets all three to `0`** — CJK glyphs gain nothing from
  letter-spacing and tracking breaks word-segmentation.

## Spacing, radius, borders, elevation

- `--sp1…6` = 4 / 8 / 16 / 24 / 32 / 48px. GTM extends the ladder with `--sp7`
  64px / `--sp8` 96px for section rhythm only; the app's ladder stops at `--sp6`
  because no in-app surface needs a 64-96px gap.
- Radius ladder is **`--r0:0` · `--r1:2px` · `--r2:4px`**. `--r1` for anything
  interactive or contained, `--r2` for a centred sheet and `.prose img`, `--r0`
  for full-bleed. **999px pills are banned** — at 12px they read as decoration.
  The one permitted `50%` is a *fixed-square* mark (the 8px status `.dot`), where
  the radius is the shape rather than a corner treatment.
- **Elevation is a token, and only two layers may have one.** Surfaces in the
  layout separate by hairline border plus layer fill; `--elev` (toast) and
  `--elev-lg` (modal) exist for the two that genuinely float over the page. They
  are theme properties rather than per-rule literals because the dark ramp needs
  roughly twice the black of the light one for the same perceived lift — a
  hard-coded `rgba(0,0,0,.35)` reads as dirt on white and vanishes on charcoal.
  This is still the single biggest structural difference from a SaaS default.
- Side-stripe borders (`border-left` > 1px as a colored accent) are banned on
  every surface.
- The build guards enforce the last three rules, so they are written to accept
  what the ramp itself emits: colour may appear inside a shadow token (a literal
  `rgba()` is the violation, `var(--elev)` is not), and `50%` is allowed in the
  radius check where a mark is a fixed square. Both carve-outs name the
  distinction rather than widening the ban.

## Motion

- `--dur:110ms`, `--ease:cubic-bezier(0.2,0,0.38,0.9)`.
- Only `color`, `border-color`, `background-color`, `opacity`. No `transform` on hover.
- Console has no entrance animation. GTM keeps its mechanical slot-in (`slot-in`,
  `thud`); reduced motion kills it to a crossfade and sets `scroll-behavior:auto`.

## Z-scale

Semantic tiers, never arbitrary numbers: `--z-sticky:60` → `--z-toast:70` are
declared in the ramp itself, so a sticky bar cannot out-rank a toast on one
surface and not on another (the console said 60, the catalogue said 20, before
the pair became tokens). `--z-tooltip:80` exists only in the Android demo, for
its glossary tooltip — the topmost tier on that page, and a per-surface
extension rather than a ramp token because nothing else has a tooltip.

## Component vocabulary

- Tabs: `<button role="tab">` with `aria-selected`, list is `role="tablist"`.
- Named classes, no inline layout: `.plan-group`/`.plan-item`,
  `.diff`/`.diff-h`/`.diff-b`/`.diff-row`, `.steps`, `.hint`, `.side-card`, and
  layout utilities `.stack`/`.w-full`/`.mt*`/`.gap6`.
- Empty states teach: icon + what happened + the next action, never a bare "暂无".
- Secondary actions are `button.ghost`; accent fill stays on the single primary
  action per card.
- Status: `--good/--warn/--bad` appear only as 7–10px dots, state lamps, or text
  on gate/phase rows — never as large fills. Pill text stays `--muted`/`--fg`; the
  dot carries semantics. State surfaces use `--*-fill` plus the dot.
- **A verdict is a mark plus a word, never an emoji.** The mark vocabulary is
  `.dot` (8px, `--faint`) with `.d-ok`/`.d-warn`/`.d-bad`, plus the inline SVG
  ticks and crosses; the word beside it is what makes it legible to a screen
  reader and to a monochrome print. The console previously spelled pass/fail with
  `✅`/`❌`, which reads as chrome from a consumer app and disappears at
  `font-size:var(--fs-xs)`. Emoji are banned as UI on every surface.
- The mark, `.hint`, `.stats`/`.stat`, `.sec-head`, `.brand`/`.logo` and `input`
  live in the shared layer, not per page: six surfaces had six near-copies of the
  same stat strip and section head, each with one number off. Reuse is the default;
  a page authors a rule only when the shape genuinely differs.
- `.notice` is not `.card`. The console's `.card` is a dense `--layer-01` panel at
  `--r1` inside a working grid; `.notice` is a centred `--panel` sheet at `--r2`
  with a brand lockup, one `h1`, a paragraph and a `.cta` row. One name cannot mean
  both, so `NOTICE_CSS` ships the sheet whole — the share and acknowledgement pages
  take it instead of authoring a third variant.
- Focus: `:focus-visible` → 2px `--accent` outline, 2px offset. Never animate the ring.
- Icons: console inline SVG sprite (16×16, stroke 1.5 round); GTM/portal inline
  paths, `stroke:currentColor; fill:none`, stroke-width 1.8. No emoji as chrome.
- Bilingual: when zh and en coexist, **both must be readable** — no small gray
  Chinese under a large Latin heading.

## What all surfaces must share

The engineering blue and its placement (≤5% per viewport), the hairline border
language, the r0/r1/r2 ladder, the tokenised type scale — every size expressed as
a step, including a mirrored surface's own — the two elevation tokens and nothing
above them, the 60/70 z-scale, the mark vocabulary for verdicts, 110ms motion, and
the enterprise copy voice: declarative, numbers only when real.

Register may differ; the ladder may not. A marketing board is allowed a 16px
reading size and a fluid hero *because it declares them as named steps of this
same ramp*, which is the difference between one system with two registers and two
systems.

## Cross-surface navigation (mandatory keep)

- GTM footer nav and the portal topbars link each other.
- Console topbar carries 「GTM 官网」 and 「技能手册库」 on both `/` and `/console`.
- `GTM/images/` console rasters are intentional live captures (stamped
  `LIVE CAPTURE · FDE-Scope-0.1.0-universal2.app · 1440×952 @2x`) and are
  deliberately **not** localized — they are evidence of the real product.
