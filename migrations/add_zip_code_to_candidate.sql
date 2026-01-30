-- Migration: Add zip_code column to candidate table
-- Date: 2026-01-29
-- Description: Adds zip_code field to store candidate zip codes

ALTER TABLE candidate ADD COLUMN zip_code VARCHAR(20) NULL AFTER address;

-- Optional: Add an index if you plan to search by zip code frequently
-- CREATE INDEX idx_candidate_zip_code ON candidate(zip_code);
