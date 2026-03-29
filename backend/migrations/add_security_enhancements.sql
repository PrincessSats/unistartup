-- Security Enhancements Migration
-- Adds audit logging, password tracking, and security-related indexes
-- Created: March 2026

-- ============================================================
-- 1. Audit Logging Table
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(128) NOT NULL,
    resource_type VARCHAR(64),
    resource_id BIGINT,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address VARCHAR(64),
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for common audit queries
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_created ON audit_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action_created ON audit_logs(action, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

-- ============================================================
-- 2. Password Tracking
-- ============================================================

-- Add password change tracking to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_password_changed ON users(password_changed_at);

-- ============================================================
-- 3. Security Event Tracking
-- ============================================================

-- Add failed login tracking (for account lockout policies)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0;

ALTER TABLE users 
ADD COLUMN IF NOT EXISTS last_failed_login_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_failed_login ON users(failed_login_attempts) WHERE failed_login_attempts > 0;

-- ============================================================
-- 4. Session Security
-- ============================================================

-- Add fingerprint column to refresh tokens for session binding
ALTER TABLE auth_refresh_tokens 
ADD COLUMN IF NOT EXISTS user_agent_hash VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_user_agent_hash ON auth_refresh_tokens(user_agent_hash);

-- ============================================================
-- 5. Audit Log Retention Function
-- ============================================================

-- Function to clean up old audit logs (retention policy)
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs(retention_days INTEGER DEFAULT 365)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM audit_logs
    WHERE created_at < (now() - (retention_days || ' days')::interval)
    AND action NOT IN (
        'auth.login.failed',
        'security.rate_limit_exceeded',
        'security.xss_attempt',
        'security.sql_injection_attempt'
    );  -- Keep security events longer
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 6. Security Audit View
-- ============================================================

-- Create a view for easy security auditing
CREATE OR REPLACE VIEW v_security_audit AS
SELECT 
    id,
    action,
    user_id,
    resource_type,
    resource_id,
    ip_address,
    DATE_TRUNC('hour', created_at) AS hour,
    COUNT(*) OVER (
        PARTITION BY action, ip_address, DATE_TRUNC('hour', created_at)
    ) AS occurrences_in_hour
FROM audit_logs
WHERE action LIKE 'auth.%' OR action LIKE 'security.%'
ORDER BY created_at DESC;

-- ============================================================
-- 7. Initial Data
-- ============================================================

-- Log the migration itself
INSERT INTO audit_logs (action, details, ip_address)
VALUES (
    'system.migration_applied',
    '{"migration": "add_security_enhancements", "version": "2026-03"}'::jsonb,
    'SYSTEM'
);

-- ============================================================
-- 8. Comments for Documentation
-- ============================================================

COMMENT ON TABLE audit_logs IS 'Immutable audit trail for security-relevant events';
COMMENT ON COLUMN audit_logs.action IS 'Standardized action code (e.g., auth.login.success, admin.task.deleted)';
COMMENT ON COLUMN audit_logs.details IS 'JSONB payload with action-specific details';
COMMENT ON COLUMN audit_logs.ip_address IS 'IP address of the request (for forensics)';
COMMENT ON COLUMN audit_logs.user_agent IS 'User agent string (truncated to 1024 chars)';
COMMENT ON FUNCTION cleanup_old_audit_logs IS 'Remove audit logs older than retention period (default 365 days)';
COMMENT ON VIEW v_security_audit IS 'Aggregated view of security events for monitoring';

-- ============================================================
-- Migration Complete
-- ============================================================
