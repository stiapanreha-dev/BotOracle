from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
import logging

from app.database.connection import db
from app.api.admin.auth import verify_admin_token
from app.api.admin.models import TemplateCreate, TemplateUpdate

logger = logging.getLogger(__name__)
router = APIRouter()

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