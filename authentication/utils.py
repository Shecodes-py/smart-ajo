import random
import string
import datetime
import logging

from django.conf import settings
from django.utils import timezone
import resend

from .models import OTP  # Ensure the import path matches your app structure

logger = logging.getLogger(__name__)

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def send_email_otp(email, otp):
    resend.api_key = settings.RESEND_API_KEY
    
    subject = "Your Smart Ajo Verification Code"
    html_content = f"""
        <p>Your Smart Ajo verification code is: <strong>{otp}</strong></p>
        <p>Valid for 5 minutes. Do not share this code with anyone.</p>
    """
    
    try:
        params = {
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [email],
            "subject": subject,
            "html": html_content,
        }
        
        resend.Emails.send(params)
        return True
    except Exception as e:
        logger.error(f"Resend Error: {str(e)}")
        return False


def store_otp(identifier, otp):
    """
    Stores OTP using the database model. 
    'identifier' can be a phone number or email address.
    """
    OTP.objects.filter(phone_number=identifier).delete()
    
    # Save new OTP record
    OTP.objects.create(
        phone_number=identifier,
        code=otp
    )


def verify_otp(identifier, otp_input):
    """
    Verifies input code against the latest stored OTP in DB.
    """
    otp_record = (
        OTP.objects.filter(phone_number=identifier)
        .order_by('-created_at')
        .first()
    )

    if not otp_record:
        return False, "OTP not found. Please request a new one."

    if otp_record.is_expired():
        otp_record.delete()  # Clean up expired record
        return False, "OTP has expired. Please request a new one."

    if otp_record.code != otp_input:
        return False, "Invalid OTP. Please try again."

    # Delete after successful verification (one-time use)
    otp_record.delete()
    return True, "OTP verified successfully."