# @transferlens/shared

Shared TypeScript types and API client for TransferLens.

## Installation

```bash
npm install @transferlens/shared
# or
pnpm add @transferlens/shared
```

## Usage

### Basic Client Usage

```typescript
import { createClient } from '@transferlens/shared';

const client = createClient({
  baseUrl: 'http://localhost:8000',
});

// Search for players and clubs
const searchResults = await client.search({ q: 'Haaland', limit: 10 });

// Get player details
const player = await client.getPlayer('player-uuid');
console.log(player.name, player.market_value);
console.log('What Changed:', player.what_changed);

// Get club details
const club = await client.getClub('club-uuid');
console.log(club.squad_count, club.outgoing_probabilities);

// Get market probability table
const market = await client.getMarketLatest({
  horizon_days: 90,
  min_probability: 0.5,
  limit: 50,
});
```

### Time-Travel Queries

```typescript
// Get signals as of a specific date
const signals = await client.getPlayerSignals('player-uuid', {
  as_of: '2025-01-01T00:00:00Z',
  signal_type: SignalType.MARKET_VALUE,
});

// Get predictions as of a specific date
const predictions = await client.getPlayerPredictions('player-uuid', {
  as_of: '2025-01-01T00:00:00Z',
  horizon_days: 90,
});
```

### Track User Events

```typescript
import { UserEventType } from '@transferlens/shared';

// Track a player view
await client.createUserEvent({
  user_anon_id: 'anon_abc123',
  session_id: 'sess_xyz789',
  event_type: UserEventType.PLAYER_VIEW,
  player_id: 'player-uuid',
  event_props_json: {
    page_url: '/players/player-uuid',
    referrer: 'search',
  },
});
```

### Admin Operations (requires API key)

```typescript
import { createClient, TransferType, FeeType, EntityType, SignalType } from '@transferlens/shared';

const adminClient = createClient({
  baseUrl: 'http://localhost:8000',
  adminApiKey: 'your-admin-api-key',
});

// Create a transfer event
await adminClient.createTransferEvent({
  player_id: 'player-uuid',
  from_club_id: 'from-club-uuid',
  to_club_id: 'to-club-uuid',
  transfer_type: TransferType.PERMANENT,
  transfer_date: '2025-01-15',
  fee_amount: 50000000,
  fee_currency: 'EUR',
  fee_type: FeeType.CONFIRMED,
  source: 'official',
  source_confidence: 1.0,
});

// Create a signal event
await adminClient.createSignalEvent({
  entity_type: EntityType.PLAYER,
  player_id: 'player-uuid',
  signal_type: SignalType.MARKET_VALUE,
  value_num: 100000000,
  source: 'transfermarkt',
  confidence: 0.95,
  observed_at: new Date().toISOString(),
  effective_from: new Date().toISOString(),
});

// Refresh materialized views
await adminClient.refreshMaterializedViews();
```

### Next.js Usage

```typescript
// Server Component (app router)
import { createServerClient } from '@transferlens/shared';

export default async function PlayerPage({ params }: { params: { id: string } }) {
  const client = createServerClient();
  const player = await client.getPlayer(params.id);
  
  return <div>{player.name}</div>;
}

// Client Component
'use client';
import { createBrowserClient } from '@transferlens/shared';
import { useEffect, useState } from 'react';

export function PlayerSearch() {
  const [results, setResults] = useState([]);
  const client = createBrowserClient();
  
  const handleSearch = async (q: string) => {
    const response = await client.search({ q });
    setResults(response.results);
  };
  
  return <input onChange={(e) => handleSearch(e.target.value)} />;
}
```

## Types

All API types are exported from the package:

```typescript
import type {
  PlayerDetail,
  ClubDetail,
  SearchResponse,
  MarketLatestResponse,
  ProbabilityRow,
  SignalDelta,
  // ... and more
} from '@transferlens/shared';
```

## Enums

```typescript
import {
  SignalType,
  TransferType,
  FeeType,
  UserEventType,
  EntityType,
  SearchResultType,
} from '@transferlens/shared';
```

## Error Handling

```typescript
import { TransferLensApiError } from '@transferlens/shared';

try {
  const player = await client.getPlayer('invalid-id');
} catch (error) {
  if (error instanceof TransferLensApiError) {
    console.error(`API Error ${error.status}: ${error.message}`);
    if (error.response) {
      console.error('Details:', error.response.details);
    }
  }
}
```

## Configuration

```typescript
const client = createClient({
  // Base URL of the API
  baseUrl: 'http://localhost:8000',
  
  // Admin API key for protected endpoints
  adminApiKey: 'your-api-key',
  
  // Request timeout in milliseconds (default: 30000)
  timeout: 10000,
  
  // Custom headers
  headers: {
    'X-Custom-Header': 'value',
  },
  
  // Custom fetch implementation (for testing, SSR, etc.)
  fetch: customFetch,
});
```

## License

MIT
