# Google Stitch Prompt — Trading Intelligence Platform

## Vibe / Style Direction
Dark, professional trading terminal aesthetic. Think Bloomberg Terminal meets modern fintech. Data-dense but clean — not minimal, but precise. Every pixel earns its place.

---

## Color Palette
- Background primary: #09090b (near-black zinc)
- Background card: #18181b (zinc-900)
- Background hover: #27272a (zinc-800)
- Border: #3f3f46 (zinc-700)
- Text primary: #fafafa (white)
- Text secondary: #a1a1aa (zinc-400)
- Accent / primary action: #2563eb (blue-600)
- Accent hover: #1d4ed8 (blue-700)
- Long / buy: #22c55e (green-500)
- Short / sell: #ef4444 (red-500)
- Featured badge: #f59e0b (amber-500)
- High confidence: #22c55e (green)
- Medium confidence: #f59e0b (amber)
- Low confidence: #ef4444 (red)

---

## Typography
- Font: Inter (Google Fonts)
- Display/headings: semibold, tracking tight
- Body: text-sm (14px), text-zinc-400
- Monospace for prices/levels: font-mono, text-xs

---

## App Name
Trading Intelligence Platform

---

## Pages to Design

### 1. Home / Content Feed
- Sticky header with app name "Trading Intelligence" on the left
- Search bar (full-width, dark input, blue search button)
- Filter row below search: dropdowns for Type, Asset Class, Direction, Timeframe, Confidence. Plus a "Top Picks" toggle button. Filters should be compact pill/dropdown style.
- Content grid below: 3-column responsive grid (3 cols desktop, 2 tablet, 1 mobile)
- Each content card shows:
  - Content type badge (Morning Briefing / Trade Setup / Macro Roundup / Contrarian Alert)
  - "Featured" amber badge if featured
  - Confidence badge (High/Medium/Low with color)
  - Instrument symbol (colored by asset class: blue=FX, amber=Commodities, purple=Crypto, green=Indices)
  - Direction tag (LONG in green / SHORT in red) or "MACRO" for roundups
  - Title (bold, 2-line clamp)
  - Rationale text (3-line clamp, muted)
  - For Trade Setups: 3-column mini-table showing Entry / Stop Loss / Take Profit with monospace font
  - Tags row (momentum, breakout etc — small gray pills)
  - Timestamp (bottom right, muted)
- Infinite scroll or "Load More" at bottom
- Footer with "Trading Intelligence Platform"

### 2. Instrument Detail Page (/instrument/EURUSD)
- Back breadcrumb navigation
- Large instrument badge + full name
- Stats row: asset class, number of content items
- Same 3-column content grid filtered to this instrument
- Optional: price ticker showing current price for the instrument (from API)

### 3. Content Card Component (used in both pages)
- Dark card (#18181b background)
- 1px zinc-700 border, rounded-lg
- Hover: border brightens to zinc-600, subtle transition
- Featured cards: slightly brighter border or amber left border accent

---

## Component Inventory

### ContentCard
States: default, hover, featured
Variants: briefing, setup, macro_roundup, contrarian_alert

### FilterBar
Dropdown selects for: Type, Asset Class, Direction, Timeframe, Confidence
Toggle button: Top Picks
All inline, wrapping to new lines on mobile

### SearchBar
Full-width input, dark background, subtle border, blue focus ring
Search icon inside input on left
"Search" button on right

### InstrumentBadge
Pill-shaped, color coded by asset class:
- FX: blue-900 bg, blue-300 text
- Commodities: amber-900 bg, amber-300 text
- Crypto: purple-900 bg, purple-300 text
- Indices: green-900 bg, green-300 text

### ConfidenceBadge
- High: green-900 bg, green-300 text, "HIGH" label
- Medium: amber-900 bg, amber-300 text, "MEDIUM" label
- Low: red-900 bg, red-300 text, "LOW" label

### Setup Mini-Table (inside Trade Setup cards)
3 columns: Entry | Stop Loss | Take Profit
Dark zinc-800 background cells, monospace font, small text
Entry: white text
Stop Loss: red-400 text with "SL" label above
Take Profit: green-400 text with "TP" label above

---

## Layout Specs
- Max container width: 1280px (max-w-7xl)
- Page padding: 16px sides (px-4)
- Card padding: 16px (p-4)
- Grid gap: 16px (gap-4)
- Section spacing: 24px vertical (py-6)

---

## Technical Context
- Framework: Next.js 16 with App Router
- CSS: Tailwind CSS v4
- Colors referenced above are Tailwind class names
- This is an existing codebase — designs should complement, not replace, the current structure

---

## Mood Reference
Bloomberg Terminal + Robinhood + Reuters Terminal
Professional, data-forward, no decoration for decoration's sake
Dark background is non-negotiable — this is a trading tool
