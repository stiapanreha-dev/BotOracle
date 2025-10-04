import hashlib
from typing import Dict
from urllib.parse import urlencode
from app.config import config
import logging

logger = logging.getLogger(__name__)

def generate_payment_url(amount: float, inv_id: str, description: str) -> str:
    signature = generate_signature_request(amount, inv_id)

    params = {
        'MerchantLogin': config.ROBO_LOGIN,
        'OutSum': amount,
        'InvoiceID': inv_id,
        'Description': description,
        'SignatureValue': signature,
    }

    if config.ROBO_TEST_MODE:
        params['IsTest'] = '1'

    base_url = "https://auth.robokassa.ru/Merchant/Index.aspx"
    param_string = urlencode(params)

    return f"{base_url}?{param_string}"

def generate_signature_request(amount: float, inv_id: str) -> str:
    s = f"{config.ROBO_LOGIN}:{amount}:{inv_id}:{config.ROBO_PASS1}"
    signature = hashlib.md5(s.encode()).hexdigest()
    logger.info(f"Robokassa signature string: {s}")
    logger.info(f"Robokassa signature: {signature}")
    return signature

def verify_signature_result(amount: str, inv_id: str, signature: str) -> bool:
    expected_signature = generate_signature_result(amount, inv_id)
    return expected_signature.lower() == signature.lower()

def generate_signature_result(amount: str, inv_id: str) -> str:
    s = f"{amount}:{inv_id}:{config.ROBO_PASS2}"
    return hashlib.md5(s.encode()).hexdigest()

def parse_robokassa_callback(form_data: Dict[str, str]) -> Dict[str, str]:
    return {
        'amount': form_data.get('OutSum', ''),
        'inv_id': form_data.get('InvId', ''),
        'signature': form_data.get('SignatureValue', ''),
        'fee': form_data.get('Fee', ''),
        'email': form_data.get('EMail', ''),
        'payment_method': form_data.get('PaymentMethod', ''),
    }