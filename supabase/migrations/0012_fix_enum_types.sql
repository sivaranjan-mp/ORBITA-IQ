-- ============================================================================
-- Satellite Operations & Conjunction Intelligence Dashboard
-- Migration: 0012_fix_enum_types.sql
-- Scope: Safely create enum types if missing and convert table columns
--        (status, object_type, risk_level, alert_status, alert_state)
--        from text/varchar to PostgreSQL native enums with fallbacks.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Create Enum Types if they do not exist
-- ----------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'satellite_status') then
    create type public.satellite_status as enum ('active', 'degraded', 'inactive', 'decayed');
  end if;
  
  if not exists (select 1 from pg_type where typname = 'object_type') then
    create type public.object_type as enum ('payload', 'debris', 'rocket_body', 'unknown');
  end if;

  if not exists (select 1 from pg_type where typname = 'risk_level') then
    create type public.risk_level as enum ('low', 'medium', 'high', 'critical');
  end if;

  if not exists (select 1 from pg_type where typname = 'alert_status') then
    create type public.alert_status as enum ('open', 'monitoring', 'resolved', 'dismissed');
  end if;

  if not exists (select 1 from pg_type where typname = 'alert_state') then
    create type public.alert_state as enum ('active', 'acknowledged', 'resolved');
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- 2. Alter satellites table columns (status, object_type)
-- ----------------------------------------------------------------------------
do $$
begin
  if exists (
    select 1 from information_schema.columns 
    where table_schema = 'public' and table_name = 'satellites' and column_name = 'status'
  ) then
    -- Drop default constraint before type alteration
    alter table public.satellites alter column status drop default;
    
    -- Alter status type with safe fallback
    alter table public.satellites 
      alter column status type public.satellite_status 
      using (
        case 
          when lower(status::text) in ('active', 'degraded', 'inactive', 'decayed') 
            then lower(status::text)::public.satellite_status 
          else 'active'::public.satellite_status 
        end
      );
      
    -- Re-apply default
    alter table public.satellites alter column status set default 'active'::public.satellite_status;
  end if;

  if exists (
    select 1 from information_schema.columns 
    where table_schema = 'public' and table_name = 'satellites' and column_name = 'object_type'
  ) then
    alter table public.satellites alter column object_type drop default;
    
    alter table public.satellites 
      alter column object_type type public.object_type 
      using (
        case 
          when lower(object_type::text) in ('payload', 'debris', 'rocket_body', 'unknown') 
            then lower(object_type::text)::public.object_type 
          else 'unknown'::public.object_type 
        end
      );
      
    alter table public.satellites alter column object_type set default 'payload'::public.object_type;
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- 3. Alter conjunction_events table columns (risk_level, status)
-- ----------------------------------------------------------------------------
do $$
begin
  if exists (
    select 1 from information_schema.columns 
    where table_schema = 'public' and table_name = 'conjunction_events' and column_name = 'risk_level'
  ) then
    alter table public.conjunction_events 
      alter column risk_level type public.risk_level 
      using (
        case 
          when lower(risk_level::text) in ('low', 'medium', 'high', 'critical') 
            then lower(risk_level::text)::public.risk_level 
          else 'low'::public.risk_level 
        end
      );
  end if;

  if exists (
    select 1 from information_schema.columns 
    where table_schema = 'public' and table_name = 'conjunction_events' and column_name = 'status'
  ) then
    alter table public.conjunction_events alter column status drop default;
    
    alter table public.conjunction_events 
      alter column status type public.alert_status 
      using (
        case 
          when lower(status::text) in ('open', 'monitoring', 'resolved', 'dismissed') 
            then lower(status::text)::public.alert_status 
          else 'open'::public.alert_status 
        end
      );
      
    alter table public.conjunction_events alter column status set default 'open'::public.alert_status;
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- 4. Alter alerts table columns (risk_level, status) if table exists
-- ----------------------------------------------------------------------------
do $$
begin
  if exists (
    select 1 from information_schema.tables 
    where table_schema = 'public' and table_name = 'alerts'
  ) then
    if exists (
      select 1 from information_schema.columns 
      where table_schema = 'public' and table_name = 'alerts' and column_name = 'risk_level'
    ) then
      alter table public.alerts 
        alter column risk_level type public.risk_level 
        using (
          case 
            when lower(risk_level::text) in ('low', 'medium', 'high', 'critical') 
              then lower(risk_level::text)::public.risk_level 
            else 'low'::public.risk_level 
          end
        );
    end if;

    if exists (
      select 1 from information_schema.columns 
      where table_schema = 'public' and table_name = 'alerts' and column_name = 'status'
    ) then
      alter table public.alerts alter column status drop default;
      
      alter table public.alerts 
        alter column status type public.alert_state 
        using (
          case 
            when lower(status::text) in ('active', 'acknowledged', 'resolved') 
              then lower(status::text)::public.alert_state 
            else 'active'::public.alert_state 
          end
        );
        
      alter table public.alerts alter column status set default 'active'::public.alert_state;
    end if;
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- 5. Alter conjunction_alerts table columns (risk_level, status) if table exists
-- ----------------------------------------------------------------------------
do $$
begin
  if exists (
    select 1 from information_schema.tables 
    where table_schema = 'public' and table_name = 'conjunction_alerts'
  ) then
    if exists (
      select 1 from information_schema.columns 
      where table_schema = 'public' and table_name = 'conjunction_alerts' and column_name = 'risk_level'
    ) then
      alter table public.conjunction_alerts alter column risk_level drop default;
      
      alter table public.conjunction_alerts 
        alter column risk_level type public.risk_level 
        using (
          case 
            when lower(risk_level::text) in ('low', 'medium', 'high', 'critical') 
              then lower(risk_level::text)::public.risk_level 
            else 'low'::public.risk_level 
          end
        );
        
      alter table public.conjunction_alerts alter column risk_level set default 'low'::public.risk_level;
    end if;

    if exists (
      select 1 from information_schema.columns 
      where table_schema = 'public' and table_name = 'conjunction_alerts' and column_name = 'status'
    ) then
      alter table public.conjunction_alerts alter column status drop default;
      
      alter table public.conjunction_alerts 
        alter column status type public.alert_status 
        using (
          case 
            when lower(status::text) in ('open', 'monitoring', 'resolved', 'dismissed') 
              then lower(status::text)::public.alert_status 
            else 'open'::public.alert_status 
          end
        );
        
      alter table public.conjunction_alerts alter column status set default 'open'::public.alert_status;
    end if;
  end if;
end$$;

-- ----------------------------------------------------------------------------
-- 6. Alter alert_history table columns (risk_level) if table exists
-- ----------------------------------------------------------------------------
do $$
begin
  if exists (
    select 1 from information_schema.tables 
    where table_schema = 'public' and table_name = 'alert_history'
  ) then
    if exists (
      select 1 from information_schema.columns 
      where table_schema = 'public' and table_name = 'alert_history' and column_name = 'risk_level'
    ) then
      alter table public.alert_history 
        alter column risk_level type public.risk_level 
        using (
          case 
            when lower(risk_level::text) in ('low', 'medium', 'high', 'critical') 
              then lower(risk_level::text)::public.risk_level 
            else 'low'::public.risk_level 
          end
        );
    end if;
  end if;
end$$;
