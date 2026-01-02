-- Migration 001: Initial schema
-- This migration creates the initial database schema for SDASystem v3

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Apply schema from backend/db/schema.sql
-- (Schema is applied directly, this file is for tracking migration history)

