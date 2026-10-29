-- ════════════════════════════════════════════════════════════════════════════
--  08_auth.sql  ·  Phone + OTP sign-in (schema auth, outside the 15 core tables)
--
--  The OTP itself is never stored: only an HMAC-SHA256 of (phone, code) made
--  with a server secret. A challenge expires after 5 minutes and allows at
--  most 5 wrong attempts; the API also limits how often codes can be sent.
-- ════════════════════════════════════════════════════════════════════════════
CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.otp_challenges (
    challenge_id  bigint         GENERATED ALWAYS AS IDENTITY CONSTRAINT pk_otp_challenges PRIMARY KEY,
    phone         indian_mobile  NOT NULL,
    code_hash     char(64)       NOT NULL,
    created_at    timestamptz    NOT NULL DEFAULT now(),
    expires_at    timestamptz    NOT NULL,
    attempts      smallint       NOT NULL DEFAULT 0,
    verified_at   timestamptz,
    CONSTRAINT ck_otp_expiry   CHECK (expires_at > created_at),
    CONSTRAINT ck_otp_attempts CHECK (attempts BETWEEN 0 AND 5),
    CONSTRAINT ck_otp_hash     CHECK (code_hash ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS ix_otp_phone_created ON auth.otp_challenges (phone, created_at DESC);

GRANT USAGE ON SCHEMA auth TO yup_app;
GRANT SELECT, INSERT, UPDATE ON auth.otp_challenges TO yup_app;
