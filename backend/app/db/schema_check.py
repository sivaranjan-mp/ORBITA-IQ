import logging
from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

# Expected Enum types for database columns
EXPECTED_ENUM_COLUMNS = {
    ("satellites", "status"): "satellite_status",
    ("satellites", "object_type"): "object_type",
    ("conjunction_events", "risk_level"): "risk_level",
    ("conjunction_events", "status"): "alert_status",
}


async def verify_schema(engine: AsyncEngine) -> Dict[str, Any]:
    """
    Read-only database schema verification on startup.
    Inspects column types against expected PostgreSQL ENUM types.
    Logs clear warnings if mismatches are detected without executing ANY runtime DDL.
    
    All schema changes must be applied via reviewed SQL migrations in supabase/migrations/.
    """
    results: Dict[str, Any] = {
        "valid": True,
        "columns_checked": [],
        "mismatches": [],
    }

    try:
        async with engine.connect() as conn:
            # Check if dialect is PostgreSQL
            if engine.dialect.name != "postgresql":
                logger.info(
                    "Non-PostgreSQL dialect detected (%s); skipping PostgreSQL enum schema validation.",
                    engine.dialect.name,
                )
                return results

            # Query column data types and UDT names for verified tables
            query = text("""
                SELECT table_name, column_name, data_type, udt_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                  AND (
                    (table_name = 'satellites' AND column_name IN ('status', 'object_type'))
                    OR (table_name = 'conjunction_events' AND column_name IN ('risk_level', 'status'))
                  )
                ORDER BY table_name, column_name;
            """)
            res = await conn.execute(query)
            rows = res.fetchall()

            found_columns = {}
            for row in rows:
                t_name, c_name, data_type, udt_name = row[0], row[1], row[2], row[3]
                found_columns[(t_name, c_name)] = {
                    "data_type": data_type,
                    "udt_name": udt_name,
                }
                results["columns_checked"].append({
                    "table": t_name,
                    "column": c_name,
                    "data_type": data_type,
                    "udt_name": udt_name,
                })

            for (t_name, c_name), expected_udt in EXPECTED_ENUM_COLUMNS.items():
                if (t_name, c_name) in found_columns:
                    col_info = found_columns[(t_name, c_name)]
                    actual_udt = col_info["udt_name"]
                    actual_data_type = col_info["data_type"]

                    if actual_udt != expected_udt:
                        mismatch_info = {
                            "table": t_name,
                            "column": c_name,
                            "actual_data_type": actual_data_type,
                            "actual_udt": actual_udt,
                            "expected_udt": expected_udt,
                        }
                        results["mismatches"].append(mismatch_info)
                        results["valid"] = False
                        logger.warning(
                            "SCHEMA TYPE MISMATCH: %s.%s has data_type='%s', udt_name='%s', "
                            "expected enum udt='%s'. Automatic runtime DDL is DISABLED. "
                            "Please apply migration from supabase/migrations/ (e.g. 0012_fix_enum_types.sql).",
                            t_name,
                            c_name,
                            actual_data_type,
                            actual_udt,
                            expected_udt,
                        )
                    else:
                        logger.debug(
                            "Schema column verified: %s.%s is '%s' (udt: '%s')",
                            t_name,
                            c_name,
                            actual_data_type,
                            actual_udt,
                        )
                else:
                    logger.info(
                        "Column %s.%s not found in information_schema (table or column may not exist yet).",
                        t_name,
                        c_name,
                    )

            if results["valid"]:
                logger.info(
                    "Database schema enum verification passed (%d columns verified).",
                    len(found_columns),
                )

    except Exception as e:
        logger.warning(f"Database schema verification encountered an issue: {e}")
        results["valid"] = False

    return results


# Backward compatibility alias
async def verify_and_heal_schema(engine: AsyncEngine) -> Dict[str, Any]:
    """Deprecated alias for verify_schema (healing logic removed)."""
    return await verify_schema(engine)
