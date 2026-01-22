# TransferLens Web

Next.js frontend for the TransferLens platform - real-time football transfer intelligence.

## Features

### Pages

| Route | Description |
|-------|-------------|
| `/` | Home - Search, Latest Market table, Trending players |
| `/p/[playerId]` | Player page - Probabilities, What Changed, History, Chart |
| `/c/[clubId]` | Club page - Incoming/Outgoing probabilities, Squad |
| `/market` | Full market table with filters |
| `/compare` | Side-by-side player comparison tool |
| `/watchlist` | Personal watchlist with alerts (localStorage) |

### Components

| Component | Description |
|-----------|-------------|
| `SearchBar` | Debounced search with keyboard navigation |
| `ProbabilityTable` | Sortable table of transfer probabilities |
| `ProbabilityChart` | Recharts area chart of probability history |
| `DestinationCard` | Top destination display with drivers |
| `WhatChanged` | Signal changes with severity indicators |
| `TrendingPlayers` | Ranked list by attention/probability |
| `WatchlistButton` | Add/remove from local watchlist |
| `ShareCard` | Twitter/Copy link share menu |

### Viral Mechanics

1. **OG Image Generation** - Server-side images at `/api/og/player/[playerId]`
2. **Share Cards** - Twitter and copy link with formatted text
3. **Compare Tool** - Side-by-side player analysis
4. **Watchlist** - Track players with alert toggles

### Event Tracking

All user interactions are tracked via `POST /api/v1/events/user`:

```typescript
// Events tracked
track.pageView()
track.playerView(playerId)
track.clubView(clubId)
track.search(query, resultsCount)
track.watchlistAdd(playerId)
track.watchlistRemove(playerId)
track.shareClick(playerId, platform)
track.compareUse(player1Id, player2Id)
```

Session and anonymous user IDs are stored in `sessionStorage` and `localStorage`.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS with terminal-inspired theme
- **Charts**: Recharts
- **Icons**: Lucide React
- **State**: React hooks + localStorage

## Design System

### Colors (Bloomberg Terminal inspired)

```css
--terminal-bg: #0a0a0a
--terminal-panel: #111111
--terminal-border: #2a2a2a
--bloomberg-orange: #ff6b00
--bloomberg-green: #00d26a
--bloomberg-red: #ff3d3d
--bloomberg-blue: #0088ff
```

### Typography

- **Headings**: Space Grotesk
- **Body/Data**: JetBrains Mono

## Environment Variables

```bash
# API endpoint
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Development

```bash
# Install dependencies
cd apps/web
pnpm install

# Run development server
pnpm dev

# Build for production
pnpm build

# Start production server
pnpm start
```

## Docker

```bash
# Build
docker build -t transferlens-web .

# Run
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://api:8000 transferlens-web
```

## ISR Caching

Pages use Incremental Static Regeneration:

| Page | Revalidate |
|------|------------|
| Home | 30s |
| Player | 60s |
| Club | 60s |
| Market | 30s |

## File Structure

```
src/
├── app/
│   ├── api/og/player/[playerId]/   # OG image generation
│   ├── c/[clubId]/                  # Club page
│   ├── p/[playerId]/                # Player page
│   ├── compare/                     # Compare tool
│   ├── market/                      # Market table
│   ├── watchlist/                   # Watchlist
│   ├── globals.css                  # Tailwind + custom styles
│   ├── layout.tsx                   # Root layout with nav
│   ├── page.tsx                     # Home page
│   ├── loading.tsx                  # Loading state
│   ├── error.tsx                    # Error boundary
│   └── not-found.tsx                # 404 page
├── components/
│   ├── SearchBar.tsx
│   ├── ProbabilityTable.tsx
│   ├── ProbabilityChart.tsx
│   ├── DestinationCard.tsx
│   ├── WhatChanged.tsx
│   ├── TrendingPlayers.tsx
│   ├── WatchlistButton.tsx
│   └── ShareCard.tsx
└── lib/
    ├── api.ts                       # API client
    ├── tracking.ts                  # Event tracking
    ├── watchlist.ts                 # Local watchlist
    └── utils.ts                     # Helpers
```

## Performance

- ISR caching for fast page loads
- Debounced search (200ms)
- Lazy loading with Suspense
- Optimized re-renders with proper keys
- Minimal client-side JS where possible

## License

MIT © TransferLens Team
