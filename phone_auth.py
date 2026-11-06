"""Normalize mobile credentials without changing existing email accounts."""
import hashlib,re
from fastapi import HTTPException

def normalize_mobile(value):
    text=re.sub(r'[\s().-]','',str(value).strip())
    if text.startswith('00'):text='+'+text[2:]
    if re.fullmatch(r'09\d{9}',text):text='+63'+text[1:]
    elif re.fullmatch(r'9\d{9}',text):text='+63'+text
    elif re.fullmatch(r'639\d{9}',text):text='+'+text
    if not re.fullmatch(r'\+[1-9]\d{7,14}',text):
        raise HTTPException(400,'Use a valid mobile number, such as 09xxxxxxxxx or +639xxxxxxxxx.')
    return text

def signup_identity(email,mobile):
    email=email.strip().lower();mobile=mobile.strip()
    if bool(email)==bool(mobile):raise HTTPException(400,'Choose either email or mobile number.')
    if mobile:
        phone=normalize_mobile(mobile)
        # Reserved internal identifier; never a deliverable email address.
        return 'phone-'+hashlib.sha256(phone.encode()).hexdigest()[:40]+'@accounts.invalid',phone
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254 or email.endswith('.invalid'):
        raise HTTPException(400,'Enter a valid email address.')
    return email,None

def install_phone_auth(conn):
    with conn() as c:c.execute('CREATE TABLE IF NOT EXISTS user_phones(user_id INTEGER PRIMARY KEY REFERENCES users(id), phone TEXT NOT NULL UNIQUE, verified INTEGER NOT NULL DEFAULT 0)')
