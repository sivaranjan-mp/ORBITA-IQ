import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

SELF_HEALING_ENUM_SQL = """
-- 1. Create Enum Types if missing
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'satellite_status') THEN
    CREATE TYPE public.satellite_status AS ENUM ('active', 'degraded', 'inactive', 'decayed');
  END IF;
  
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'object_type') THEN
    CREATE TYPE public.object_type AS ENUM ('payload', 'debris', 'rocket_body', 'unknown');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risk_level') THEN
    CREATE TYPE public.risk_level AS ENUM ('low', 'medium', 'high', 'critical');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_status') THEN
    CREATE TYPE public.alert_status AS ENUM ('open', 'monitoring', 'resolved', 'dismissed');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_state') THEN
    CREATE TYPE public.alert_state AS ENUM ('active', 'acknowledged', 'resolved');
  END IF;
END$$;

-- 2. Alter satellites columns safely
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'satellites' AND column_name = 'status'
  ) THEN
    ALTER TABLE public.satellites ALTER COLUMN status DROP DEFAULT;
    ALTER TABLE public.satellites 
      ALTER COLUMN status TYPE public.satellite_status 
      USING (
        CASE 
          WHEN lower(status::text) IN ('active', 'degraded', 'inactive', 'decayed') 
            THEN lower(status::text)::public.satellite_status 
          ELSE 'active'::public.satellite_status 
        END
      );
    ALTER TABLE public.satellites ALTER COLUMN status SET DEFAULT 'active'::public.satellite_status;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'satellites' AND column_name = 'object_type'
  ) THEN
    ALTER TABLE public.satellites ALTER COLUMN object_type DROP DEFAULT;
    ALTER TABLE public.satellites 
      ALTER COLUMN object_type TYPE public.object_type 
      USING (
        CASE 
          WHEN lower(object_type::text) IN ('payload', 'debris', 'rocket_body', 'unknown') 
            THEN lower(object_type::text)::public.object_type 
          ELSE 'unknown'::public.object_type 
        END
      );
    ALTER TABLE public.satellites ALTER COLUMN object_type SET DEFAULT 'payload'::public.object_type;
  END IF;
END$$;

-- 3. Alter conjunction_events columns safely
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'conjunction_events' AND column_name = 'risk_level'
  ) THEN
    ALTER TABLE public.conjunction_events 
      ALTER COLUMN risk_level TYPE public.risk_level 
      USING (
        CASE 
          WHEN lower(risk_level::text) IN ('low', 'medium', 'high', 'critical') 
            THEN lower(risk_level::text)::public.risk_level 
          ELSE 'low'::public.risk_level 
        END
      );
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'conjunction_events' AND column_name = 'status'
  ) THEN
    ALTER TABLE public.conjunction_events ALTER COLUMN status DROP DEFAULT;
    ALTER TABLE public.conjunction_events 
      ALTER COLUMN status TYPE public.alert_status 
      USING (
        CASE 
          WHEN lower(status::text) IN ('open', 'monitoring', 'resolved', 'dismissed') 
            THEN lower(status::text)::public.alert_status 
          ELSE 'open'::public.alert_status 
        END
      );
    ALTER TABLE public.conjunction_events ALTER COLUMN status SET DEFAULT 'open'::public.alert_status;
  END IF;
END$$;
"""


async def verify_and_heal_schema(engine: AsyncEngine) -> dict:
    """
    Checks database schema on startup to ensure column types match Python ENUM models.
    If schema drift is detected (e.g. satellites.status is text instead of satellite_status enum),
    automatically executes the self-healing migration and verifies the fix.
    """
    results = {
        "status_column_type": None,
        "udt_name": None,
        "healed": False,
        "valid": True,
    }

    try:
        async with engine.connect() as conn:
            # Check if dialect is PostgreSQL
            if engine.dialect.name != "postgresql":
                logger.info("Non-PostgreSQL dialect detected; skipping PostgreSQL enum schema check.")
                return results

            # 1. Query current column type of satellites.status
            query = text("""
                SELECT data_type, udt_name 
                FROM information_schema.columns 
                WHERE table_name = 'satellites' AND column_name = 'status'
            """)
            res = await conn.execute(query)
            row = res.first()

            if row:
                results["status_column_type"] = row[0]
                results["udt_name"] = row[1]
                logger.info(f"Database schema check: satellites.status is data_type='{row[0]}', udt_name='{row[1]}'")

                # If satellites.status is text/varchar instead of satellite_status enum
                if row[0] in ("text", "character varying") or row[1] != "satellite_status":
                    logger.warning(
                        f"SCHEMA DRIFT DETECTED: satellites.status is '{row[0]}' (udt: '{row[1]}'), "
                        f"expected 'USER-DEFINED' (udt: 'satellite_status'). Executing self-healing migration..."
                    )
                    
                    # Execute self-healing migration in separate transaction
                    await conn.execute(text(SELF_HEALING_ENUM_SQL))
                    await conn.commit()
                    results["healed"] = True
                    logger.info("Self-healing migration applied successfully.")

                    # Re-verify
                    recheck_res = await conn.execute(query)
                    recheck_row = recheck_res.first()
                    if recheck_row:
                        results["status_column_type"] = recheck_row[0]
                        results["udt_name"] = recheck_row[1]
                        logger.info(
                            f"Post-heal verification: satellites.status is data_type='{recheck_row[0]}', udt_name='{recheck_row[1]}'"
                        )
            else:
                logger.info("satellites table or status column does not exist yet; skipping enum conversion.")

    except Exception as e:
        logger.exception(f"Error during schema verification and self-healing: {e}")
        results["valid"] = False

    return results
