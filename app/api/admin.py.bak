from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import logging
import hmac
import hashlib
from urllib.parse import parse_qsl
import json

from app.database.models import MetricsModel
from app.database.connection import db
from app.config import config
from app.scheduler import get_scheduler

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != config.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True

def validate_telegram_webapp_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    """Validate Telegram WebApp initData and return parsed user data"""
    try:
        # Parse init_data
        parsed_data = dict(parse_qsl(init_data))

        # Extract hash
        data_check_string_parts = []
        hash_value = None

        for key, value in sorted(parsed_data.items()):
            if key == 'hash':
                hash_value = value
            else:
                data_check_string_parts.append(f"{key}={value}")

        if not hash_value:
            raise ValueError("No hash in initData")

        data_check_string = '\n'.join(data_check_string_parts)

        # Create secret key
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()

        # Calculate hash
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()

        # Verify hash
        if calculated_hash != hash_value:
            raise ValueError("Invalid hash")

        # Parse user data
        import json
        user_data = json.loads(parsed_data.get('user', '{}'))

        return user_data
    except Exception as e:
        logger.error(f"Error validating Telegram WebApp data: {e}")
        raise HTTPException(status_code=401, detail="Invalid Telegram data")

@router.post("/admin/auth/verify")
async def verify_admin_access(request: Request):
    """Verify if user is admin based on Telegram WebApp data"""
    try:
        body = await request.json()
        init_data = body.get('initData')

        if not init_data:
            raise HTTPException(status_code=400, detail="initData required")

        # Validate Telegram data
        user_data = validate_telegram_webapp_data(init_data, config.BOT_TOKEN)

        user_id = user_data.get('id')
        if not user_id:
            raise HTTPException(status_code=401, detail="No user ID in data")

        # Check if user is admin
        if user_id not in config.ADMIN_IDS:
            logger.warning(f"Access denied for user {user_id}")
            raise HTTPException(status_code=403, detail="Access denied")

        logger.info(f"Admin access granted for user {user_id}")

        return {
            "status": "success",
            "user": {
                "id": user_id,
                "username": user_data.get('username'),
                "first_name": user_data.get('first_name')
            },
            "token": config.ADMIN_TOKEN
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying admin access: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/admin/stats")
async def get_stats(
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    _: bool = Depends(verify_admin_token)
):
    try:
        if not date_from:
            date_from = date.today().strftime('%Y-%m-%d')
        if not date_to:
            date_to = date.today().strftime('%Y-%m-%d')

        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()

        rows = await db.fetch(
            """
            SELECT * FROM fact_daily_metrics
            WHERE d BETWEEN $1 AND $2
            ORDER BY d
            """,
            start_date, end_date
        )

        stats = []
        for row in rows:
            stats.append({
                'date': row['d'].isoformat(),
                'dau': row['dau'],
                'new_users': row['new_users'],
                'active_users': row['active_users'],
                'blocked_total': row['blocked_total'],
                'daily_sent': row['daily_sent'],
                'paid_active': row['paid_active'],
                'paid_new': row['paid_new'],
                'questions': row['questions'],
                'revenue': float(row['revenue'])
            })

        # Calculate summary
        summary = {
            'total_days': len(stats),
            'total_dau': sum(s['dau'] for s in stats),
            'total_new_users': sum(s['new_users'] for s in stats),
            'total_questions': sum(s['questions'] for s in stats),
            'total_revenue': sum(s['revenue'] for s in stats),
            'avg_dau': sum(s['dau'] for s in stats) / len(stats) if stats else 0
        }

        return {
            'stats': stats,
            'summary': summary,
            'period': {
                'from': date_from,
                'to': date_to
            }
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/admin/users")
async def get_users(
    status: Optional[str] = Query(None, description="Filter by status: active, blocked, paid"),
    limit: int = Query(50, description="Limit results"),
    _: bool = Depends(verify_admin_token)
):
    try:
        query = "SELECT u.*, s.ends_at as subscription_end FROM users u LEFT JOIN subscriptions s ON u.id = s.user_id AND s.status = 'active' AND s.ends_at > now()"
        params = []

        if status == "blocked":
            query += " WHERE u.is_blocked = true"
        elif status == "paid":
            query += " WHERE s.id IS NOT NULL"
        elif status == "active":
            query += " WHERE u.is_blocked = false"

        query += " ORDER BY u.last_seen_at DESC LIMIT $1"
        params.append(limit)

        rows = await db.fetch(query, *params)

        users = []
        for row in rows:
            users.append({
                'id': row['id'],
                'tg_user_id': row['tg_user_id'],
                'username': row['username'],
                'first_seen_at': row['first_seen_at'].isoformat() if row['first_seen_at'] else None,
                'last_seen_at': row['last_seen_at'].isoformat() if row['last_seen_at'] else None,
                'is_blocked': row['is_blocked'],
                'free_questions_left': row['free_questions_left'],
                'has_subscription': row['subscription_end'] is not None,
                'subscription_end': row['subscription_end'].isoformat() if row['subscription_end'] else None
            })

        return {
            'users': users,
            'total': len(users),
            'filter': status
        }

    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/admin/users/{user_id}")
async def get_user_details(
    user_id: int,
    _: bool = Depends(verify_admin_token)
):
    """Get detailed user information including history"""
    try:
        # Get user info
        user = await db.fetchrow(
            """
            SELECT u.*,
                   s.ends_at as subscription_end
            FROM users u
            LEFT JOIN subscriptions s ON s.user_id = u.id
                AND s.status = 'active' AND s.ends_at > now()
            WHERE u.id = $1
            """,
            user_id
        )

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get daily messages history
        daily_messages = await db.fetch(
            """
            SELECT sent_date
            FROM daily_sent
            WHERE user_id = $1
            ORDER BY sent_date DESC
            LIMIT 50
            """,
            user_id
        )

        # Get Oracle questions history
        oracle_questions = await db.fetch(
            """
            SELECT question, answer, source, asked_date, asked_at, tokens_used
            FROM oracle_questions
            WHERE user_id = $1
            ORDER BY asked_at DESC
            LIMIT 50
            """,
            user_id
        )

        # Get payments history
        payments = await db.fetch(
            """
            SELECT plan_code, amount, status, created_at, paid_at
            FROM payments
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 50
            """,
            user_id
        )

        # Get CRM tasks history (logs)
        crm_logs = await db.fetch(
            """
            SELECT type, status, due_at, sent_at, result_code, payload, created_at
            FROM admin_tasks
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 100
            """,
            user_id
        )

        return {
            'user': {
                'id': user['id'],
                'tg_user_id': user['tg_user_id'],
                'username': user['username'],
                'age': user['age'],
                'gender': user['gender'],
                'first_seen_at': user['first_seen_at'].isoformat() if user['first_seen_at'] else None,
                'last_seen_at': user['last_seen_at'].isoformat() if user['last_seen_at'] else None,
                'is_blocked': user['is_blocked'],
                'free_questions_left': user['free_questions_left'],
                'has_subscription': user['subscription_end'] is not None,
                'subscription_end': user['subscription_end'].isoformat() if user['subscription_end'] else None
            },
            'daily_messages': [{
                'date': msg['sent_date'].isoformat()
            } for msg in daily_messages],
            'oracle_questions': [{
                'question': q['question'],
                'answer': q['answer'],
                'source': q['source'],
                'date': q['asked_date'].isoformat(),
                'asked_at': q['asked_at'].isoformat() if q['asked_at'] else None,
                'tokens': q['tokens_used']
            } for q in oracle_questions],
            'payments': [{
                'plan': p['plan_code'],
                'amount': float(p['amount']),
                'status': p['status'],
                'created_at': p['created_at'].isoformat() if p['created_at'] else None,
                'paid_at': p['paid_at'].isoformat() if p['paid_at'] else None
            } for p in payments],
            'crm_logs': [{
                'type': log['type'],
                'status': log['status'],
                'due_at': log['due_at'].isoformat() if log['due_at'] else None,
                'sent_at': log['sent_at'].isoformat() if log['sent_at'] else None,
                'result_code': log['result_code'],
                'created_at': log['created_at'].isoformat() if log['created_at'] else None
            } for log in crm_logs]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/admin/export")
async def export_stats(
    date_from: str = Query(..., description="Start date (YYYY-MM-DD)"),
    date_to: str = Query(..., description="End date (YYYY-MM-DD)"),
    format: str = Query("json", description="Export format: json, csv"),
    _: bool = Depends(verify_admin_token)
):
    try:
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()

        rows = await db.fetch(
            """
            SELECT * FROM fact_daily_metrics
            WHERE d BETWEEN $1 AND $2
            ORDER BY d
            """,
            start_date, end_date
        )

        if format == "csv":
            from fastapi.responses import Response

            headers = ['date', 'dau', 'new_users', 'active_users', 'blocked_total',
                      'daily_sent', 'paid_active', 'paid_new', 'questions', 'revenue']

            csv_lines = [','.join(headers)]

            for row in rows:
                line = ','.join([str(row[header] if row[header] is not None else 0) for header in headers])
                csv_lines.append(line)

            csv_content = '\n'.join(csv_lines)

            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=stats_{date_from}_{date_to}.csv"}
            )

        # JSON format (default)
        stats = []
        for row in rows:
            stats.append({
                'date': row['d'].isoformat(),
                'dau': row['dau'],
                'new_users': row['new_users'],
                'active_users': row['active_users'],
                'blocked_total': row['blocked_total'],
                'daily_sent': row['daily_sent'],
                'paid_active': row['paid_active'],
                'paid_new': row['paid_new'],
                'questions': row['questions'],
                'revenue': float(row['revenue'])
            })

        return {
            'data': stats,
            'period': {'from': date_from, 'to': date_to},
            'exported_at': datetime.now().isoformat()
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error exporting stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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

@router.get("/admin/dashboard")
async def get_dashboard(_: bool = Depends(verify_admin_token)):
    """Get dashboard summary with extended metrics"""
    try:
        # Total users
        total_users = await db.fetchval("SELECT COUNT(*) FROM users")

        # Active users (last seen today/week)
        active_today = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE DATE(last_seen_at) = CURRENT_DATE"
        )
        active_week = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE last_seen_at > now() - interval '7 days'"
        )

        # New users
        new_today = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE DATE(first_seen_at) = CURRENT_DATE"
        )
        new_week = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE first_seen_at > now() - interval '7 days'"
        )
        new_month = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE first_seen_at > now() - interval '30 days'"
        )

        # Subscriptions
        active_subs = await db.fetchval(
            "SELECT COUNT(*) FROM subscriptions WHERE status = 'active' AND ends_at > now()"
        )

        # Subscriptions by plan
        subs_by_plan = await db.fetch(
            """
            SELECT plan_code, COUNT(*) as count
            FROM subscriptions
            WHERE status = 'active' AND ends_at > now()
            GROUP BY plan_code
            """
        )

        # Revenue
        today_revenue = await db.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM subscriptions WHERE DATE(started_at) = CURRENT_DATE"
        )
        month_revenue = await db.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM subscriptions WHERE started_at > now() - interval '30 days'"
        )

        # Payments today
        payments_today = await db.fetchval(
            "SELECT COUNT(*) FROM subscriptions WHERE DATE(started_at) = CURRENT_DATE"
        )

        return {
            'total_users': total_users,
            'active_today': active_today,
            'active_week': active_week,
            'new_today': new_today,
            'new_week': new_week,
            'new_month': new_month,
            'active_subscriptions': active_subs,
            'subscriptions_by_plan': {row['plan_code']: row['count'] for row in subs_by_plan},
            'today_revenue': float(today_revenue) if today_revenue else 0,
            'month_revenue': float(month_revenue) if month_revenue else 0,
            'payments_today': payments_today,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/health")
async def health_check():
    try:
        # Simple database check
        await db.fetchval("SELECT 1")

        # Get git commit hash
        try:
            with open('/app/GIT_COMMIT', 'r') as f:
                git_hash = f.read().strip()
        except Exception:
            git_hash = "unknown"

        return {
            "status": "healthy",
            "service": "Bot Oracle",
            "version": "2.0.0",
            "commit": git_hash,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@router.post("/admin/test/crm")
async def test_crm_for_admin(_: bool = Depends(verify_admin_token)):
    """Test CRM system for admin user"""
    try:
        from app.crm.planner import crm_planner
        from app.crm.dispatcher import crm_dispatcher

        if not crm_dispatcher:
            return {
                "status": "error",
                "message": "CRM dispatcher not initialized"
            }

        # Get admin user from config
        admin_id = config.ADMIN_IDS[0] if config.ADMIN_IDS else None
        if not admin_id:
            return {
                "status": "error",
                "message": "No admin ID configured"
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

        user_data = dict(user_row)

        # Test 1: CRM Planner
        logger.info(f"Testing CRM planner for admin {admin_id}")
        tasks_created = await crm_planner.plan_for_user(user_data)

        # Get created tasks
        created_tasks = await db.fetch(
            """
            SELECT id, type, due_at, status
            FROM admin_tasks
            WHERE user_id = $1 AND status = 'pending'
            ORDER BY due_at DESC
            LIMIT 10
            """,
            user_data['id']
        )

        # Test 2: CRM Dispatcher
        logger.info(f"Testing CRM dispatcher for admin {admin_id}")
        dispatch_stats = await crm_dispatcher.dispatch_due_tasks(limit=5)

        return {
            "status": "success",
            "admin_id": admin_id,
            "planner": {
                "tasks_created": tasks_created,
                "created_tasks": [
                    {
                        "id": t['id'],
                        "type": t['type'],
                        "due_at": t['due_at'].isoformat(),
                        "status": t['status']
                    } for t in created_tasks
                ]
            },
            "dispatcher": dispatch_stats,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error testing CRM: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Events CRUD
# ============================================================================

class EventCreate(BaseModel):
    user_id: Optional[int] = None
    type: str
    meta: Optional[Dict[str, Any]] = {}

class EventUpdate(BaseModel):
    user_id: Optional[int] = None
    type: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

class AdminTaskCreate(BaseModel):
    user_id: Optional[int] = None
    type: str
    status: str = 'scheduled'
    payload: Optional[Dict[str, Any]] = {}
    scheduled_at: Optional[str] = None
    due_at: Optional[str] = None

class AdminTaskUpdate(BaseModel):
    user_id: Optional[int] = None
    type: Optional[str] = None
    status: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[str] = None
    due_at: Optional[str] = None
    sent_at: Optional[str] = None
    result_code: Optional[str] = None

class TemplateCreate(BaseModel):
    type: str
    tone: str
    text: str
    enabled: bool = True
    weight: int = 1

class TemplateUpdate(BaseModel):
    type: Optional[str] = None
    tone: Optional[str] = None
    text: Optional[str] = None
    enabled: Optional[bool] = None
    weight: Optional[int] = None

class DailyMessageCreate(BaseModel):
    text: str
    is_active: bool = True
    weight: int = 1

class DailyMessageUpdate(BaseModel):
    text: Optional[str] = None
    is_active: Optional[bool] = None
    weight: Optional[int] = None

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


# ============================================================================
# Admin Tasks CRUD
# ============================================================================

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
        from datetime import datetime

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
        from datetime import datetime

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
# ============ ADMIN_TEMPLATES CRUD ============

@router.get("/admin/templates")
async def get_templates(
    _: bool = Depends(verify_admin_token),
    type: Optional[str] = Query(None),
    tone: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    limit: int = Query(100)
):
    """Get admin templates with optional filtering"""
    try:
        query = "SELECT * FROM admin_templates WHERE 1=1"
        params = []
        param_count = 0

        if type:
            param_count += 1
            query += f" AND type = ${param_count}"
            params.append(type)

        if tone:
            param_count += 1
            query += f" AND tone = ${param_count}"
            params.append(tone)

        if enabled is not None:
            param_count += 1
            query += f" AND enabled = ${param_count}"
            params.append(enabled)

        param_count += 1
        query += f" ORDER BY id DESC LIMIT ${param_count}"
        params.append(limit)

        rows = await db.fetch(query, *params)

        templates = []
        for row in rows:
            templates.append({
                'id': row['id'],
                'type': row['type'],
                'tone': row['tone'],
                'text': row['text'],
                'enabled': row['enabled'],
                'weight': row['weight']
            })

        return {
            'templates': templates,
            'total': len(templates),
            'filters': {'type': type, 'tone': tone, 'enabled': enabled}
        }

    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/templates")
async def create_template(
    template: TemplateCreate,
    _: bool = Depends(verify_admin_token)
):
    """Create a new admin template"""
    try:
        row = await db.fetchrow(
            """
            INSERT INTO admin_templates (type, tone, text, enabled, weight)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, type, tone, text, enabled, weight
            """,
            template.type,
            template.tone,
            template.text,
            template.enabled,
            template.weight
        )

        return {
            "status": "success",
            "template": {
                "id": row['id'],
                "type": row['type'],
                "tone": row['tone'],
                "text": row['text'],
                "enabled": row['enabled'],
                "weight": row['weight']
            }
        }
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/admin/templates/{template_id}")
async def update_template(
    template_id: int,
    template: TemplateUpdate,
    _: bool = Depends(verify_admin_token)
):
    """Update an existing admin template"""
    try:
        # Check if template exists
        existing = await db.fetchrow(
            "SELECT id FROM admin_templates WHERE id = $1",
            template_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

        # Build update query dynamically
        updates = []
        params = []
        param_count = 1

        if template.type is not None:
            updates.append(f"type = ${param_count}")
            params.append(template.type)
            param_count += 1

        if template.tone is not None:
            updates.append(f"tone = ${param_count}")
            params.append(template.tone)
            param_count += 1

        if template.text is not None:
            updates.append(f"text = ${param_count}")
            params.append(template.text)
            param_count += 1

        if template.enabled is not None:
            updates.append(f"enabled = ${param_count}")
            params.append(template.enabled)
            param_count += 1

        if template.weight is not None:
            updates.append(f"weight = ${param_count}")
            params.append(template.weight)
            param_count += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(template_id)
        query = f"""
            UPDATE admin_templates
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING id, type, tone, text, enabled, weight
        """

        row = await db.fetchrow(query, *params)

        return {
            "status": "success",
            "template": {
                "id": row['id'],
                "type": row['type'],
                "tone": row['tone'],
                "text": row['text'],
                "enabled": row['enabled'],
                "weight": row['weight']
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/admin/templates/{template_id}")
async def delete_template(
    template_id: int,
    _: bool = Depends(verify_admin_token)
):
    """Delete an admin template"""
    try:
        # Check if template exists
        existing = await db.fetchrow(
            "SELECT id FROM admin_templates WHERE id = $1",
            template_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

        # Delete template
        await db.execute(
            "DELETE FROM admin_templates WHERE id = $1",
            template_id
        )

        return {
            "status": "success",
            "message": f"Template {template_id} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ DAILY_MESSAGES CRUD ============

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
