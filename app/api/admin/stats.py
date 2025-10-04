from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, date
from typing import Optional
import logging

from app.database.connection import db
from app.api.admin.auth import verify_admin_token

logger = logging.getLogger(__name__)
router = APIRouter()

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