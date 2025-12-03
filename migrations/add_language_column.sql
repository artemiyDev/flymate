-- Migration: Add language column to users table
-- Date: 2025
-- Description: Add language preference column for i18n support

-- Add language column with default 'ru'
ALTER TABLE users
ADD COLUMN IF NOT EXISTS language CHAR(5) NOT NULL DEFAULT 'ru';

-- Update existing users to use their Telegram language_code if available
UPDATE users
SET language = CASE
    WHEN SUBSTRING(language_code FROM 1 FOR 2) IN ('ru', 'en')
    THEN SUBSTRING(language_code FROM 1 FOR 2)
    ELSE 'ru'
END
WHERE language_code IS NOT NULL;
