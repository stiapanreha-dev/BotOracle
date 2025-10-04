from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
import logging

from app.database.connection import db
from app.api.admin.auth import verify_admin_token
from app.api.admin.models import DailyMessageCreate, DailyMessageUpdate

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/admin/daily-messages")
async def get_daily_messages(
    _: bool = Depends(verify_admin_token),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(100)
):
    """Get daily messages with optional filtering"""
    try:
        query = "SELECT * FROM daily_messages WHERE 1=1"
        params = []
        param_count = 0

        if is_active is not None:
            param_count += 1
            query += f" AND is_active = ${param_count}"
            params.append(is_active)

        param_count += 1
        query += f" ORDER BY id DESC LIMIT ${param_count}"
        params.append(limit)

        rows = await db.fetch(query, *params)

        messages = []
        for row in rows:
            messages.append({
                'id': row['id'],
                'text': row['text'],
                'is_active': row['is_active'],
                'weight': row['weight']
            })

        return {
            'messages': messages,
            'total': len(messages),
            'filters': {'is_active': is_active}
        }

    except Exception as e:
        logger.error(f"Error getting daily messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/daily-messages")
async def create_daily_message(
    message: DailyMessageCreate,
    _: bool = Depends(verify_admin_token)
):
    """Create a new daily message"""
    try:
        row = await db.fetchrow(
            """
            INSERT INTO daily_messages (text, is_active, weight)
            VALUES ($1, $2, $3)
            RETURNING id, text, is_active, weight
            """,
            message.text,
            message.is_active,
            message.weight
        )

        return {
            "status": "success",
            "message": {
                "id": row['id'],
                "text": row['text'],
                "is_active": row['is_active'],
                "weight": row['weight']
            }
        }
    except Exception as e:
        logger.error(f"Error creating daily message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/admin/daily-messages/{message_id}")
async def update_daily_message(
    message_id: int,
    message: DailyMessageUpdate,
    _: bool = Depends(verify_admin_token)
):
    """Update an existing daily message"""
    try:
        # Check if message exists
        existing = await db.fetchrow(
            "SELECT id FROM daily_messages WHERE id = $1",
            message_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

        # Build update query dynamically
        updates = []
        params = []
        param_count = 1

        if message.text is not None:
            updates.append(f"text = ${param_count}")
            params.append(message.text)
            param_count += 1

        if message.is_active is not None:
            updates.append(f"is_active = ${param_count}")
            params.append(message.is_active)
            param_count += 1

        if message.weight is not None:
            updates.append(f"weight = ${param_count}")
            params.append(message.weight)
            param_count += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(message_id)
        query = f"""
            UPDATE daily_messages
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING id, text, is_active, weight
        """

        row = await db.fetchrow(query, *params)

        return {
            "status": "success",
            "message": {
                "id": row['id'],
                "text": row['text'],
                "is_active": row['is_active'],
                "weight": row['weight']
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating daily message {message_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/admin/daily-messages/{message_id}")
async def delete_daily_message(
    message_id: int,
    _: bool = Depends(verify_admin_token)
):
    """Delete a daily message"""
    try:
        # Check if message exists
        existing = await db.fetchrow(
            "SELECT id FROM daily_messages WHERE id = $1",
            message_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")

        # Delete message
        await db.execute(
            "DELETE FROM daily_messages WHERE id = $1",
            message_id
        )

        return {
            "status": "success",
            "message": f"Message {message_id} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting daily message {message_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))