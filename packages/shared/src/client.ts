/**
 * TransferLens API Client
 * =======================
 * 
 * TypeScript client for the TransferLens FastAPI backend.
 * Provides type-safe access to all API endpoints.
 */

import type {
  HealthResponse,
  ReadyResponse,
  SearchResponse,
  SearchParams,
  PlayerDetail,
  SignalEventRead,
  PlayerSignalsParams,
  PredictionBrief,
  PlayerPredictionsParams,
  ClubDetail,
  MarketLatestResponse,
  MarketLatestParams,
  UserEventCreate,
  UserEventResponse,
  TransferEventCreate,
  TransferEventRead,
  SignalEventCreate,
  MaterializedViewRefreshResponse,
  ErrorResponse,
} from './types';

// =============================================================================
// CLIENT CONFIGURATION
// =============================================================================

export interface TransferLensClientConfig {
  /** Base URL of the API (default: http://localhost:8000) */
  baseUrl?: string;
  /** Admin API key for protected endpoints */
  adminApiKey?: string;
  /** Custom fetch implementation (for SSR, testing, etc.) */
  fetch?: typeof fetch;
  /** Default timeout in milliseconds */
  timeout?: number;
  /** Custom headers to include in all requests */
  headers?: Record<string, string>;
}

export interface RequestOptions {
  /** Abort signal for request cancellation */
  signal?: AbortSignal;
  /** Custom headers for this request */
  headers?: Record<string, string>;
}

// =============================================================================
// API ERROR
// =============================================================================

export class TransferLensApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public response?: ErrorResponse
  ) {
    super(message);
    this.name = 'TransferLensApiError';
  }
}

// =============================================================================
// CLIENT IMPLEMENTATION
// =============================================================================

export class TransferLensClient {
  private baseUrl: string;
  private adminApiKey?: string;
  private fetchImpl: typeof fetch;
  private timeout: number;
  private defaultHeaders: Record<string, string>;

