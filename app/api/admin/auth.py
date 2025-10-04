from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
import logging
import hmac
import hashlib
from urllib.parse import parse_qsl
import json

from app.config import config

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