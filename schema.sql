--
-- PostgreSQL database dump
--

\restrict USD7DJhMROKtvNj69onx1JWvblU1M2OuT6uQgi1dNkEmI1b9MsGGBZXLp4iddPN

-- Dumped from database version 16.13 (Ubuntu 16.13-201-yandex.57868.41c1cedd09)
-- Dumped by pg_dump version 16.13 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


--
-- Name: pgvector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgvector WITH SCHEMA public;


--
-- Name: EXTENSION pgvector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgvector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: cleanup_old_audit_logs(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.cleanup_old_audit_logs(retention_days integer DEFAULT 365) RETURNS integer
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: FUNCTION cleanup_old_audit_logs(retention_days integer); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.cleanup_old_audit_logs(retention_days integer) IS 'Remove audit logs older than retention period (default 365 days)';


--
-- Name: grant_early_promo_on_email_verified(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.grant_early_promo_on_email_verified() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    promo_count BIGINT;
    pro_plan_id BIGINT;
BEGIN
    -- Only fire on first email verification (NEW has value, OLD didn't)
    IF NEW.email_verified_at IS NULL OR OLD.email_verified_at IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Serialize to prevent race conditions on the first 1000 check
    PERFORM pg_advisory_xact_lock(431001);

    -- If user already has a promo tariff, skip
    IF EXISTS (
        SELECT 1 FROM user_tariffs
        WHERE user_id = NEW.id AND is_promo = TRUE
    ) THEN
        RETURN NEW;
    END IF;

    -- Count existing promo users
    SELECT COUNT(*) INTO promo_count FROM user_tariffs WHERE is_promo = TRUE;
    IF promo_count >= 1000 THEN
        -- Already granted 1000 promos, no more
        RETURN NEW;
    END IF;

    -- Get the PRO plan ID
    SELECT id INTO pro_plan_id FROM tariff_plans WHERE code = 'PRO' LIMIT 1;
    IF pro_plan_id IS NULL THEN
        -- tariff_plans not seeded yet, bail safely
        RETURN NEW;
    END IF;

    -- Upgrade existing active tariff to PRO, or insert PRO if none exists
    UPDATE user_tariffs
    SET tariff_id = pro_plan_id,
        is_promo  = TRUE,
        source    = COALESCE(source, 'early_1000')
    WHERE user_id = NEW.id AND valid_to IS NULL;

    -- If no active tariff was found/updated, insert a new PRO row
    IF NOT FOUND THEN
        INSERT INTO user_tariffs (user_id, tariff_id, is_promo, source)
        VALUES (NEW.id, pro_plan_id, TRUE, 'early_1000');
    END IF;

    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: activity_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_log (
    id integer NOT NULL,
    admin_id bigint,
    contest_id bigint,
    event_type character varying(64) NOT NULL,
    source character varying(32) DEFAULT 'admin_action'::character varying NOT NULL,
    action character varying(255) NOT NULL,
    details jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: activity_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: activity_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_log_id_seq OWNED BY public.activity_log.id;


--
-- Name: ai_base_images; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_base_images (
    id integer NOT NULL,
    category character varying(50) NOT NULL,
    s3_key character varying(500) NOT NULL,
    format character varying(10) NOT NULL,
    is_active boolean DEFAULT true
);


--
-- Name: ai_base_images_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_base_images_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_base_images_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_base_images_id_seq OWNED BY public.ai_base_images.id;


--
-- Name: ai_generation_analytics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_generation_analytics (
    id integer NOT NULL,
    task_type character varying(50) NOT NULL,
    difficulty character varying(20) NOT NULL,
    period_date date NOT NULL,
    total_variants integer DEFAULT 0,
    passed_variants integer DEFAULT 0,
    avg_reward double precision,
    avg_quality_score double precision,
    common_failures jsonb,
    best_temperature double precision,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: ai_generation_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_generation_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_generation_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_generation_analytics_id_seq OWNED BY public.ai_generation_analytics.id;


--
-- Name: ai_generation_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_generation_batches (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    requested_by integer,
    task_type character varying(50) NOT NULL,
    difficulty character varying(20) NOT NULL,
    num_variants integer DEFAULT 5 NOT NULL,
    attempt integer DEFAULT 1 NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    group_mean_reward double precision,
    group_std_reward double precision,
    pass_rate double precision,
    selected_variant_id uuid,
    failure_reasons_summary jsonb,
    created_at timestamp with time zone DEFAULT now(),
    completed_at timestamp with time zone,
    rag_context_ids integer[],
    rag_context_summary text,
    rag_query_text text,
    current_stage character varying(50) DEFAULT 'pending'::character varying,
    stage_started_at timestamp with time zone,
    stage_meta jsonb
);


--
-- Name: ai_generation_variants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_generation_variants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    batch_id uuid NOT NULL,
    variant_number integer NOT NULL,
    model_used character varying(100),
    temperature double precision,
    tokens_input integer,
    tokens_output integer,
    generation_time_ms integer,
    generated_spec jsonb,
    artifact_result jsonb,
    reward_checks jsonb,
    reward_total double precision,
    reward_binary double precision,
    passed_all_binary boolean DEFAULT false,
    quality_score double precision,
    quality_details jsonb,
    advantage double precision,
    rank_in_group integer,
    is_selected boolean DEFAULT false,
    published_task_id integer,
    failure_reason text,
    created_at timestamp with time zone DEFAULT now(),
    embedding public.vector(256)
);


--
-- Name: ai_xss_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_xss_templates (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    difficulty character varying(20) NOT NULL,
    xss_type character varying(50) NOT NULL,
    html_template text NOT NULL,
    payload_example text,
    is_active boolean DEFAULT true
);


--
-- Name: ai_xss_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_xss_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_xss_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_xss_templates_id_seq OWNED BY public.ai_xss_templates.id;


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id bigint NOT NULL,
    user_id bigint,
    action character varying(128) NOT NULL,
    resource_type character varying(64),
    resource_id bigint,
    details jsonb DEFAULT '{}'::jsonb,
    ip_address character varying(64),
    user_agent text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE audit_logs; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.audit_logs IS 'Immutable audit trail for security-relevant events';


--
-- Name: COLUMN audit_logs.action; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.audit_logs.action IS 'Standardized action code (e.g., auth.login.success, admin.task.deleted)';


--
-- Name: COLUMN audit_logs.details; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.audit_logs.details IS 'JSONB payload with action-specific details';


--
-- Name: COLUMN audit_logs.ip_address; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.audit_logs.ip_address IS 'IP address of the request (for forensics)';


--
-- Name: COLUMN audit_logs.user_agent; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.audit_logs.user_agent IS 'User agent string (truncated to 1024 chars)';


--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: auth_password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_password_reset_tokens (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    token_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    CONSTRAINT no_reuse CHECK (((used_at IS NULL) OR (used_at <= expires_at)))
);


--
-- Name: auth_password_reset_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_password_reset_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_password_reset_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_password_reset_tokens_id_seq OWNED BY public.auth_password_reset_tokens.id;


--
-- Name: auth_refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_refresh_tokens (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    token_hash text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    rotated_to_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone,
    user_agent text,
    ip_address text,
    user_agent_hash character varying(64)
);


--
-- Name: auth_refresh_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_refresh_tokens_id_seq OWNED BY public.auth_refresh_tokens.id;


--
-- Name: auth_registration_flows; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_registration_flows (
    id bigint NOT NULL,
    intent text DEFAULT 'register'::text NOT NULL,
    source text NOT NULL,
    email text,
    email_verified_at timestamp with time zone,
    terms_accepted_at timestamp with time zone,
    marketing_opt_in boolean DEFAULT false NOT NULL,
    marketing_opt_in_at timestamp with time zone,
    provider text,
    provider_user_id text,
    provider_email text,
    provider_login text,
    provider_avatar_url text,
    provider_raw_profile_json jsonb,
    oauth_state_hash text,
    oauth_code_verifier text,
    magic_link_token_hash text,
    magic_link_expires_at timestamp with time zone,
    magic_link_sent_count integer DEFAULT 0 NOT NULL,
    last_magic_link_sent_at timestamp with time zone,
    magic_link_consumed_at timestamp with time zone,
    expires_at timestamp with time zone NOT NULL,
    completed_user_id bigint,
    consumed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: auth_registration_flows_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_registration_flows_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_registration_flows_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_registration_flows_id_seq OWNED BY public.auth_registration_flows.id;


--
-- Name: contest_participants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contest_participants (
    contest_id bigint NOT NULL,
    user_id bigint NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL,
    last_active_at timestamp with time zone,
    completed_at timestamp with time zone
);


--
-- Name: contest_task_ratings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contest_task_ratings (
    id bigint NOT NULL,
    contest_id bigint NOT NULL,
    task_id bigint NOT NULL,
    user_id bigint NOT NULL,
    rating smallint NOT NULL,
    rated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT contest_task_ratings_rating_check CHECK (((rating >= 1) AND (rating <= 5)))
);


--
-- Name: contest_task_ratings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contest_task_ratings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contest_task_ratings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contest_task_ratings_id_seq OWNED BY public.contest_task_ratings.id;


--
-- Name: contest_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contest_tasks (
    contest_id bigint NOT NULL,
    task_id bigint NOT NULL,
    order_index integer DEFAULT 0 NOT NULL,
    points_override integer,
    override_title text,
    override_participant_description text,
    override_tags text[],
    override_category text,
    override_difficulty integer
);


--
-- Name: contests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contests (
    id bigint NOT NULL,
    title text NOT NULL,
    description text,
    start_at timestamp with time zone NOT NULL,
    end_at timestamp with time zone NOT NULL,
    is_public boolean DEFAULT false NOT NULL,
    leaderboard_visible boolean DEFAULT true NOT NULL
);


--
-- Name: contests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contests_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contests_id_seq OWNED BY public.contests.id;


--
-- Name: course_modules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.course_modules (
    id bigint NOT NULL,
    course_id bigint NOT NULL,
    title text NOT NULL,
    order_index integer DEFAULT 0 NOT NULL
);


--
-- Name: course_modules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.course_modules_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: course_modules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.course_modules_id_seq OWNED BY public.course_modules.id;


--
-- Name: courses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.courses (
    id bigint NOT NULL,
    code text NOT NULL,
    title text NOT NULL,
    description text,
    level text,
    is_public boolean DEFAULT true NOT NULL
);


--
-- Name: courses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.courses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: courses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.courses_id_seq OWNED BY public.courses.id;


--
-- Name: feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.feedback (
    user_id bigint NOT NULL,
    topic text NOT NULL,
    message text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id bigint NOT NULL,
    resolved boolean DEFAULT false NOT NULL
);


--
-- Name: feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.feedback_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.feedback_id_seq OWNED BY public.feedback.id;


--
-- Name: kb_comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kb_comments (
    id bigint NOT NULL,
    kb_entry_id bigint NOT NULL,
    user_id bigint NOT NULL,
    parent_id bigint,
    body text NOT NULL,
    status text DEFAULT 'published'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone,
    deleted_at timestamp with time zone
);


--
-- Name: kb_comments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kb_comments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kb_comments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kb_comments_id_seq OWNED BY public.kb_comments.id;


--
-- Name: kb_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kb_entries (
    id bigint NOT NULL,
    source text NOT NULL,
    source_id text,
    cve_id text,
    raw_en_text text,
    ru_title text,
    ru_summary text,
    ru_explainer text,
    tags text[] DEFAULT '{}'::text[],
    difficulty integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    embedding public.vector(256),
    cwe_ids text[] DEFAULT '{}'::text[],
    cvss_base_score real,
    cvss_vector text,
    attack_vector text,
    attack_complexity text,
    affected_products text[] DEFAULT '{}'::text[],
    cve_metadata jsonb
);


--
-- Name: kb_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kb_entries_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kb_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kb_entries_id_seq OWNED BY public.kb_entries.id;


--
-- Name: landing_hunt_session_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.landing_hunt_session_items (
    session_id bigint NOT NULL,
    bug_key text NOT NULL,
    found_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: landing_hunt_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.landing_hunt_sessions (
    id bigint NOT NULL,
    session_token text NOT NULL,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: landing_hunt_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.landing_hunt_sessions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: landing_hunt_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.landing_hunt_sessions_id_seq OWNED BY public.landing_hunt_sessions.id;


--
-- Name: lesson_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lesson_tasks (
    lesson_id bigint NOT NULL,
    task_id bigint NOT NULL,
    order_index integer DEFAULT 0 NOT NULL
);


--
-- Name: lessons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lessons (
    id bigint NOT NULL,
    course_id bigint NOT NULL,
    module_id bigint,
    title text NOT NULL,
    slug text,
    content text,
    difficulty integer,
    estimated_minutes integer
);


--
-- Name: lessons_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lessons_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lessons_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lessons_id_seq OWNED BY public.lessons.id;


--
-- Name: llm_generations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_generations (
    id bigint NOT NULL,
    model text NOT NULL,
    purpose text NOT NULL,
    input_payload jsonb NOT NULL,
    output_payload jsonb,
    kb_entry_id bigint,
    task_id bigint,
    created_by bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: llm_generations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_generations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_generations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_generations_id_seq OWNED BY public.llm_generations.id;


--
-- Name: nvd_sync_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.nvd_sync_log (
    id bigint NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL,
    window_start timestamp with time zone,
    window_end timestamp with time zone,
    inserted_count integer,
    status text DEFAULT 'success'::text NOT NULL,
    error text,
    fetched_count integer,
    embedding_total integer DEFAULT 0 NOT NULL,
    embedding_completed integer DEFAULT 0 NOT NULL,
    embedding_failed integer DEFAULT 0 NOT NULL,
    translation_total integer DEFAULT 0 NOT NULL,
    translation_completed integer DEFAULT 0 NOT NULL,
    translation_failed integer DEFAULT 0 NOT NULL,
    total_to_fetch integer DEFAULT 0 NOT NULL,
    detailed_status text,
    event_log text
);


--
-- Name: COLUMN nvd_sync_log.translation_total; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.nvd_sync_log.translation_total IS 'Total number of kb_entries requiring translation';


--
-- Name: COLUMN nvd_sync_log.translation_completed; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.nvd_sync_log.translation_completed IS 'Number of entries successfully translated to Russian';


--
-- Name: COLUMN nvd_sync_log.translation_failed; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.nvd_sync_log.translation_failed IS 'Number of entries that failed translation';


--
-- Name: COLUMN nvd_sync_log.total_to_fetch; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.nvd_sync_log.total_to_fetch IS 'Total records reported by NVD for the time window';


--
-- Name: COLUMN nvd_sync_log.detailed_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.nvd_sync_log.detailed_status IS 'Human-readable status for the admin panel';


--
-- Name: nvd_sync_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.nvd_sync_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nvd_sync_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.nvd_sync_log_id_seq OWNED BY public.nvd_sync_log.id;


--
-- Name: practice_task_starts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.practice_task_starts (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    task_id bigint NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: practice_task_starts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.practice_task_starts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: practice_task_starts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.practice_task_starts_id_seq OWNED BY public.practice_task_starts.id;


--
-- Name: promo_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.promo_codes (
    id bigint NOT NULL,
    code text NOT NULL,
    source text NOT NULL,
    reward_points integer DEFAULT 0 NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    issued_hunt_session_id bigint,
    redeemed_by_user_id bigint,
    redeemed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: promo_codes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.promo_codes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: promo_codes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.promo_codes_id_seq OWNED BY public.promo_codes.id;


--
-- Name: prompt_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompt_templates (
    code text NOT NULL,
    title text NOT NULL,
    description text,
    content text NOT NULL,
    updated_by bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: submissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.submissions (
    id bigint NOT NULL,
    contest_id bigint,
    task_id bigint NOT NULL,
    user_id bigint NOT NULL,
    flag_id text NOT NULL,
    submitted_value text NOT NULL,
    is_correct boolean NOT NULL,
    awarded_points integer DEFAULT 0 NOT NULL,
    submitted_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: submissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.submissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: submissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.submissions_id_seq OWNED BY public.submissions.id;


--
-- Name: tariff_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tariff_plans (
    id bigint NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    monthly_price_rub numeric(10,2) DEFAULT 0 NOT NULL,
    description text,
    limits jsonb DEFAULT '{}'::jsonb,
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: tariff_plans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tariff_plans_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tariff_plans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tariff_plans_id_seq OWNED BY public.tariff_plans.id;


--
-- Name: task_author_solutions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_author_solutions (
    task_id bigint NOT NULL,
    summary text,
    steps jsonb,
    difficulty_rationale text,
    implementation_notes text,
    creation_solution text
);


--
-- Name: task_chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_chat_messages (
    id bigint NOT NULL,
    session_id bigint NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT task_chat_messages_role_check CHECK ((role = ANY (ARRAY['user'::text, 'assistant'::text])))
);


--
-- Name: task_chat_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.task_chat_messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: task_chat_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.task_chat_messages_id_seq OWNED BY public.task_chat_messages.id;


--
-- Name: task_chat_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_chat_sessions (
    id bigint NOT NULL,
    task_id bigint NOT NULL,
    user_id bigint NOT NULL,
    contest_id bigint,
    status text DEFAULT 'active'::text NOT NULL,
    flag_seed text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    last_activity_at timestamp with time zone DEFAULT now() NOT NULL,
    solved_at timestamp with time zone,
    CONSTRAINT task_chat_sessions_status_check CHECK ((status = ANY (ARRAY['active'::text, 'solved'::text])))
);


--
-- Name: task_chat_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.task_chat_sessions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: task_chat_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.task_chat_sessions_id_seq OWNED BY public.task_chat_sessions.id;


--
-- Name: task_flags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_flags (
    id bigint NOT NULL,
    task_id bigint NOT NULL,
    flag_id text NOT NULL,
    format text NOT NULL,
    expected_value text,
    description text
);


--
-- Name: task_flags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.task_flags_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: task_flags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.task_flags_id_seq OWNED BY public.task_flags.id;


--
-- Name: task_materials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_materials (
    id bigint NOT NULL,
    task_id bigint NOT NULL,
    type text NOT NULL,
    name text NOT NULL,
    description text,
    url text,
    storage_key text,
    meta jsonb DEFAULT '{}'::jsonb
);


--
-- Name: task_materials_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.task_materials_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: task_materials_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.task_materials_id_seq OWNED BY public.task_materials.id;


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tasks (
    id bigint NOT NULL,
    title text NOT NULL,
    category text NOT NULL,
    difficulty integer NOT NULL,
    points integer DEFAULT 100 NOT NULL,
    tags text[] DEFAULT '{}'::text[],
    language text DEFAULT 'ru'::text NOT NULL,
    story text,
    participant_description text,
    state text DEFAULT 'draft'::text NOT NULL,
    kb_entry_id bigint,
    llm_raw_response jsonb,
    created_by bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    task_kind text DEFAULT 'contest'::text NOT NULL,
    access_type text DEFAULT 'just_flag'::text NOT NULL,
    chat_system_prompt_template text,
    chat_user_message_max_chars integer DEFAULT 150 NOT NULL,
    chat_model_max_output_tokens integer DEFAULT 256 NOT NULL,
    chat_session_ttl_minutes integer DEFAULT 180 NOT NULL,
    embedding public.vector(256),
    parent_id bigint,
    CONSTRAINT tasks_access_type_check CHECK ((access_type = ANY (ARRAY['vpn'::text, 'vm'::text, 'link'::text, 'file'::text, 'chat'::text, 'just_flag'::text]))),
    CONSTRAINT tasks_chat_model_max_output_tokens_check CHECK (((chat_model_max_output_tokens >= 32) AND (chat_model_max_output_tokens <= 1024))),
    CONSTRAINT tasks_chat_prompt_template_required_check CHECK (((access_type <> 'chat'::text) OR ((chat_system_prompt_template IS NOT NULL) AND (POSITION(('{{FLAG}}'::text) IN (chat_system_prompt_template)) > 0)))),
    CONSTRAINT tasks_chat_session_ttl_minutes_check CHECK (((chat_session_ttl_minutes >= 15) AND (chat_session_ttl_minutes <= 720))),
    CONSTRAINT tasks_chat_user_message_max_chars_check CHECK (((chat_user_message_max_chars >= 20) AND (chat_user_message_max_chars <= 500)))
);


--
-- Name: tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tasks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tasks_id_seq OWNED BY public.tasks.id;


--
-- Name: user_auth_identities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_auth_identities (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    provider text NOT NULL,
    provider_user_id text NOT NULL,
    provider_email text,
    provider_login text,
    provider_avatar_url text,
    raw_profile_json jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_login_at timestamp with time zone
);


--
-- Name: user_auth_identities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_auth_identities_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_auth_identities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_auth_identities_id_seq OWNED BY public.user_auth_identities.id;


--
-- Name: user_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_profiles (
    user_id bigint NOT NULL,
    username text NOT NULL,
    role text DEFAULT 'participant'::text NOT NULL,
    bio text,
    avatar_url text,
    locale text DEFAULT 'ru-RU'::text,
    timezone text DEFAULT 'Europe/Moscow'::text,
    last_login timestamp with time zone,
    onboarding_status text,
    sub_request boolean DEFAULT false NOT NULL
);


--
-- Name: user_ratings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_ratings (
    user_id bigint NOT NULL,
    contest_rating integer DEFAULT 0 NOT NULL,
    practice_rating integer DEFAULT 0 NOT NULL,
    last_updated_at timestamp with time zone DEFAULT now() NOT NULL,
    first_blood integer DEFAULT 0 NOT NULL,
    CONSTRAINT user_ratings_first_blood_check CHECK ((first_blood >= 0))
);


--
-- Name: user_registration_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_registration_data (
    user_id bigint NOT NULL,
    registration_source text NOT NULL,
    terms_accepted_at timestamp with time zone NOT NULL,
    marketing_opt_in boolean DEFAULT false NOT NULL,
    marketing_opt_in_at timestamp with time zone,
    profession_tags text[] DEFAULT '{}'::text[] NOT NULL,
    grade text,
    interest_tags text[] DEFAULT '{}'::text[] NOT NULL,
    questionnaire_completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_tariffs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_tariffs (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    tariff_id bigint NOT NULL,
    is_promo boolean DEFAULT false NOT NULL,
    source text,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone
);


--
-- Name: user_tariffs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_tariffs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_tariffs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_tariffs_id_seq OWNED BY public.user_tariffs.id;


--
-- Name: user_task_variant_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_task_variant_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    parent_task_id bigint NOT NULL,
    user_id bigint NOT NULL,
    user_request text NOT NULL,
    sanitized_request text,
    status text DEFAULT 'pending'::text NOT NULL,
    generated_variant_id uuid,
    failure_reason text,
    rejection_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone
);


--
-- Name: TABLE user_task_variant_requests; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.user_task_variant_requests IS 'User requests for generating task variants';


--
-- Name: COLUMN user_task_variant_requests.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_task_variant_requests.status IS 'pending, generating, completed, failed';


--
-- Name: user_task_variant_votes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_task_variant_votes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    variant_id uuid NOT NULL,
    user_id bigint NOT NULL,
    vote_type text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT user_task_variant_votes_vote_type_check CHECK ((vote_type = ANY (ARRAY['upvote'::text, 'downvote'::text])))
);


--
-- Name: TABLE user_task_variant_votes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.user_task_variant_votes IS 'Community votes on user-generated task variants';


--
-- Name: COLUMN user_task_variant_votes.vote_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_task_variant_votes.vote_type IS 'upvote or downvote';


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    email_verified_at timestamp with time zone,
    password_changed_at timestamp with time zone,
    failed_login_attempts integer DEFAULT 0 NOT NULL,
    last_failed_login_at timestamp with time zone
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: v_security_audit; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_security_audit AS
 SELECT id,
    action,
    user_id,
    resource_type,
    resource_id,
    ip_address,
    date_trunc('hour'::text, created_at) AS hour,
    count(*) OVER (PARTITION BY action, ip_address, (date_trunc('hour'::text, created_at))) AS occurrences_in_hour
   FROM public.audit_logs
  WHERE (((action)::text ~~ 'auth.%'::text) OR ((action)::text ~~ 'security.%'::text))
  ORDER BY created_at DESC;


--
-- Name: VIEW v_security_audit; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_security_audit IS 'Aggregated view of security events for monitoring';


--
-- Name: activity_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log ALTER COLUMN id SET DEFAULT nextval('public.activity_log_id_seq'::regclass);


--
-- Name: ai_base_images id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_base_images ALTER COLUMN id SET DEFAULT nextval('public.ai_base_images_id_seq'::regclass);


--
-- Name: ai_generation_analytics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_generation_analytics ALTER COLUMN id SET DEFAULT nextval('public.ai_generation_analytics_id_seq'::regclass);


--
-- Name: ai_xss_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_xss_templates ALTER COLUMN id SET DEFAULT nextval('public.ai_xss_templates_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: auth_password_reset_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_password_reset_tokens ALTER COLUMN id SET DEFAULT nextval('public.auth_password_reset_tokens_id_seq'::regclass);


--
-- Name: auth_refresh_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_refresh_tokens ALTER COLUMN id SET DEFAULT nextval('public.auth_refresh_tokens_id_seq'::regclass);


--
-- Name: auth_registration_flows id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_registration_flows ALTER COLUMN id SET DEFAULT nextval('public.auth_registration_flows_id_seq'::regclass);


--
-- Name: contest_task_ratings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_task_ratings ALTER COLUMN id SET DEFAULT nextval('public.contest_task_ratings_id_seq'::regclass);


--
-- Name: contests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contests ALTER COLUMN id SET DEFAULT nextval('public.contests_id_seq'::regclass);


--
-- Name: course_modules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_modules ALTER COLUMN id SET DEFAULT nextval('public.course_modules_id_seq'::regclass);


--
-- Name: courses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses ALTER COLUMN id SET DEFAULT nextval('public.courses_id_seq'::regclass);


--
-- Name: feedback id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback ALTER COLUMN id SET DEFAULT nextval('public.feedback_id_seq'::regclass);


--
-- Name: kb_comments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_comments ALTER COLUMN id SET DEFAULT nextval('public.kb_comments_id_seq'::regclass);


--
-- Name: kb_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_entries ALTER COLUMN id SET DEFAULT nextval('public.kb_entries_id_seq'::regclass);


--
-- Name: landing_hunt_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.landing_hunt_sessions ALTER COLUMN id SET DEFAULT nextval('public.landing_hunt_sessions_id_seq'::regclass);


--
-- Name: lessons id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons ALTER COLUMN id SET DEFAULT nextval('public.lessons_id_seq'::regclass);


--
-- Name: llm_generations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_generations ALTER COLUMN id SET DEFAULT nextval('public.llm_generations_id_seq'::regclass);


--
-- Name: nvd_sync_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nvd_sync_log ALTER COLUMN id SET DEFAULT nextval('public.nvd_sync_log_id_seq'::regclass);


--
-- Name: practice_task_starts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practice_task_starts ALTER COLUMN id SET DEFAULT nextval('public.practice_task_starts_id_seq'::regclass);


--
-- Name: promo_codes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promo_codes ALTER COLUMN id SET DEFAULT nextval('public.promo_codes_id_seq'::regclass);


--
-- Name: submissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions ALTER COLUMN id SET DEFAULT nextval('public.submissions_id_seq'::regclass);


--
-- Name: tariff_plans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tariff_plans ALTER COLUMN id SET DEFAULT nextval('public.tariff_plans_id_seq'::regclass);


--
-- Name: task_chat_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_chat_messages ALTER COLUMN id SET DEFAULT nextval('public.task_chat_messages_id_seq'::regclass);


--
-- Name: task_chat_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_chat_sessions ALTER COLUMN id SET DEFAULT nextval('public.task_chat_sessions_id_seq'::regclass);


--
-- Name: task_flags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_flags ALTER COLUMN id SET DEFAULT nextval('public.task_flags_id_seq'::regclass);


--
-- Name: task_materials id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_materials ALTER COLUMN id SET DEFAULT nextval('public.task_materials_id_seq'::regclass);


--
-- Name: tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks ALTER COLUMN id SET DEFAULT nextval('public.tasks_id_seq'::regclass);


--
-- Name: user_auth_identities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_auth_identities ALTER COLUMN id SET DEFAULT nextval('public.user_auth_identities_id_seq'::regclass);


--
-- Name: user_tariffs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tariffs ALTER COLUMN id SET DEFAULT nextval('public.user_tariffs_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: activity_log activity_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log
    ADD CONSTRAINT activity_log_pkey PRIMARY KEY (id);


--
-- Name: ai_base_images ai_base_images_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_base_images
    ADD CONSTRAINT ai_base_images_pkey PRIMARY KEY (id);


--
-- Name: ai_generation_analytics ai_generation_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_generation_analytics
    ADD CONSTRAINT ai_generation_analytics_pkey PRIMARY KEY (id);


--
-- Name: ai_generation_analytics ai_generation_analytics_task_type_difficulty_period_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_generation_analytics
    ADD CONSTRAINT ai_generation_analytics_task_type_difficulty_period_date_key UNIQUE (task_type, difficulty, period_date);


--
-- Name: ai_generation_batches ai_generation_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_generation_batches
    ADD CONSTRAINT ai_generation_batches_pkey PRIMARY KEY (id);


--
-- Name: ai_generation_variants ai_generation_variants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_generation_variants
    ADD CONSTRAINT ai_generation_variants_pkey PRIMARY KEY (id);


--
-- Name: ai_xss_templates ai_xss_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_xss_templates
    ADD CONSTRAINT ai_xss_templates_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: auth_password_reset_tokens auth_password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_password_reset_tokens
    ADD CONSTRAINT auth_password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: auth_password_reset_tokens auth_password_reset_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_password_reset_tokens
    ADD CONSTRAINT auth_password_reset_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: auth_refresh_tokens auth_refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: auth_refresh_tokens auth_refresh_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: auth_registration_flows auth_registration_flows_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_registration_flows
    ADD CONSTRAINT auth_registration_flows_pkey PRIMARY KEY (id);


--
-- Name: contest_participants contest_participants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_participants
    ADD CONSTRAINT contest_participants_pkey PRIMARY KEY (contest_id, user_id);


--
-- Name: contest_task_ratings contest_task_ratings_contest_id_task_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_task_ratings
    ADD CONSTRAINT contest_task_ratings_contest_id_task_id_user_id_key UNIQUE (contest_id, task_id, user_id);


--
-- Name: contest_task_ratings contest_task_ratings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_task_ratings
    ADD CONSTRAINT contest_task_ratings_pkey PRIMARY KEY (id);


--
-- Name: contest_tasks contest_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_tasks
    ADD CONSTRAINT contest_tasks_pkey PRIMARY KEY (contest_id, task_id);


--
-- Name: contests contests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contests
    ADD CONSTRAINT contests_pkey PRIMARY KEY (id);


--
-- Name: course_modules course_modules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_modules
    ADD CONSTRAINT course_modules_pkey PRIMARY KEY (id);


--
-- Name: courses courses_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_code_key UNIQUE (code);


--
-- Name: courses courses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_pkey PRIMARY KEY (id);


--
-- Name: kb_comments kb_comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_comments
    ADD CONSTRAINT kb_comments_pkey PRIMARY KEY (id);


--
-- Name: kb_entries kb_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_entries
    ADD CONSTRAINT kb_entries_pkey PRIMARY KEY (id);


--
-- Name: landing_hunt_session_items landing_hunt_session_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.landing_hunt_session_items
    ADD CONSTRAINT landing_hunt_session_items_pkey PRIMARY KEY (session_id, bug_key);


--
-- Name: landing_hunt_sessions landing_hunt_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.landing_hunt_sessions
    ADD CONSTRAINT landing_hunt_sessions_pkey PRIMARY KEY (id);


--
-- Name: landing_hunt_sessions landing_hunt_sessions_session_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.landing_hunt_sessions
    ADD CONSTRAINT landing_hunt_sessions_session_token_key UNIQUE (session_token);


--
-- Name: lesson_tasks lesson_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lesson_tasks
    ADD CONSTRAINT lesson_tasks_pkey PRIMARY KEY (lesson_id, task_id);


--
-- Name: lessons lessons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons
    ADD CONSTRAINT lessons_pkey PRIMARY KEY (id);


--
-- Name: llm_generations llm_generations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_generations
    ADD CONSTRAINT llm_generations_pkey PRIMARY KEY (id);


--
-- Name: nvd_sync_log nvd_sync_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nvd_sync_log
    ADD CONSTRAINT nvd_sync_log_pkey PRIMARY KEY (id);


--
-- Name: practice_task_starts practice_task_starts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practice_task_starts
    ADD CONSTRAINT practice_task_starts_pkey PRIMARY KEY (id);


--
-- Name: promo_codes promo_codes_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promo_codes
    ADD CONSTRAINT promo_codes_code_key UNIQUE (code);


--
-- Name: promo_codes promo_codes_issued_hunt_session_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promo_codes
    ADD CONSTRAINT promo_codes_issued_hunt_session_id_key UNIQUE (issued_hunt_session_id);


--
-- Name: promo_codes promo_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promo_codes
    ADD CONSTRAINT promo_codes_pkey PRIMARY KEY (id);


--
-- Name: prompt_templates prompt_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_pkey PRIMARY KEY (code);


--
-- Name: submissions submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_pkey PRIMARY KEY (id);


--
-- Name: tariff_plans tariff_plans_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tariff_plans
    ADD CONSTRAINT tariff_plans_code_key UNIQUE (code);


--
-- Name: tariff_plans tariff_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tariff_plans
    ADD CONSTRAINT tariff_plans_pkey PRIMARY KEY (id);


--
-- Name: task_author_solutions task_author_solutions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_author_solutions
    ADD CONSTRAINT task_author_solutions_pkey PRIMARY KEY (task_id);


--
-- Name: task_chat_messages task_chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_chat_messages
    ADD CONSTRAINT task_chat_messages_pkey PRIMARY KEY (id);


--
-- Name: task_chat_sessions task_chat_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_chat_sessions
    ADD CONSTRAINT task_chat_sessions_pkey PRIMARY KEY (id);


--
-- Name: task_flags task_flags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_flags
    ADD CONSTRAINT task_flags_pkey PRIMARY KEY (id);


--
-- Name: task_flags task_flags_task_id_flag_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_flags
    ADD CONSTRAINT task_flags_task_id_flag_id_key UNIQUE (task_id, flag_id);


--
-- Name: task_materials task_materials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_materials
    ADD CONSTRAINT task_materials_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: practice_task_starts uq_practice_task_starts_user_task; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practice_task_starts
    ADD CONSTRAINT uq_practice_task_starts_user_task UNIQUE (user_id, task_id);


--
-- Name: user_task_variant_votes uq_variant_user_vote; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_task_variant_votes
    ADD CONSTRAINT uq_variant_user_vote UNIQUE (variant_id, user_id);


--
-- Name: user_auth_identities user_auth_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_auth_identities
    ADD CONSTRAINT user_auth_identities_pkey PRIMARY KEY (id);


--
-- Name: user_profiles user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_pkey PRIMARY KEY (user_id);


--
-- Name: user_profiles user_profiles_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_username_key UNIQUE (username);


--
-- Name: user_ratings user_ratings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_ratings
    ADD CONSTRAINT user_ratings_pkey PRIMARY KEY (user_id);


--
-- Name: user_registration_data user_registration_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_registration_data
    ADD CONSTRAINT user_registration_data_pkey PRIMARY KEY (user_id);


--
-- Name: user_tariffs user_tariffs_one_active; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tariffs
    ADD CONSTRAINT user_tariffs_one_active EXCLUDE USING gist (user_id WITH =, tstzrange(valid_from, COALESCE(valid_to, 'infinity'::timestamp with time zone)) WITH &&);


--
-- Name: user_tariffs user_tariffs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tariffs
    ADD CONSTRAINT user_tariffs_pkey PRIMARY KEY (id);


--
-- Name: user_task_variant_requests user_task_variant_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_task_variant_requests
    ADD CONSTRAINT user_task_variant_requests_pkey PRIMARY KEY (id);


--
-- Name: user_task_variant_votes user_task_variant_votes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_task_variant_votes
    ADD CONSTRAINT user_task_variant_votes_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_activity_log_admin_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_log_admin_id ON public.activity_log USING btree (admin_id);


--
-- Name: idx_activity_log_contest_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_log_contest_created ON public.activity_log USING btree (contest_id, created_at);


--
-- Name: idx_activity_log_contest_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_log_contest_id ON public.activity_log USING btree (contest_id);


--
-- Name: idx_activity_log_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_log_created_at ON public.activity_log USING btree (created_at);


--
-- Name: idx_activity_log_event_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_log_event_created ON public.activity_log USING btree (event_type, created_at);


--
-- Name: idx_activity_log_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_log_event_type ON public.activity_log USING btree (event_type);


--
-- Name: idx_activity_log_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_log_source ON public.activity_log USING btree (source);


--
-- Name: idx_ai_gen_analytics_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_gen_analytics_lookup ON public.ai_generation_analytics USING btree (task_type, difficulty, period_date);


--
-- Name: idx_ai_gen_batches_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_gen_batches_status ON public.ai_generation_batches USING btree (status);


--
-- Name: idx_ai_gen_variants_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_gen_variants_batch ON public.ai_generation_variants USING btree (batch_id);


--
-- Name: idx_ai_gen_variants_embedding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_gen_variants_embedding ON public.ai_generation_variants USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64') WHERE (embedding IS NOT NULL);


--
-- Name: idx_ai_gen_variants_selected; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_gen_variants_selected ON public.ai_generation_variants USING btree (is_selected) WHERE (is_selected = true);


--
-- Name: idx_audit_logs_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_action ON public.audit_logs USING btree (action);


--
-- Name: idx_audit_logs_action_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_action_created ON public.audit_logs USING btree (action, created_at DESC);


--
-- Name: idx_audit_logs_created_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_created_desc ON public.audit_logs USING btree (created_at DESC);


--
-- Name: idx_audit_logs_resource; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_resource ON public.audit_logs USING btree (resource_type, resource_id);


--
-- Name: idx_audit_logs_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_user_created ON public.audit_logs USING btree (user_id, created_at DESC);


--
-- Name: idx_audit_logs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_user_id ON public.audit_logs USING btree (user_id);


--
-- Name: idx_auth_refresh_tokens_active_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_refresh_tokens_active_user ON public.auth_refresh_tokens USING btree (user_id, revoked_at, expires_at);


--
-- Name: idx_auth_refresh_tokens_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_refresh_tokens_expires_at ON public.auth_refresh_tokens USING btree (expires_at);


--
-- Name: idx_auth_refresh_tokens_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_auth_refresh_tokens_hash ON public.auth_refresh_tokens USING btree (token_hash);


--
-- Name: idx_auth_refresh_tokens_user_agent_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_refresh_tokens_user_agent_hash ON public.auth_refresh_tokens USING btree (user_agent_hash);


--
-- Name: idx_auth_registration_flows_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_registration_flows_email ON public.auth_registration_flows USING btree (email);


--
-- Name: idx_auth_registration_flows_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_registration_flows_expires_at ON public.auth_registration_flows USING btree (expires_at);


--
-- Name: idx_auth_registration_flows_magic_link_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_auth_registration_flows_magic_link_hash ON public.auth_registration_flows USING btree (magic_link_token_hash);


--
-- Name: idx_auth_registration_flows_state_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_auth_registration_flows_state_hash ON public.auth_registration_flows USING btree (oauth_state_hash);


--
-- Name: idx_contest_participants_contest_joined; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contest_participants_contest_joined ON public.contest_participants USING btree (contest_id, joined_at);


--
-- Name: idx_contest_tasks_order_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_contest_tasks_order_unique ON public.contest_tasks USING btree (contest_id, order_index);


--
-- Name: idx_feedback_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_feedback_id ON public.feedback USING btree (id);


--
-- Name: idx_kb_comments_entry_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kb_comments_entry_created ON public.kb_comments USING btree (kb_entry_id, created_at DESC);


--
-- Name: idx_kb_comments_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kb_comments_parent ON public.kb_comments USING btree (parent_id);


--
-- Name: idx_kb_comments_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kb_comments_user_created ON public.kb_comments USING btree (user_id, created_at DESC);


--
-- Name: idx_kb_entries_attack_vector; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kb_entries_attack_vector ON public.kb_entries USING btree (attack_vector) WHERE (attack_vector IS NOT NULL);


--
-- Name: idx_kb_entries_cve_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kb_entries_cve_id ON public.kb_entries USING btree (cve_id);


--
-- Name: idx_kb_entries_cvss_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kb_entries_cvss_score ON public.kb_entries USING btree (cvss_base_score) WHERE (cvss_base_score IS NOT NULL);


--
-- Name: idx_kb_entries_cwe_ids_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kb_entries_cwe_ids_gin ON public.kb_entries USING gin (cwe_ids);


--
-- Name: idx_kb_entries_embedding_hnsw; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kb_entries_embedding_hnsw ON public.kb_entries USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_kb_entries_tags_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kb_entries_tags_gin ON public.kb_entries USING gin (tags);


--
-- Name: idx_kb_entries_updated_created_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kb_entries_updated_created_desc ON public.kb_entries USING btree (COALESCE(updated_at, created_at) DESC);


--
-- Name: idx_landing_hunt_session_items_found_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_landing_hunt_session_items_found_at ON public.landing_hunt_session_items USING btree (found_at DESC);


--
-- Name: idx_landing_hunt_sessions_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_landing_hunt_sessions_token ON public.landing_hunt_sessions USING btree (session_token);


--
-- Name: idx_llm_generations_purpose; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_generations_purpose ON public.llm_generations USING btree (purpose);


--
-- Name: idx_nvd_sync_log_fetched_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nvd_sync_log_fetched_at ON public.nvd_sync_log USING btree (fetched_at DESC);


--
-- Name: idx_nvd_sync_log_status_fetched_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nvd_sync_log_status_fetched_at ON public.nvd_sync_log USING btree (status, fetched_at DESC);


--
-- Name: idx_nvd_sync_log_translation_progress; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_nvd_sync_log_translation_progress ON public.nvd_sync_log USING btree (translation_total, translation_completed, translation_failed) WHERE (status = ANY (ARRAY['translating'::text, 'embedding'::text]));


--
-- Name: idx_password_reset_tokens_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_password_reset_tokens_expires_at ON public.auth_password_reset_tokens USING btree (expires_at);


--
-- Name: idx_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_password_reset_tokens_user_id ON public.auth_password_reset_tokens USING btree (user_id);


--
-- Name: idx_promo_codes_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_promo_codes_code ON public.promo_codes USING btree (code);


--
-- Name: idx_promo_codes_issued_hunt_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_promo_codes_issued_hunt_session_id ON public.promo_codes USING btree (issued_hunt_session_id);


--
-- Name: idx_promo_codes_landing_redeemed_user_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_promo_codes_landing_redeemed_user_unique ON public.promo_codes USING btree (redeemed_by_user_id) WHERE ((source = 'landing_hunt'::text) AND (redeemed_by_user_id IS NOT NULL));


--
-- Name: idx_promo_codes_redeemed_by_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_promo_codes_redeemed_by_user_id ON public.promo_codes USING btree (redeemed_by_user_id);


--
-- Name: idx_promo_codes_source_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_promo_codes_source_expires_at ON public.promo_codes USING btree (source, expires_at);


--
-- Name: idx_submissions_contest_correct_submitted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_contest_correct_submitted ON public.submissions USING btree (contest_id, is_correct, submitted_at, id);


--
-- Name: idx_submissions_contest_user_correct; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_contest_user_correct ON public.submissions USING btree (contest_id, user_id, is_correct, submitted_at DESC);


--
-- Name: idx_submissions_correct_contest_user_task; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_correct_contest_user_task ON public.submissions USING btree (contest_id, is_correct, user_id, task_id);


--
-- Name: idx_submissions_correct_user_task_practice; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_correct_user_task_practice ON public.submissions USING btree (user_id, task_id) WHERE ((contest_id IS NULL) AND (is_correct = true));


--
-- Name: idx_submissions_practice_task_user_flag_correct; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_practice_task_user_flag_correct ON public.submissions USING btree (task_id, user_id, flag_id) WHERE ((contest_id IS NULL) AND (is_correct = true));


--
-- Name: idx_submissions_practice_user_task_all; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_practice_user_task_all ON public.submissions USING btree (user_id, task_id) WHERE (contest_id IS NULL);


--
-- Name: idx_submissions_user_contest; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_user_contest ON public.submissions USING btree (user_id, contest_id);


--
-- Name: idx_task_chat_messages_session_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_task_chat_messages_session_created ON public.task_chat_messages USING btree (session_id, created_at, id);


--
-- Name: idx_task_chat_sessions_active_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_task_chat_sessions_active_unique ON public.task_chat_sessions USING btree (task_id, user_id, COALESCE(contest_id, (0)::bigint)) WHERE (status = 'active'::text);


--
-- Name: idx_task_chat_sessions_expiry_unsolved; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_task_chat_sessions_expiry_unsolved ON public.task_chat_sessions USING btree (expires_at) WHERE (status = 'active'::text);


--
-- Name: idx_task_chat_sessions_task_user_context; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_task_chat_sessions_task_user_context ON public.task_chat_sessions USING btree (task_id, user_id, contest_id);


--
-- Name: idx_task_flags_task_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_task_flags_task_id ON public.task_flags USING btree (task_id, id);


--
-- Name: idx_task_materials_task_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_task_materials_task_id ON public.task_materials USING btree (task_id, id);


--
-- Name: idx_tasks_embedding_hnsw; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tasks_embedding_hnsw ON public.tasks USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_tasks_parent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tasks_parent_id ON public.tasks USING btree (parent_id);


--
-- Name: idx_tasks_practice_ready_category_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tasks_practice_ready_category_created ON public.tasks USING btree (task_kind, state, lower(category), created_at DESC, id DESC);


--
-- Name: idx_tasks_practice_ready_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tasks_practice_ready_created ON public.tasks USING btree (task_kind, state, created_at DESC, id DESC);


--
-- Name: idx_tasks_practice_ready_difficulty_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tasks_practice_ready_difficulty_created ON public.tasks USING btree (task_kind, state, difficulty, created_at DESC, id DESC);


--
-- Name: idx_tasks_tags_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tasks_tags_gin ON public.tasks USING gin (tags);


--
-- Name: idx_user_auth_identities_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_auth_identities_email ON public.user_auth_identities USING btree (provider_email);


--
-- Name: idx_user_auth_identities_provider_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_user_auth_identities_provider_subject ON public.user_auth_identities USING btree (provider, provider_user_id);


--
-- Name: idx_user_auth_identities_user_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_user_auth_identities_user_provider ON public.user_auth_identities USING btree (user_id, provider);


--
-- Name: idx_user_profiles_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_profiles_username ON public.user_profiles USING btree (username);


--
-- Name: idx_user_profiles_username_lower; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_profiles_username_lower ON public.user_profiles USING btree (lower(username));


--
-- Name: idx_user_ratings_contest_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_ratings_contest_order ON public.user_ratings USING btree (contest_rating DESC, first_blood DESC, user_id);


--
-- Name: idx_user_ratings_practice_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_ratings_practice_order ON public.user_ratings USING btree (practice_rating DESC, first_blood DESC, user_id);


--
-- Name: idx_user_registration_data_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_registration_data_source ON public.user_registration_data USING btree (registration_source);


--
-- Name: idx_user_variant_requests_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_variant_requests_created ON public.user_task_variant_requests USING btree (created_at DESC);


--
-- Name: idx_user_variant_requests_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_variant_requests_parent ON public.user_task_variant_requests USING btree (parent_task_id);


--
-- Name: idx_user_variant_requests_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_variant_requests_status ON public.user_task_variant_requests USING btree (status);


--
-- Name: idx_user_variant_requests_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_variant_requests_user ON public.user_task_variant_requests USING btree (user_id);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: idx_users_failed_login; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_failed_login ON public.users USING btree (failed_login_attempts) WHERE (failed_login_attempts > 0);


--
-- Name: idx_users_password_changed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_password_changed ON public.users USING btree (password_changed_at);


--
-- Name: idx_variant_votes_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_variant_votes_user ON public.user_task_variant_votes USING btree (user_id);


--
-- Name: idx_variant_votes_variant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_variant_votes_variant ON public.user_task_variant_votes USING btree (variant_id);


--
-- Name: users trg_users_email_verified_promo; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_users_email_verified_promo AFTER UPDATE OF email_verified_at ON public.users FOR EACH ROW EXECUTE FUNCTION public.grant_early_promo_on_email_verified();


--
-- Name: activity_log activity_log_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log
    ADD CONSTRAINT activity_log_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: activity_log activity_log_contest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log
    ADD CONSTRAINT activity_log_contest_id_fkey FOREIGN KEY (contest_id) REFERENCES public.contests(id) ON DELETE SET NULL;


--
-- Name: ai_generation_batches ai_generation_batches_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_generation_batches
    ADD CONSTRAINT ai_generation_batches_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.users(id);


--
-- Name: ai_generation_variants ai_generation_variants_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_generation_variants
    ADD CONSTRAINT ai_generation_variants_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.ai_generation_batches(id) ON DELETE CASCADE;


--
-- Name: ai_generation_variants ai_generation_variants_published_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_generation_variants
    ADD CONSTRAINT ai_generation_variants_published_task_id_fkey FOREIGN KEY (published_task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: auth_password_reset_tokens auth_password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_password_reset_tokens
    ADD CONSTRAINT auth_password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: auth_refresh_tokens auth_refresh_tokens_rotated_to_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_rotated_to_id_fkey FOREIGN KEY (rotated_to_id) REFERENCES public.auth_refresh_tokens(id) ON DELETE SET NULL;


--
-- Name: auth_refresh_tokens auth_refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: auth_registration_flows auth_registration_flows_completed_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_registration_flows
    ADD CONSTRAINT auth_registration_flows_completed_user_id_fkey FOREIGN KEY (completed_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: contest_participants contest_participants_contest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_participants
    ADD CONSTRAINT contest_participants_contest_id_fkey FOREIGN KEY (contest_id) REFERENCES public.contests(id) ON DELETE CASCADE;


--
-- Name: contest_participants contest_participants_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_participants
    ADD CONSTRAINT contest_participants_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: contest_task_ratings contest_task_ratings_contest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_task_ratings
    ADD CONSTRAINT contest_task_ratings_contest_id_fkey FOREIGN KEY (contest_id) REFERENCES public.contests(id) ON DELETE CASCADE;


--
-- Name: contest_task_ratings contest_task_ratings_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_task_ratings
    ADD CONSTRAINT contest_task_ratings_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: contest_task_ratings contest_task_ratings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_task_ratings
    ADD CONSTRAINT contest_task_ratings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: contest_tasks contest_tasks_contest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_tasks
    ADD CONSTRAINT contest_tasks_contest_id_fkey FOREIGN KEY (contest_id) REFERENCES public.contests(id) ON DELETE CASCADE;


--
-- Name: contest_tasks contest_tasks_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contest_tasks
    ADD CONSTRAINT contest_tasks_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id);


--
-- Name: course_modules course_modules_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_modules
    ADD CONSTRAINT course_modules_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: feedback feedback_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feedback
    ADD CONSTRAINT feedback_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: kb_comments kb_comments_kb_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_comments
    ADD CONSTRAINT kb_comments_kb_entry_id_fkey FOREIGN KEY (kb_entry_id) REFERENCES public.kb_entries(id) ON DELETE CASCADE;


--
-- Name: kb_comments kb_comments_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_comments
    ADD CONSTRAINT kb_comments_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.kb_comments(id) ON DELETE CASCADE;


--
-- Name: kb_comments kb_comments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kb_comments
    ADD CONSTRAINT kb_comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: landing_hunt_session_items landing_hunt_session_items_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.landing_hunt_session_items
    ADD CONSTRAINT landing_hunt_session_items_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.landing_hunt_sessions(id) ON DELETE CASCADE;


--
-- Name: lesson_tasks lesson_tasks_lesson_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lesson_tasks
    ADD CONSTRAINT lesson_tasks_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES public.lessons(id) ON DELETE CASCADE;


--
-- Name: lesson_tasks lesson_tasks_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lesson_tasks
    ADD CONSTRAINT lesson_tasks_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id);


--
-- Name: lessons lessons_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons
    ADD CONSTRAINT lessons_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: lessons lessons_module_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lessons
    ADD CONSTRAINT lessons_module_id_fkey FOREIGN KEY (module_id) REFERENCES public.course_modules(id);


--
-- Name: llm_generations llm_generations_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_generations
    ADD CONSTRAINT llm_generations_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: llm_generations llm_generations_kb_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_generations
    ADD CONSTRAINT llm_generations_kb_entry_id_fkey FOREIGN KEY (kb_entry_id) REFERENCES public.kb_entries(id);


--
-- Name: llm_generations llm_generations_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_generations
    ADD CONSTRAINT llm_generations_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id);


--
-- Name: practice_task_starts practice_task_starts_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practice_task_starts
    ADD CONSTRAINT practice_task_starts_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: practice_task_starts practice_task_starts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practice_task_starts
    ADD CONSTRAINT practice_task_starts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: promo_codes promo_codes_issued_hunt_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promo_codes
    ADD CONSTRAINT promo_codes_issued_hunt_session_id_fkey FOREIGN KEY (issued_hunt_session_id) REFERENCES public.landing_hunt_sessions(id) ON DELETE SET NULL;


--
-- Name: promo_codes promo_codes_redeemed_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promo_codes
    ADD CONSTRAINT promo_codes_redeemed_by_user_id_fkey FOREIGN KEY (redeemed_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: prompt_templates prompt_templates_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: submissions submissions_contest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_contest_id_fkey FOREIGN KEY (contest_id) REFERENCES public.contests(id) ON DELETE CASCADE;


--
-- Name: submissions submissions_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: submissions submissions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: task_author_solutions task_author_solutions_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_author_solutions
    ADD CONSTRAINT task_author_solutions_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_chat_messages task_chat_messages_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_chat_messages
    ADD CONSTRAINT task_chat_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.task_chat_sessions(id) ON DELETE CASCADE;


--
-- Name: task_chat_sessions task_chat_sessions_contest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_chat_sessions
    ADD CONSTRAINT task_chat_sessions_contest_id_fkey FOREIGN KEY (contest_id) REFERENCES public.contests(id) ON DELETE CASCADE;


--
-- Name: task_chat_sessions task_chat_sessions_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_chat_sessions
    ADD CONSTRAINT task_chat_sessions_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_chat_sessions task_chat_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_chat_sessions
    ADD CONSTRAINT task_chat_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: task_flags task_flags_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_flags
    ADD CONSTRAINT task_flags_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: task_materials task_materials_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_materials
    ADD CONSTRAINT task_materials_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: tasks tasks_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: tasks tasks_kb_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_kb_entry_id_fkey FOREIGN KEY (kb_entry_id) REFERENCES public.kb_entries(id);


--
-- Name: tasks tasks_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.tasks(id) ON DELETE SET NULL;


--
-- Name: user_auth_identities user_auth_identities_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_auth_identities
    ADD CONSTRAINT user_auth_identities_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_profiles user_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_ratings user_ratings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_ratings
    ADD CONSTRAINT user_ratings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_registration_data user_registration_data_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_registration_data
    ADD CONSTRAINT user_registration_data_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_tariffs user_tariffs_tariff_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tariffs
    ADD CONSTRAINT user_tariffs_tariff_id_fkey FOREIGN KEY (tariff_id) REFERENCES public.tariff_plans(id);


--
-- Name: user_tariffs user_tariffs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tariffs
    ADD CONSTRAINT user_tariffs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_task_variant_requests user_task_variant_requests_generated_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_task_variant_requests
    ADD CONSTRAINT user_task_variant_requests_generated_variant_id_fkey FOREIGN KEY (generated_variant_id) REFERENCES public.ai_generation_variants(id) ON DELETE CASCADE;


--
-- Name: user_task_variant_requests user_task_variant_requests_parent_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_task_variant_requests
    ADD CONSTRAINT user_task_variant_requests_parent_task_id_fkey FOREIGN KEY (parent_task_id) REFERENCES public.tasks(id) ON DELETE CASCADE;


--
-- Name: user_task_variant_requests user_task_variant_requests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_task_variant_requests
    ADD CONSTRAINT user_task_variant_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_task_variant_votes user_task_variant_votes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_task_variant_votes
    ADD CONSTRAINT user_task_variant_votes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_task_variant_votes user_task_variant_votes_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_task_variant_votes
    ADD CONSTRAINT user_task_variant_votes_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.ai_generation_variants(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict USD7DJhMROKtvNj69onx1JWvblU1M2OuT6uQgi1dNkEmI1b9MsGGBZXLp4iddPN