  constructor(config: TransferLensClientConfig = {}) {
    this.baseUrl = config.baseUrl?.replace(/\/$/, '') || 'http://localhost:8000';
    this.adminApiKey = config.adminApiKey;
    this.fetchImpl = config.fetch || globalThis.fetch;
    this.timeout = config.timeout || 30000;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      ...config.headers,
    };
  }

  // ===========================================================================
  // PRIVATE HELPERS
  // ===========================================================================

  private async request<T>(
    method: string,
    path: string,
    options: {
      body?: unknown;
      params?: Record<string, string | number | boolean | undefined>;
      requiresAdmin?: boolean;
      requestOptions?: RequestOptions;
    } = {}
  ): Promise<T> {
    const { body, params, requiresAdmin, requestOptions } = options;

    // Build URL with query params
    let url = `${this.baseUrl}${path}`;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      });
      const queryString = searchParams.toString();
      if (queryString) {
        url += `?${queryString}`;
      }
    }

    // Build headers
    const headers: Record<string, string> = {
      ...this.defaultHeaders,
      ...requestOptions?.headers,
    };

    if (requiresAdmin && this.adminApiKey) {
      headers['X-API-Key'] = this.adminApiKey;
    }

    // Create abort controller for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await this.fetchImpl(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: requestOptions?.signal || controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorResponse: ErrorResponse | undefined;
        try {
          errorResponse = await response.json();
        } catch {
          // Response might not be JSON
        }
        throw new TransferLensApiError(
          errorResponse?.message || `HTTP ${response.status}: ${response.statusText}`,
          response.status,
          errorResponse
        );
      }

      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof TransferLensApiError) {
        throw error;
      }
      if (error instanceof Error && error.name === 'AbortError') {
        throw new TransferLensApiError('Request timeout', 408);
      }
      throw new TransferLensApiError(
        error instanceof Error ? error.message : 'Unknown error',
        0
      );
    }
  }

  // ===========================================================================
  // HEALTH ENDPOINTS
  // ===========================================================================

  /**
   * Health check endpoint.
   * Returns status of all dependencies.
   */
  async health(options?: RequestOptions): Promise<HealthResponse> {
    return this.request<HealthResponse>('GET', '/health', { requestOptions: options });
  }

  /**
   * Kubernetes readiness probe.
   */
  async ready(options?: RequestOptions): Promise<ReadyResponse> {
    return this.request<ReadyResponse>('GET', '/ready', { requestOptions: options });
  }

  /**
   * Kubernetes liveness probe.
   */
  async live(options?: RequestOptions): Promise<{ alive: boolean }> {
    return this.request<{ alive: boolean }>('GET', '/live', { requestOptions: options });
  }

  // ===========================================================================
  // SEARCH
  // ===========================================================================

  /**
   * Search for players and clubs by name.
   * Results are ranked by relevance.
   */
  async search(params: SearchParams, options?: RequestOptions): Promise<SearchResponse> {
    return this.request<SearchResponse>('GET', '/api/v1/search', {
      params: {
        q: params.q,
        limit: params.limit,
      },
      requestOptions: options,
    });
  }

  // ===========================================================================
  // PLAYERS
  // ===========================================================================

  /**
   * Get detailed player information.
   * Includes profile, signals, predictions, and "what changed".
   */
  async getPlayer(playerId: string, options?: RequestOptions): Promise<PlayerDetail> {
    return this.request<PlayerDetail>('GET', `/api/v1/players/${playerId}`, {
      requestOptions: options,
    });
  }

  /**
   * Get signal history for a player.
   * Supports time-travel via as_of parameter.
   */
  async getPlayerSignals(
    playerId: string,
    params?: PlayerSignalsParams,
    options?: RequestOptions
  ): Promise<SignalEventRead[]> {
    return this.request<SignalEventRead[]>('GET', `/api/v1/players/${playerId}/signals`, {
      params: params as Record<string, string | number | undefined>,
      requestOptions: options,
    });
  }

  /**
   * Get prediction history for a player.
   * Supports time-travel via as_of parameter.
   */
  async getPlayerPredictions(
    playerId: string,
    params?: PlayerPredictionsParams,
    options?: RequestOptions
  ): Promise<PredictionBrief[]> {
    return this.request<PredictionBrief[]>('GET', `/api/v1/players/${playerId}/predictions`, {
      params: params as Record<string, string | number | undefined>,
      requestOptions: options,
    });
  }

  // ===========================================================================
  // CLUBS
  // ===========================================================================

  /**
   * Get detailed club information.
   * Includes squad, probabilities, and recent transfers.
   */
  async getClub(clubId: string, options?: RequestOptions): Promise<ClubDetail> {
    return this.request<ClubDetail>('GET', `/api/v1/clubs/${clubId}`, {
      requestOptions: options,
    });
  }

  // ===========================================================================
  // MARKET
  // ===========================================================================

  /**
   * Get the latest transfer probability table.
   * Supports filtering by competition, club, horizon, and probability.
   */
  async getMarketLatest(
    params?: MarketLatestParams,
    options?: RequestOptions
  ): Promise<MarketLatestResponse> {
    return this.request<MarketLatestResponse>('GET', '/api/v1/market/latest', {
      params: params as Record<string, string | number | undefined>,
      requestOptions: options,
    });
  }

  // ===========================================================================
  // EVENTS
  // ===========================================================================

  /**
   * Record a user event for analytics and weak signal derivation.
   */
  async createUserEvent(
    event: UserEventCreate,
    options?: RequestOptions
  ): Promise<UserEventResponse> {
    return this.request<UserEventResponse>('POST', '/api/v1/events/user', {
      body: event,
      requestOptions: options,
    });
  }

  // ===========================================================================
  // ADMIN ENDPOINTS (requires API key)
  // ===========================================================================

  /**
   * Create a new transfer event in the ledger.
   * Requires admin API key.
   */
  async createTransferEvent(
    transfer: TransferEventCreate,
    options?: RequestOptions
  ): Promise<TransferEventRead> {
    return this.request<TransferEventRead>('POST', '/api/v1/admin/transfer_events', {
      body: transfer,
      requiresAdmin: true,
      requestOptions: options,
    });
  }

  /**
   * Create a new signal event.
   * Requires admin API key.
   */
  async createSignalEvent(
    signal: SignalEventCreate,
    options?: RequestOptions
  ): Promise<SignalEventRead> {
    return this.request<SignalEventRead>('POST', '/api/v1/admin/signal_events', {
      body: signal,
      requiresAdmin: true,
      requestOptions: options,
    });
  }

  /**
   * Refresh all materialized views.
   * Requires admin API key.
   */
  async refreshMaterializedViews(
    options?: RequestOptions
  ): Promise<MaterializedViewRefreshResponse> {
    return this.request<MaterializedViewRefreshResponse>(
      'POST',
      '/api/v1/admin/rebuild/materialized',
      {
        requiresAdmin: true,
        requestOptions: options,
      }
    );
  }
}

// =============================================================================
// FACTORY FUNCTION
// =============================================================================

/**
 * Create a new TransferLens API client.
 * 
 * @example
 * ```typescript
 * // Basic usage
 * const client = createClient({ baseUrl: 'https://api.transferlens.com' });
 * const player = await client.getPlayer('123');
 * 
 * // With admin access
 * const adminClient = createClient({
 *   baseUrl: 'https://api.transferlens.com',
 *   adminApiKey: 'your-api-key'
 * });
 * ```
 */
export function createClient(config?: TransferLensClientConfig): TransferLensClient {
  return new TransferLensClient(config);
}

// =============================================================================
// REACT/NEXT.JS HELPERS
// =============================================================================

/**
 * Create a client configured for Next.js server-side usage.
 */
export function createServerClient(config?: TransferLensClientConfig): TransferLensClient {
  return new TransferLensClient({
    baseUrl: process.env.API_URL || config?.baseUrl || 'http://api:8000',
    adminApiKey: process.env.ADMIN_API_KEY || config?.adminApiKey,
    ...config,
  });
}

/**
 * Create a client configured for browser usage.
 */
export function createBrowserClient(config?: TransferLensClientConfig): TransferLensClient {
  const baseUrl = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_URL || config?.baseUrl || 'http://localhost:8000')
    : config?.baseUrl;
  
  return new TransferLensClient({
    baseUrl,
    ...config,
  });
}
