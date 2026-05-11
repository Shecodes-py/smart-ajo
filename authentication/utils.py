import random
import string
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def send_email_otp(email, otp):
    subject = "Your Smart Ajo Verification Code"
    message = (
        f"Your Smart Ajo verification code is: {otp}\n\n"
        f"Valid for 10 minutes. Do not share this code with anyone."
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])

def store_otp(email, otp, timeout=600):
    key = f'otp_{email}'
    cache.set(key, otp, timeout=timeout)

def verify_otp(email, otp_input):
    key = f'otp_{email}'
    stored_otp = cache.get(key)

    if stored_otp is None:
        return False, "OTP has expired. Please request a new one."
    if stored_otp != otp_input:
        return False, "Invalid OTP. Please try again."

    cache.delete(key)
    return True, "OTP verified successfully."