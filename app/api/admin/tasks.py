from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime
from typing import Optional
import logging
import json

from app.database.connection import db
from app.api.admin.auth import verify_admin_token
from app.api.admin.models import AdminTaskCreate, AdminTaskUpdate

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/admin/tasks")
async def get_admin_tasks(
    _: bool = Depends(verify_admin_token),
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0)
):
    """Get admin tasks list with optional filtering"""
    try:
        where_clauses = []
        params = []
        param_count = 1

        if type:
            where_clauses.append(f"t.type = ${param_count}")
            params.append(type)
            param_count += 1

        if status:
            where_clauses.append(f"t.status = ${param_count}")
            params.append(status)
            param_count += 1

        if user_id:
            where_clauses.append(f"t.user_id = ${param_count}")
            params.append(user_id)
            param_count += 1

        where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total
            FROM admin_tasks t
            {where_str}
        """
        count_row = await db.fetchrow(count_query, *params)
        total = count_row['total'] if count_row else 0

        # Get tasks
        params.extend([limit, offset])
        query = f"""
            SELECT
                t.id,
                t.user_id,
                t.type,
                t.status,
                t.payload,
                t.scheduled_at,
                t.due_at,
                t.sent_at,
                t.result_code,
                t.created_at,
                t.updated_at,
                u.username,
                u.tg_user_id
            FROM admin_tasks t
            LEFT JOIN users u ON u.id = t.user_id
            {where_str}
            ORDER BY t.created_at DESC
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """

        tasks = await db.fetch(query, *params)

        return {
            "tasks": [
                {
                    "id": t['id'],
                    "user_id": t['user_id'],
                    "username": t.get('username'),
                    "tg_user_id": t.get('tg_user_id'),
                    "type": t['type'],
                    "status": t['status'],
                    "payload": t['payload'],
                    "scheduled_at": t['scheduled_at'].isoformat() if t['scheduled_at'] else None,
                    "due_at": t['due_at'].isoformat() if t['due_at'] else None,
                    "sent_at": t['sent_at'].isoformat() if t['sent_at'] else None,
                    "result_code": t['result_code'],
                    "created_at": t['created_at'].isoformat() if t['created_at'] else None,
                    "updated_at": t['updated_at'].isoformat() if t['updated_at'] else None
                }
                for t in tasks
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error fetching admin tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/tasks")
async def create_admin_task(
    task: AdminTaskCreate,
    _: bool = Depends(verify_admin_token)
):
    """Create a new admin task"""
    try:
        # Validate user_id if provided
        if task.user_id:
            user = await db.fetchrow(
                "SELECT id FROM users WHERE id = $1",
                task.user_id
            )
            if not user:
                raise HTTPException(status_code=404, detail=f"User {task.user_id} not found")

        # Parse datetime strings
        scheduled_at = datetime.fromisoformat(task.scheduled_at) if task.scheduled_at else None
        due_at = datetime.fromisoformat(task.due_at) if task.due_at else None

        # Insert task
        row = await db.fetchrow(
            """
            INSERT INTO admin_tasks (user_id, type, status, payload, scheduled_at, due_at, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, now(), now())
            RETURNING id, user_id, type, status, payload, scheduled_at, due_at, sent_at, result_code, created_at, updated_at
            """,
            task.user_id,
            task.type,
            task.status,
            json.dumps(task.payload) if task.payload else '{}',
            scheduled_at,
            due_at
        )

        return {
            "status": "success",
            "task": {
                "id": row['id'],
                "user_id": row['user_id'],
                "type": row['type'],
                "status": row['status'],
                "payload": row['payload'],
                "scheduled_at": row['scheduled_at'].isoformat() if row['scheduled_at'] else None,
                "due_at": row['due_at'].isoformat() if row['due_at'] else None,
                "sent_at": row['sent_at'].isoformat() if row['sent_at'] else None,
                "result_code": row['result_code'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating admin task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/admin/tasks/{task_id}")
async def update_admin_task(
    task_id: int,
    task: AdminTaskUpdate,
    _: bool = Depends(verify_admin_token)
):
    """Update an existing admin task"""
    try:
        # Check if task exists
        existing = await db.fetchrow(
            "SELECT id FROM admin_tasks WHERE id = $1",
            task_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # Validate user_id if provided
        if task.user_id is not None:
            user = await db.fetchrow(
                "SELECT id FROM users WHERE id = $1",
                task.user_id
            )
            if not user:
                raise HTTPException(status_code=404, detail=f"User {task.user_id} not found")

        # Build update query dynamically
        updates = []
        params = []
        param_count = 1

        if task.user_id is not None:
            updates.append(f"user_id = ${param_count}")
            params.append(task.user_id)
            param_count += 1

        if task.type is not None:
            updates.append(f"type = ${param_count}")
            params.append(task.type)
            param_count += 1

        if task.status is not None:
            updates.append(f"status = ${param_count}")
            params.append(task.status)
            param_count += 1

        if task.payload is not None:
            updates.append(f"payload = ${param_count}")
            params.append(json.dumps(task.payload))
            param_count += 1

        if task.scheduled_at is not None:
            updates.append(f"scheduled_at = ${param_count}")
            params.append(datetime.fromisoformat(task.scheduled_at))
            param_count += 1

        if task.due_at is not None:
            updates.append(f"due_at = ${param_count}")
            params.append(datetime.fromisoformat(task.due_at))
            param_count += 1

        if task.sent_at is not None:
            updates.append(f"sent_at = ${param_count}")
            params.append(datetime.fromisoformat(task.sent_at))
            param_count += 1

        if task.result_code is not None:
            updates.append(f"result_code = ${param_count}")
            params.append(task.result_code)
            param_count += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates.append(f"updated_at = now()")
        params.append(task_id)
        query = f"""
            UPDATE admin_tasks
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING id, user_id, type, status, payload, scheduled_at, due_at, sent_at, result_code, created_at, updated_at
        """

        row = await db.fetchrow(query, *params)

        return {
            "status": "success",
            "task": {
                "id": row['id'],
                "user_id": row['user_id'],
                "type": row['type'],
                "status": row['status'],
                "payload": row['payload'],
                "scheduled_at": row['scheduled_at'].isoformat() if row['scheduled_at'] else None,
                "due_at": row['due_at'].isoformat() if row['due_at'] else None,
                "sent_at": row['sent_at'].isoformat() if row['sent_at'] else None,
                "result_code": row['result_code'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating admin task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/admin/tasks/{task_id}")
async def delete_admin_task(
    task_id: int,
    _: bool = Depends(verify_admin_token)
):
    """Delete an admin task"""
    try:
        # Check if task exists
        existing = await db.fetchrow(
            "SELECT id FROM admin_tasks WHERE id = $1",
            task_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # Delete task
        await db.execute(
            "DELETE FROM admin_tasks WHERE id = $1",
            task_id
        )

        return {
            "status": "success",
            "message": f"Task {task_id} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting admin task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))