from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
import logging

from app.database.connection import db
from app.api.admin.auth import verify_admin_token

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/admin/subscriptions")
async def get_subscriptions(
    status: Optional[str] = Query(None, description="Filter by status: active, expired"),
    limit: int = Query(50, description="Limit results"),
    _: bool = Depends(verify_admin_token)
):
    """Get subscriptions list"""
    try:
        query = """
            SELECT s.*, u.tg_user_id, u.username
            FROM subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE 1=1
        """
        params = []

        if status == "active":
            query += " AND s.status = 'active' AND s.ends_at > now()"
        elif status == "expired":
            query += " AND (s.status = 'expired' OR s.ends_at <= now())"

        query += " ORDER BY s.started_at DESC LIMIT $1"
        params.append(limit)

        rows = await db.fetch(query, *params)

        subscriptions = []
        for row in rows:
            subscriptions.append({
                'id': row['id'],
                'user_id': row['user_id'],
                'tg_user_id': row['tg_user_id'],
                'username': row['username'],
                'plan_code': row['plan_code'],
                'amount': float(row['amount']) if row['amount'] else 0,
                'currency': row['currency'],
                'status': row['status'],
                'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                'ends_at': row['ends_at'].isoformat() if row['ends_at'] else None
            })

        return {
            'subscriptions': subscriptions,
            'total': len(subscriptions),
            'filter': status
        }

    except Exception as e:
        logger.error(f"Error getting subscriptions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")