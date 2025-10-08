"""
Admin API endpoints for viewing OpenAI API request logs
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.database.connection import db
from app.api.admin.auth import admin_required

router = APIRouter()


class APILogResponse(BaseModel):
    id: int
    created_at: datetime
    user_id: Optional[int]
    persona: Optional[str]
    operation: str
    curl_command: str
    response_status: Optional[int]
    response_time_ms: Optional[int]
    error_message: Optional[str]
    metadata: Optional[dict]


@router.get("/admin/api-logs", dependencies=[admin_required])
async def get_api_logs(
    limit: int = Query(50, ge=1, le=500),
    operation: Optional[str] = None,
    user_id: Optional[int] = None,
    persona: Optional[str] = None
):
    """
    Get recent OpenAI API request logs with curl commands

    Query parameters:
    - limit: Number of logs to return (default 50, max 500)
    - operation: Filter by operation type (add_message, create_run, etc)
    - user_id: Filter by user ID
    - persona: Filter by persona (admin/oracle)
    """
    try:
        # Build query with filters
        query = """
            SELECT
                id,
                created_at,
                user_id,
                persona,
                operation,
                curl_command,
                response_status,
                response_time_ms,
                error_message,
                metadata
            FROM api_request_logs
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if operation:
            query += f" AND operation = ${param_idx}"
            params.append(operation)
            param_idx += 1

        if user_id:
            query += f" AND user_id = ${param_idx}"
            params.append(user_id)
            param_idx += 1

        if persona:
            query += f" AND persona = ${param_idx}"
            params.append(persona)
            param_idx += 1

        query += f" ORDER BY created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        rows = await db.fetch(query, *params)

        logs = []
        for row in rows:
            logs.append({
                "id": row['id'],
                "created_at": row['created_at'].isoformat(),
                "user_id": row['user_id'],
                "persona": row['persona'],
                "operation": row['operation'],
                "curl_command": row['curl_command'],
                "response_status": row['response_status'],
                "response_time_ms": row['response_time_ms'],
                "error_message": row['error_message'],
                "metadata": row['metadata']
            })

        return {
            "logs": logs,
            "count": len(logs)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching API logs: {str(e)}")


@router.get("/admin/api-logs/{log_id}", dependencies=[admin_required])
async def get_api_log(log_id: int):
    """
    Get single API log by ID with full curl command
    """
    try:
        row = await db.fetchrow("""
            SELECT *
            FROM api_request_logs
            WHERE id = $1
        """, log_id)

        if not row:
            raise HTTPException(status_code=404, detail="Log not found")

        return {
            "id": row['id'],
            "created_at": row['created_at'].isoformat(),
            "user_id": row['user_id'],
            "persona": row['persona'],
            "operation": row['operation'],
            "curl_command": row['curl_command'],
            "response_status": row['response_status'],
            "response_time_ms": row['response_time_ms'],
            "error_message": row['error_message'],
            "metadata": row['metadata']
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching API log: {str(e)}")


@router.delete("/admin/api-logs/cleanup", dependencies=[admin_required])
async def cleanup_old_logs(days: int = Query(7, ge=1, le=365)):
    """
    Delete API logs older than specified days
    """
    try:
        result = await db.execute("""
            DELETE FROM api_request_logs
            WHERE created_at < NOW() - INTERVAL '1 day' * $1
        """, days)

        # Extract number of deleted rows from result
        deleted_count = int(result.split()[-1]) if result else 0

        return {
            "message": f"Deleted logs older than {days} days",
            "deleted_count": deleted_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cleaning up logs: {str(e)}")
