from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
import logging

from app.database.connection import db
from app.api.admin.auth import verify_admin_token
from app.api.admin.models import PromptCreate, PromptUpdate

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/admin/prompts")
async def get_prompts(
    _: bool = Depends(verify_admin_token),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(100)
):
    """Get AI prompts with optional filtering"""
    try:
        query = "SELECT * FROM ai_prompts WHERE 1=1"
        params = []
        param_count = 0

        if is_active is not None:
            param_count += 1
            query += f" AND is_active = ${param_count}"
            params.append(is_active)

        param_count += 1
        query += f" ORDER BY key ASC LIMIT ${param_count}"
        params.append(limit)

        rows = await db.fetch(query, *params)

        prompts = []
        for row in rows:
            prompts.append({
                'id': row['id'],
                'key': row['key'],
                'name': row['name'],
                'prompt_text': row['prompt_text'],
                'description': row['description'],
                'is_active': row['is_active'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
            })

        return {
            'prompts': prompts,
            'total': len(prompts),
            'filters': {'is_active': is_active}
        }

    except Exception as e:
        logger.error(f"Error getting prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/prompts/{prompt_id}")
async def get_prompt(
    prompt_id: int,
    _: bool = Depends(verify_admin_token)
):
    """Get single prompt by ID"""
    try:
        row = await db.fetchrow(
            "SELECT * FROM ai_prompts WHERE id = $1",
            prompt_id
        )

        if not row:
            raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")

        return {
            'id': row['id'],
            'key': row['key'],
            'name': row['name'],
            'prompt_text': row['prompt_text'],
            'description': row['description'],
            'is_active': row['is_active'],
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/prompts")
async def create_prompt(
    prompt: PromptCreate,
    _: bool = Depends(verify_admin_token)
):
    """Create a new prompt"""
    try:
        row = await db.fetchrow(
            """
            INSERT INTO ai_prompts (key, name, prompt_text, description, is_active)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, key, name, prompt_text, description, is_active, created_at, updated_at
            """,
            prompt.key,
            prompt.name,
            prompt.prompt_text,
            prompt.description,
            prompt.is_active
        )

        return {
            "status": "success",
            "prompt": {
                "id": row['id'],
                "key": row['key'],
                "name": row['name'],
                "prompt_text": row['prompt_text'],
                "description": row['description'],
                "is_active": row['is_active'],
                "created_at": row['created_at'].isoformat(),
                "updated_at": row['updated_at'].isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error creating prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/admin/prompts/{prompt_id}")
async def update_prompt(
    prompt_id: int,
    prompt: PromptUpdate,
    _: bool = Depends(verify_admin_token)
):
    """Update an existing prompt"""
    try:
        # Check if prompt exists
        existing = await db.fetchrow(
            "SELECT id FROM ai_prompts WHERE id = $1",
            prompt_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")

        # Build update query dynamically
        updates = []
        params = []
        param_count = 1

        if prompt.key is not None:
            updates.append(f"key = ${param_count}")
            params.append(prompt.key)
            param_count += 1

        if prompt.name is not None:
            updates.append(f"name = ${param_count}")
            params.append(prompt.name)
            param_count += 1

        if prompt.prompt_text is not None:
            updates.append(f"prompt_text = ${param_count}")
            params.append(prompt.prompt_text)
            param_count += 1

        if prompt.description is not None:
            updates.append(f"description = ${param_count}")
            params.append(prompt.description)
            param_count += 1

        if prompt.is_active is not None:
            updates.append(f"is_active = ${param_count}")
            params.append(prompt.is_active)
            param_count += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(prompt_id)
        query = f"""
            UPDATE ai_prompts
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING id, key, name, prompt_text, description, is_active, created_at, updated_at
        """

        row = await db.fetchrow(query, *params)

        return {
            "status": "success",
            "prompt": {
                "id": row['id'],
                "key": row['key'],
                "name": row['name'],
                "prompt_text": row['prompt_text'],
                "description": row['description'],
                "is_active": row['is_active'],
                "created_at": row['created_at'].isoformat(),
                "updated_at": row['updated_at'].isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/admin/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    _: bool = Depends(verify_admin_token)
):
    """Delete a prompt"""
    try:
        # Check if prompt exists
        existing = await db.fetchrow(
            "SELECT id FROM ai_prompts WHERE id = $1",
            prompt_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")

        # Delete prompt
        await db.execute(
            "DELETE FROM ai_prompts WHERE id = $1",
            prompt_id
        )

        return {
            "status": "success",
            "message": f"Prompt {prompt_id} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
