/**
 * TransferLens Shared Package
 * ===========================
 * 
 * Provides TypeScript types and API client for the TransferLens platform.
 * 
 * @packageDocumentation
 */

// Re-export all types
export * from './types';

// Re-export client
export {
  TransferLensClient,
  TransferLensApiError,
  createClient,
  createServerClient,
  createBrowserClient,
  type TransferLensClientConfig,
  type RequestOptions,
} from './client';
