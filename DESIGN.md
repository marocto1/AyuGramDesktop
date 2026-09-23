# Extera One — Desktop design system

This branch uses a restrained desktop-messenger visual system instead of a web-dashboard aesthetic.

## Principles

- Dense enough for desktop, but never cramped.
- One visual hierarchy: navigation → conversation → actions.
- No decorative cards, gradients, glass, glow, left-border accents or status pills without meaning.
- No raw brand hex values in layout/style files. Colors remain driven by Telegram theme tokens so day/night/custom themes continue to work.
- Shadows are reserved for real elevation (menus, modal layers), not hover decoration.
- Interactive controls in the same row share a height.
- Accent color is for actions and state, not decoration.

## Geometry tokens

- Compact control: 40 px
- Standard control: 44 px
- Primary/touch control: 48 px
- Chat row: 68 px
- Chat avatar: 48 px
- Settings row: 48 px
- Small radius: 7–10 px
- Message radius: 14 px
- Search radius: 10 px
- Left column baseline: 300 px

## Layout

- Left column is deliberately wider and calmer.
- Chat rows use more horizontal breathing room and a stronger text baseline.
- Message bubbles are less pill-like and more desktop-oriented.
- Composer controls use a shared 48 px rhythm.
- Settings and ExteraGram sections inherit the same 48 px row system.
- Main menu is wider but visually shorter, reducing the oversized cover feeling.

## Anti-slop constraints

- No indigo/violet default branding.
- No emoji as UI icons.
- No permanent animated status dots.
- No card-within-card layouts for settings.
- No all-caps micro-label system.
- No blanket hover shadows.
- No pill-shaped controls where a compact rounded rectangle is clearer.

The intended character is quiet, precise and tool-like: Telegram-native behavior with a visibly different desktop composition.
