"""convert columns to postgres enum types

Revision ID: a1b2c3d4e5f6
Revises: dc6bb1d26626
Create Date: 2026-09-03 15:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'dc6bb1d26626'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # 1. Create enum types if not exists
        op.execute("""
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
        """)

        # 2. Alter satellites columns
        op.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'satellites' AND column_name = 'status') THEN
                    ALTER TABLE public.satellites ALTER COLUMN status DROP DEFAULT;
                    ALTER TABLE public.satellites ALTER COLUMN status TYPE public.satellite_status 
                    USING (
                        CASE 
                            WHEN lower(status::text) IN ('active', 'degraded', 'inactive', 'decayed') 
                                THEN lower(status::text)::public.satellite_status 
                            ELSE 'active'::public.satellite_status 
                        END
                    );
                    ALTER TABLE public.satellites ALTER COLUMN status SET DEFAULT 'active'::public.satellite_status;
                END IF;

                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'satellites' AND column_name = 'object_type') THEN
                    ALTER TABLE public.satellites ALTER COLUMN object_type DROP DEFAULT;
                    ALTER TABLE public.satellites ALTER COLUMN object_type TYPE public.object_type 
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
        """)

        # 3. Alter conjunction_events columns
        op.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'conjunction_events' AND column_name = 'risk_level') THEN
                    ALTER TABLE public.conjunction_events ALTER COLUMN risk_level TYPE public.risk_level 
                    USING (
                        CASE 
                            WHEN lower(risk_level::text) IN ('low', 'medium', 'high', 'critical') 
                                THEN lower(risk_level::text)::public.risk_level 
                            ELSE 'low'::public.risk_level 
                        END
                    );
                END IF;

                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'conjunction_events' AND column_name = 'status') THEN
                    ALTER TABLE public.conjunction_events ALTER COLUMN status DROP DEFAULT;
                    ALTER TABLE public.conjunction_events ALTER COLUMN status TYPE public.alert_status 
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
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("""
            ALTER TABLE public.satellites ALTER COLUMN status TYPE text USING status::text;
            ALTER TABLE public.satellites ALTER COLUMN object_type TYPE text USING object_type::text;
            ALTER TABLE public.conjunction_events ALTER COLUMN risk_level TYPE text USING risk_level::text;
            ALTER TABLE public.conjunction_events ALTER COLUMN status TYPE text USING status::text;
        """)
