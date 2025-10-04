from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, timedelta
from typing import Optional
import logging

from app.database.connection import db
from app.api.admin.auth import verify_admin_token
from app.scheduler import get_scheduler
from app.config import config

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/admin/trigger/daily-messages")
async def trigger_daily_messages(_: bool = Depends(verify_admin_token)):
    try:
        scheduler = get_scheduler()
        if scheduler:
            await scheduler.trigger_daily_messages()
            return {"status": "success", "message": "Daily messages triggered successfully"}
        else:
            return {"status": "error", "message": "Scheduler not available"}
    except Exception as e:
        logger.error(f"Error triggering daily messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger daily messages")

@router.post("/admin/trigger/crm-planning")
async def trigger_crm_planning(_: bool = Depends(verify_admin_token)):
    """Manually trigger CRM daily task planning"""
    try:
        scheduler = get_scheduler()
        if scheduler:
            stats = await scheduler.trigger_crm_planning()
            return {
                "status": "success",
                "message": "CRM planning triggered successfully",
                "stats": stats
            }
        else:
            return {"status": "error", "message": "Scheduler not available"}
    except Exception as e:
        logger.error(f"Error triggering CRM planning: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger CRM planning")

@router.post("/admin/trigger/crm-dispatch")
async def trigger_crm_dispatch(_: bool = Depends(verify_admin_token)):
    """Manually trigger CRM task dispatch"""
    try:
        scheduler = get_scheduler()
        if scheduler:
            stats = await scheduler.trigger_crm_dispatch()
            return {
                "status": "success",
                "message": "CRM dispatch triggered successfully",
                "stats": stats
            }
        else:
            return {"status": "error", "message": "Scheduler not available"}
    except Exception as e:
        logger.error(f"Error triggering CRM dispatch: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger CRM dispatch")

@router.get("/admin/crm/tasks")
async def get_crm_tasks(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, description="Limit results"),
    _: bool = Depends(verify_admin_token)
):
    """Get CRM tasks"""
    try:
        query = """
            SELECT t.*, u.tg_user_id, u.username, u.age, u.gender
            FROM admin_tasks t
            JOIN users u ON u.id = t.user_id
            WHERE 1=1
        """
        params = []
        param_count = 0

        if user_id:
            param_count += 1
            query += f" AND t.user_id = ${param_count}"
            params.append(user_id)

        if status:
            param_count += 1
            query += f" AND t.status = ${param_count}"
            params.append(status)

        param_count += 1
        query += f" ORDER BY t.created_at DESC LIMIT ${param_count}"
        params.append(limit)

        rows = await db.fetch(query, *params)

        tasks = []
        for row in rows:
            tasks.append({
                'id': row['id'],
                'user_id': row['user_id'],
                'tg_user_id': row['tg_user_id'],
                'username': row['username'],
                'type': row['type'],
                'status': row['status'],
                'due_at': row['due_at'].isoformat() if row['due_at'] else None,
                'sent_at': row['sent_at'].isoformat() if row['sent_at'] else None,
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'payload': row['payload']
            })

        return {
            'tasks': tasks,
            'total': len(tasks),
            'filters': {'user_id': user_id, 'status': status}
        }

    except Exception as e:
        logger.error(f"Error getting CRM tasks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/admin/test/ai-responses")
async def test_ai_responses(
    question: str = Query(..., description="Test question"),
    persona: str = Query("admin", description="Persona to test: admin or oracle"),
    age: int = Query(25, description="User age for personalization"),
    gender: str = Query("other", description="User gender: male, female, other"),
    _: bool = Depends(verify_admin_token)
):
    """Test AI responses for both personas"""
    try:
        from app.services.ai_client import call_admin_ai, call_oracle_ai

        user_context = {'age': age, 'gender': gender}

        if persona == "admin":
            response = await call_admin_ai(question, user_context)
            response_type = "Administrator (эмоциональный помощник)"
        elif persona == "oracle":
            response = await call_oracle_ai(question, user_context)
            response_type = "Oracle (мудрый наставник)"
        else:
            raise HTTPException(status_code=400, detail="Invalid persona. Use 'admin' or 'oracle'")

        return {
            "status": "success",
            "persona": response_type,
            "question": question,
            "response": response,
            "user_context": user_context,
            "response_length": len(response)
        }

    except Exception as e:
        logger.error(f"Error testing AI responses: {e}")
        raise HTTPException(status_code=500, detail="Failed to test AI responses")

@router.post("/admin/test/crm")
async def test_crm_for_admin(
    tg_user_id: Optional[int] = Query(None, description="Telegram user ID to test (defaults to first admin)"),
    _: bool = Depends(verify_admin_token)
):
    """Test CRM system - creates all task types for specified user"""
    try:
        # Get admin user ID: use provided or default to first from config
        admin_id = tg_user_id if tg_user_id else (config.ADMIN_IDS[0] if config.ADMIN_IDS else None)
        if not admin_id:
            return {
                "status": "error",
                "message": "No admin ID provided or configured"
            }

        # Get admin user data
        user_row = await db.fetchrow(
            """
            SELECT id, tg_user_id, username, age, gender, last_seen_at, free_questions_left
            FROM users
            WHERE tg_user_id = $1
            """,
            admin_id
        )

        if not user_row:
            return {
                "status": "error",
                "message": f"Admin user {admin_id} not found in database"
            }

        user_id = user_row['id']

        # Calculate due_at as current UTC time + 1 minute
        now_utc = datetime.utcnow()
        due_at = now_utc + timedelta(minutes=1)

        # All task types to create
        task_types = [
            'PING',
            'NUDGE_SUB',
            'DAILY_MSG_PROMPT',
            'DAILY_MSG_PUSH',
            'LIMIT_INFO',
            'RECOVERY',
            'POST_SUB_ONBOARD'
        ]

        # Create all task types
        created_tasks = []
        for task_type in task_types:
            row = await db.fetchrow(
                """
                INSERT INTO admin_tasks (user_id, type, status, due_at, created_at, updated_at, payload)
                VALUES ($1, $2, 'scheduled', $3, $4, $4, '{}')
                RETURNING id, type, status, due_at, created_at
                """,
                user_id,
                task_type,
                due_at,
                now_utc
            )
            created_tasks.append({
                "id": row['id'],
                "type": row['type'],
                "status": row['status'],
                "due_at": row['due_at'].isoformat() + 'Z',
                "created_at": row['created_at'].isoformat() + 'Z'
            })

        logger.info(f"Created {len(created_tasks)} test tasks for admin {admin_id}")

        return {
            "status": "success",
            "admin_id": admin_id,
            "tasks_created": len(created_tasks),
            "due_at_utc": due_at.isoformat() + 'Z',
            "current_time_utc": now_utc.isoformat() + 'Z',
            "tasks": created_tasks
        }

    except Exception as e:
        logger.error(f"Error testing CRM: {e}")
        raise HTTPException(status_code=500, detail=str(e))