from fastapi import APIRouter, Request, HTTPException, Form
from typing import Dict, Any
import logging
from aiogram import Bot

from app.database.models import UserModel, SubscriptionModel, EventModel, PaymentModel
from app.utils.robokassa import verify_signature_result, parse_robokassa_callback
from app.config import config
from app.services.persona import persona_factory

logger = logging.getLogger(__name__)
router = APIRouter()

@router.api_route("/robokassa/result", methods=["GET", "POST"])
async def robokassa_result(request: Request):
    try:
        # Parse form data or query params
        if request.method == "POST":
            form = await request.form()
            form_data = dict(form)
        else:
            # GET request - parse query params
            form_data = dict(request.query_params)

        logger.info(f"Robokassa callback received ({request.method}): {form_data}")

        # Parse callback data
        callback_data = parse_robokassa_callback(form_data)

        amount = callback_data['amount']
        inv_id = callback_data['inv_id']
        signature = callback_data['signature']

        if not amount or not inv_id or not signature:
            logger.warning("Missing required parameters in Robokassa callback")
            raise HTTPException(status_code=400, detail="Missing parameters")

        # Verify signature
        if not verify_signature_result(amount, inv_id, signature):
            logger.warning(f"Invalid signature for payment {inv_id}")
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Get payment info from database using numeric inv_id
        try:
            inv_id_int = int(inv_id)
            payment = await PaymentModel.get_payment_by_inv_id(inv_id_int)
            if not payment:
                logger.error(f"Payment not found for invoice ID: {inv_id}")
                raise HTTPException(status_code=400, detail="Payment not found")

            user_id = payment['user_id']
            plan_code = payment['plan_code']
        except (ValueError, TypeError):
            logger.error(f"Invalid invoice ID format: {inv_id}")
            raise HTTPException(status_code=400, detail="Invalid invoice ID")

        # Process payment
        await process_successful_payment(
            user_id=user_id,
            inv_id=inv_id_int,
            plan_code=plan_code,
            amount=float(amount),
            raw_payload=form_data
        )

        logger.info(f"Payment {inv_id} processed successfully")
        return "OK"

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Robokassa callback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.api_route("/robokassa/success", methods=["GET", "POST"])
async def robokassa_success(request: Request):
    # Success redirect - show user-friendly page
    logger.info(f"Robokassa success page accessed ({request.method})")

    html_content = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Оплата успешна - Bot Oracle</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}

            .container {{
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                max-width: 500px;
                width: 100%;
                padding: 40px;
                text-align: center;
                animation: slideUp 0.5s ease-out;
            }}

            @keyframes slideUp {{
                from {{
                    opacity: 0;
                    transform: translateY(30px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}

            .success-icon {{
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 30px;
                animation: scaleIn 0.5s ease-out 0.2s both;
            }}

            @keyframes scaleIn {{
                from {{
                    transform: scale(0);
                }}
                to {{
                    transform: scale(1);
                }}
            }}

            .success-icon svg {{
                width: 50px;
                height: 50px;
                stroke: white;
                stroke-width: 3;
                stroke-linecap: round;
                stroke-linejoin: round;
                fill: none;
            }}

            h1 {{
                color: #2d3748;
                font-size: 28px;
                margin-bottom: 15px;
                font-weight: 700;
            }}

            p {{
                color: #718096;
                font-size: 16px;
                line-height: 1.6;
                margin-bottom: 30px;
            }}

            .info-box {{
                background: #f7fafc;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 30px;
                text-align: left;
            }}

            .info-item {{
                display: flex;
                align-items: center;
                margin-bottom: 12px;
                color: #4a5568;
                font-size: 14px;
            }}

            .info-item:last-child {{
                margin-bottom: 0;
            }}

            .info-item svg {{
                width: 20px;
                height: 20px;
                margin-right: 12px;
                stroke: #667eea;
                flex-shrink: 0;
            }}

            .btn {{
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                padding: 15px 40px;
                border-radius: 12px;
                font-weight: 600;
                font-size: 16px;
                transition: transform 0.2s, box-shadow 0.2s;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            }}

            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
            }}

            .btn:active {{
                transform: translateY(0);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">
                <svg viewBox="0 0 52 52">
                    <polyline points="14 27 22 35 38 19"/>
                </svg>
            </div>

            <h1>Оплата успешна! ✨</h1>
            <p>Ваша подписка активирована. Сейчас вы получите подтверждение в боте.</p>

            <div class="info-box">
                <div class="info-item">
                    <svg viewBox="0 0 24 24" fill="none">
                        <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <span>Доступ к Оракулу активирован</span>
                </div>
                <div class="info-item">
                    <svg viewBox="0 0 24 24" fill="none">
                        <path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
                    </svg>
                    <span>До 10 вопросов в день</span>
                </div>
                <div class="info-item">
                    <svg viewBox="0 0 24 24" fill="none">
                        <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <span>Мгновенные ответы на ваши вопросы</span>
                </div>
            </div>

            <a href="{bot_url}" class="btn">Вернуться в бот</a>
        </div>
    </body>
    </html>
    """

    from fastapi.responses import HTMLResponse
    html_content = html_content.format(bot_url=config.BOT_URL)
    return HTMLResponse(content=html_content)

@router.api_route("/robokassa/fail", methods=["GET", "POST"])
async def robokassa_fail(request: Request):
    # Fail redirect - show error page
    logger.info(f"Robokassa fail page accessed ({request.method})")

    html_content = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Ошибка оплаты - Bot Oracle</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}

            .container {{
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                max-width: 500px;
                width: 100%;
                padding: 40px;
                text-align: center;
                animation: slideUp 0.5s ease-out;
            }}

            @keyframes slideUp {{
                from {{
                    opacity: 0;
                    transform: translateY(30px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}

            .error-icon {{
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 30px;
                animation: scaleIn 0.5s ease-out 0.2s both;
            }}

            @keyframes scaleIn {{
                from {{
                    transform: scale(0);
                }}
                to {{
                    transform: scale(1);
                }}
            }}

            .error-icon svg {{
                width: 50px;
                height: 50px;
                stroke: white;
                stroke-width: 3;
                stroke-linecap: round;
                stroke-linejoin: round;
                fill: none;
            }}

            h1 {{
                color: #2d3748;
                font-size: 28px;
                margin-bottom: 15px;
                font-weight: 700;
            }}

            p {{
                color: #718096;
                font-size: 16px;
                line-height: 1.6;
                margin-bottom: 30px;
            }}

            .info-box {{
                background: #fff5f5;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 30px;
                text-align: left;
                border-left: 4px solid #f5576c;
            }}

            .info-text {{
                color: #742a2a;
                font-size: 14px;
                line-height: 1.6;
            }}

            .btn {{
                display: inline-block;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
                text-decoration: none;
                padding: 15px 40px;
                border-radius: 12px;
                font-weight: 600;
                font-size: 16px;
                transition: transform 0.2s, box-shadow 0.2s;
                box-shadow: 0 4px 15px rgba(245, 87, 108, 0.4);
            }}

            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(245, 87, 108, 0.6);
            }}

            .btn:active {{
                transform: translateY(0);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="error-icon">
                <svg viewBox="0 0 52 52">
                    <line x1="18" y1="18" x2="34" y2="34"/>
                    <line x1="34" y1="18" x2="18" y2="34"/>
                </svg>
            </div>

            <h1>Оплата не прошла</h1>
            <p>К сожалению, платёж не был завершён. Возможно, произошла ошибка или оплата была отменена.</p>

            <div class="info-box">
                <div class="info-text">
                    Если средства были списаны с вашей карты, они автоматически вернутся в течение нескольких минут.
                </div>
            </div>

            <a href="{bot_url}" class="btn">Вернуться в бот</a>
        </div>
    </body>
    </html>
    """

    from fastapi.responses import HTMLResponse
    html_content = html_content.format(bot_url=config.BOT_URL)
    return HTMLResponse(content=html_content)

async def process_successful_payment(user_id: int, inv_id: int, plan_code: str,
                                   amount: float, raw_payload: Dict[str, Any]):
    try:
        # Check if payment already processed
        payment = await PaymentModel.get_payment_by_inv_id(inv_id)
        if payment and payment['status'] == 'success':
            logger.info(f"Payment {inv_id} already processed, skipping")
            return

        # Mark payment as successful
        await PaymentModel.mark_payment_success(inv_id, raw_payload)

        # Save payment record
        await EventModel.log_event(
            user_id=user_id,
            event_type='payment_success',
            meta={
                'inv_id': inv_id,
                'plan_code': plan_code,
                'amount': amount,
                'raw_payload': raw_payload
            }
        )

        # Check if user has active subscription
        existing_subscription = await SubscriptionModel.get_active_subscription(user_id)

        if existing_subscription:
            # Extend existing subscription
            await SubscriptionModel.extend_subscription(user_id, plan_code, amount)
            logger.info(f"Extended subscription for user {user_id}, plan {plan_code}")
        else:
            # Create new subscription
            await SubscriptionModel.create_subscription(user_id, plan_code, amount, inv_id)
            logger.info(f"Created new subscription for user {user_id}, plan {plan_code}")

        # Send confirmation message to user
        try:
            logger.info(f"Attempting to send confirmation message to user_id={user_id}")

            # Get user by internal user_id
            user = await UserModel.get_by_id(user_id)
            if not user:
                logger.warning(f"Cannot send confirmation: user {user_id} not found")
                return

            tg_user_id = user['tg_user_id']
            logger.info(f"User found: tg_user_id={tg_user_id}, age={user.get('age')}, gender={user.get('gender')}")

            persona = persona_factory(user)
            confirmation_message = persona.wrap("Готово ✅ Теперь ты VIP. Оракул ждёт твоих вопросов. Помни: максимум 10 в день.")
            logger.info(f"Confirmation message prepared: {confirmation_message[:50]}...")

            # Create bot instance and send message
            bot = Bot(token=config.BOT_TOKEN)
            try:
                await bot.send_message(tg_user_id, confirmation_message)
                logger.info(f"Confirmation message sent successfully to user {tg_user_id}")
            finally:
                await bot.session.close()
        except Exception as e:
            logger.error(f"Error sending confirmation message: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error processing payment for user {user_id}: {e}")
        raise