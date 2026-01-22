-- TransferLens PostgreSQL Initialization
-- This script runs on first container startup

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- Create read-only user for analytics (optional)
-- CREATE USER tl_readonly WITH PASSWORD 'readonly_password';
-- GRANT CONNECT ON DATABASE transferlens TO tl_readonly;
-- GRANT USAGE ON SCHEMA public TO tl_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO tl_readonly;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'TransferLens database initialized successfully';
END $$;
