from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
import logging
import json

from app.database.connection import db
from app.api.admin.auth import verify_admin_token
from app.api.admin.models import EventCreate, EventUpdate

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/admin/events")
async def get_events(
    _: bool = Depends(verify_admin_token),
    type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0)
):
    """Get events list with optional filtering"""
    try:
        where_clauses = []
        params = []
        param_count = 1

        if type:
            where_clauses.append(f"e.type = ${param_count}")
            params.append(type)
            param_count += 1

        if user_id:
            where_clauses.append(f"e.user_id = ${param_count}")
            params.append(user_id)
            param_count += 1

        where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total
            FROM events e
            {where_str}
        """
        count_row = await db.fetchrow(count_query, *params)
        total = count_row['total'] if count_row else 0

        # Get events
        params.extend([limit, offset])
        query = f"""
            SELECT
                e.id,
                e.user_id,
                e.type,
                e.meta,
                e.occurred_at,
                u.username,
                u.tg_user_id
            FROM events e
            LEFT JOIN users u ON u.id = e.user_id
            {where_str}
            ORDER BY e.occurred_at DESC
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """

        events = await db.fetch(query, *params)

        return {
            "events": [
                {
                    "id": e['id'],
                    "user_id": e['user_id'],
                    "username": e.get('username'),
                    "tg_user_id": e.get('tg_user_id'),
                    "type": e['type'],
                    "meta": e['meta'],
                    "occurred_at": e['occurred_at'].isoformat() if e['occurred_at'] else None
                }
                for e in events
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/events")
async def create_event(
    event: EventCreate,
    _: bool = Depends(verify_admin_token)
):
    """Create a new event"""
    try:
        # Validate user_id if provided
        if event.user_id:
            user = await db.fetchrow(
                "SELECT id FROM users WHERE id = $1",
                event.user_id
            )
            if not user:
                raise HTTPException(status_code=404, detail=f"User {event.user_id} not found")

        # Insert event
        row = await db.fetchrow(
            """
            INSERT INTO events (user_id, type, meta, occurred_at)
            VALUES ($1, $2, $3, now())
            RETURNING id, user_id, type, meta, occurred_at
            """,
            event.user_id,
            event.type,
            json.dumps(event.meta) if event.meta else '{}'
        )

        return {
            "status": "success",
            "event": {
                "id": row['id'],
                "user_id": row['user_id'],
                "type": row['type'],
                "meta": row['meta'],
                "occurred_at": row['occurred_at'].isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/admin/events/{event_id}")
async def update_event(
    event_id: int,
    event: EventUpdate,
    _: bool = Depends(verify_admin_token)
):
    """Update an existing event"""
    try:
        # Check if event exists
        existing = await db.fetchrow(
            "SELECT id FROM events WHERE id = $1",
            event_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

        # Validate user_id if provided
        if event.user_id is not None:
            user = await db.fetchrow(
                "SELECT id FROM users WHERE id = $1",
                event.user_id
            )
            if not user:
                raise HTTPException(status_code=404, detail=f"User {event.user_id} not found")

        # Build update query dynamically
        updates = []
        params = []
        param_count = 1

        if event.user_id is not None:
            updates.append(f"user_id = ${param_count}")
            params.append(event.user_id)
            param_count += 1

        if event.type is not None:
            updates.append(f"type = ${param_count}")
            params.append(event.type)
            param_count += 1

        if event.meta is not None:
            updates.append(f"meta = ${param_count}")
            params.append(json.dumps(event.meta))
            param_count += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(event_id)
        query = f"""
            UPDATE events
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING id, user_id, type, meta, occurred_at
        """

        row = await db.fetchrow(query, *params)

        return {
            "status": "success",
            "event": {
                "id": row['id'],
                "user_id": row['user_id'],
                "type": row['type'],
                "meta": row['meta'],
                "occurred_at": row['occurred_at'].isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/admin/events/{event_id}")
async def delete_event(
    event_id: int,
    _: bool = Depends(verify_admin_token)
):
    """Delete an event"""
    try:
        # Check if event exists
        existing = await db.fetchrow(
            "SELECT id FROM events WHERE id = $1",
            event_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

        # Delete event
        await db.execute(
            "DELETE FROM events WHERE id = $1",
            event_id
        )

        return {
            "status": "success",
            "message": f"Event {event_id} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))