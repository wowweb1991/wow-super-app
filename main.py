import os, sqlite3, secrets, hashlib, hmac, time, base64, re
from contextlib import contextmanager
from fastapi import FastAPI, Request, HTTPException, Header, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE=os.path.dirname(__file__)
DB=os.getenv('DATABASE_PATH',os.path.join(BASE,'wow.db'))
app=FastAPI(title='WOW Super App API',docs_url='/api/docs')
app.mount('/static', StaticFiles(directory=os.path.join(BASE, 'static')), name='static')

def conn():
    c=sqlite3.connect(DB,timeout=20)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA journal_mode=WAL')
    return c

def init():
    with conn() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, salt TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS ai_wallets(user_id INTEGER PRIMARY KEY REFERENCES users(id),credits INTEGER NOT NULL DEFAULT 0 CHECK(credits>=0));
        CREATE TABLE IF NOT EXISTS ai_generations(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),tool TEXT NOT NULL,prompt TEXT NOT NULL,result TEXT NOT NULL,cost INTEGER NOT NULL,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS credit_events(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),delta INTEGER NOT NULL,reason TEXT NOT NULL,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL, description TEXT NOT NULL, price REAL NOT NULL, category TEXT NOT NULL, created_at INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id), body TEXT NOT NULL, created_at INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL, description TEXT NOT NULL, price REAL NOT NULL, created_at INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY,service_id INTEGER NOT NULL REFERENCES services(id),requester_id INTEGER NOT NULL REFERENCES users(id),message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_listing_active ON listings(active,created_at);
        CREATE INDEX IF NOT EXISTS idx_post_active ON posts(active,created_at);
        CREATE INDEX IF NOT EXISTS idx_service_active ON services(active,created_at);
        CREATE INDEX IF NOT EXISTS idx_requests_service ON requests(service_id);''')
init()
def init_rewards():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS reward_wallets(user_id INTEGER PRIMARY KEY REFERENCES users(id), welcome_pending INTEGER NOT NULL DEFAULT 50, welcome_approved INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS referral_codes(user_id INTEGER PRIMARY KEY REFERENCES users(id),code TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS referrals(id INTEGER PRIMARY KEY,referrer_id INTEGER NOT NULL REFERENCES users(id),referred_id INTEGER NOT NULL UNIQUE REFERENCES users(id),status TEXT NOT NULL DEFAULT 'pending',created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS reward_claims(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),amount INTEGER NOT NULL,qr_data TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at INTEGER NOT NULL,processed_at INTEGER);
        CREATE INDEX IF NOT EXISTS idx_referrals_owner ON referrals(referrer_id,status);
        """)
init_rewards()

def ensure_rewards(c,uid):
    c.execute('INSERT OR IGNORE INTO reward_wallets(user_id) VALUES (?)',(uid,))
    c.execute('INSERT OR IGNORE INTO referral_codes(user_id,code) VALUES (?,?)',(uid,secrets.token_urlsafe(9)))

def hashed(password,salt): return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),260000).hex()
def issue(c,uid):
    token=secrets.token_urlsafe(40)
    c.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,int(time.time())+7*86400))
    return token

def user(authorization:str|None):
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401,'Please sign in')
    token=authorization[7:]
    with conn() as c:
        r=c.execute('SELECT u.id,u.name,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
    if not r: raise HTTPException(401,'Session expired. Sign in again')
    return dict(r)

def limited(s,maxlen):
    s=s.strip()
    if not s or len(s)>maxlen: raise HTTPException(400,f'Text must be 1–{maxlen} characters')
    return s

class Auth(BaseModel):
    name:str=''
    email:str
    password:str
    referral_code:str=''
class Listing(BaseModel):
    title:str
    description:str
    category:str='General'
    price:float=Field(ge=0,le=100000000)
class Post(BaseModel): body:str
class Service(BaseModel):
    title:str
    description:str
    price:float=Field(ge=0,le=100000000)
class RequestIn(BaseModel):
    service_id:int
    message:str
class Moderation(BaseModel):
    kind:str
    id:int

@app.get('/')
def home():return FileResponse(os.path.join(BASE,'static','index.html'))
@app.get('/api/health')
def health():return {'status':'ok'}
@app.post('/api/register')
def register(data:Auth):
    email=data.email.strip().lower()
    if '@' not in email or len(email)>254 or len(data.password)<8: raise HTTPException(400,'Use a valid email and password of at least 8 characters')
    salt=secrets.token_hex(16)
    with conn() as c:
        try:
            cur=c.execute('INSERT INTO users(name,email,salt,password_hash,created_at) VALUES (?,?,?,?,?)',(limited(data.name,70),email,salt,hashed(data.password,salt),int(time.time())))
        except sqlite3.IntegrityError: raise HTTPException(409,'Email already registered')
        c.execute('INSERT INTO ai_wallets(user_id,credits) VALUES (?,?)',(cur.lastrowid,10))
        c.execute('INSERT INTO credit_events(user_id,delta,reason,created_at) VALUES (?,?,?,?)',(cur.lastrowid,10,'signup demo credits',int(time.time())))
        ensure_rewards(c,cur.lastrowid)
        code=data.referral_code.strip()
        if code:
            owner=c.execute('SELECT user_id FROM referral_codes WHERE code=?',(code,)).fetchone()
            if owner and owner['user_id']!=cur.lastrowid:
                c.execute('INSERT INTO referrals(referrer_id,referred_id,created_at) VALUES (?,?,?)',(owner['user_id'],cur.lastrowid,int(time.time())))
        token=issue(c,cur.lastrowid)
    return {'token':token}
@app.post('/api/login')
def login(data:Auth):
    with conn() as c:
        r=c.execute('SELECT * FROM users WHERE email=?',(data.email.strip().lower(),)).fetchone()
        if not r or not hmac.compare_digest(hashed(data.password,r['salt']),r['password_hash']): raise HTTPException(401,'Invalid credentials')
        token=issue(c,r['id'])
    return {'token':token}
@app.post('/api/logout')
def logout(authorization:str|None=Header(None)):
    user(authorization)
    with conn() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(authorization[7:].encode()).hexdigest(),))
    return {'ok':True}
@app.get('/api/me')
def me(authorization:str|None=Header(None)):return user(authorization)
@app.get('/api/feed/{kind}')
def feed(kind:str,q:str='',page:int=1):
    if kind not in ('listings','posts','services'):raise HTTPException(404)
    page=max(1,min(page,10000))
    q=q[:80]
    column='body' if kind=='posts' else 'title'
    with conn() as c:
        rows=c.execute(f'''SELECT t.*,u.name AS author FROM {kind} t JOIN users u ON u.id=t.user_id WHERE t.active=1 AND (t.{column} LIKE ? OR t.{('body' if kind=='posts' else 'description')} LIKE ?) ORDER BY t.created_at DESC,t.id DESC LIMIT 30 OFFSET ?''',(f'%{q}%',f'%{q}%',(page-1)*30)).fetchall()
    return [dict(x) for x in rows]
@app.post('/api/listings')
def listing(data:Listing,authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:r=c.execute('INSERT INTO listings(user_id,title,description,price,category,created_at) VALUES (?,?,?,?,?,?)',(u['id'],limited(data.title,100),limited(data.description,1000),data.price,limited(data.category,40),int(time.time())))
    return {'id':r.lastrowid}
@app.post('/api/posts')
def post(data:Post,authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:r=c.execute('INSERT INTO posts(user_id,body,created_at) VALUES (?,?,?)',(u['id'],limited(data.body,1500),int(time.time())))
    return {'id':r.lastrowid}
@app.post('/api/services')
def service(data:Service,authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:r=c.execute('INSERT INTO services(user_id,title,description,price,created_at) VALUES (?,?,?,?,?)',(u['id'],limited(data.title,100),limited(data.description,1000),data.price,int(time.time())))
    return {'id':r.lastrowid}
@app.post('/api/requests')
def request_service(data:RequestIn,authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:
        s=c.execute('SELECT id,user_id FROM services WHERE id=? AND active=1',(data.service_id,)).fetchone()
        if not s:raise HTTPException(404,'Service not found')
        if s['user_id']==u['id']:raise HTTPException(400,'Cannot request your own service')
        r=c.execute('INSERT INTO requests(service_id,requester_id,message,created_at) VALUES (?,?,?,?)',(data.service_id,u['id'],limited(data.message,500),int(time.time())))
    return {'id':r.lastrowid}
@app.get('/api/requests')
def my_requests(authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:
        rows=c.execute('''SELECT r.id,r.message,r.status,r.created_at,s.title,u.name AS requester FROM requests r JOIN services s ON s.id=r.service_id JOIN users u ON u.id=r.requester_id WHERE s.user_id=? OR r.requester_id=? ORDER BY r.id DESC LIMIT 100''',(u['id'],u['id'])).fetchall()
    return [dict(x) for x in rows]
@app.delete('/api/{kind}/{item_id}')
def remove(kind:str,item_id:int,authorization:str|None=Header(None)):
    u=user(authorization)
    if kind not in ('listings','posts','services'):raise HTTPException(404)
    with conn() as c:
        r=c.execute(f'SELECT user_id FROM {kind} WHERE id=?',(item_id,)).fetchone()
        if not r:raise HTTPException(404)
        if r['user_id']!=u['id'] and u['role']!='admin':raise HTTPException(403)
        c.execute(f'UPDATE {kind} SET active=0 WHERE id=?',(item_id,))
    return {'ok':True}

# AI text services. Provider credentials stay on the server.
import json, urllib.request, urllib.error
AI_TOOLS={'caption':0,'description':2,'business':2,'video_script':2,'poster':5,'logo':10,'video':30,'website':50}
TEXT_TOOLS={'caption','description','business','video_script'}
class AIInput(BaseModel):
    tool:str
    prompt:str=Field(min_length=3,max_length=800)
    language:str='English'

def provider_text(prompt,language,tool):
    key=os.getenv('OPENAI_API_KEY','')
    if not key:raise HTTPException(503,'AI provider is not connected. No credits charged.')
    body=json.dumps({'model':os.getenv('OPENAI_TEXT_MODEL','gpt-4.1-mini'),'store':False,'max_output_tokens':1000,
        'instructions':f'Write {tool} content in {language}. Use only supplied business facts. Do not invent prices, links, guarantees or testimonials. For video_script provide scenes, voiceover and on-screen text. Return a draft for human review.',
        'input':prompt}).encode()
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=45) as response:data=json.load(response)
    except (urllib.error.URLError,TimeoutError,ValueError):raise HTTPException(502,'AI provider unavailable. No credits charged.')
    text='\n'.join(part.get('text','') for item in data.get('output',[]) for part in item.get('content',[]) if part.get('type')=='output_text').strip()
    if not text:raise HTTPException(502,'AI provider returned no text. No credits charged.')
    return text

@app.get('/api/ai/tools')
def ai_tools():
    connected=bool(os.getenv('OPENAI_API_KEY'))
    return {'tools':[{'id':k,'credits':v,'mode':('ai' if connected else 'provider-required') if k in TEXT_TOOLS else 'coming-soon'} for k,v in AI_TOOLS.items()],'payments_live':False,'provider_connected':connected}
@app.get('/ai-services')
def ai_page():return FileResponse(os.path.join(BASE,'static','ai-services.html'))
@app.get('/api/ai/wallet')
def ai_wallet(authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:r=c.execute('SELECT credits FROM ai_wallets WHERE user_id=?',(u['id'],)).fetchone()
    return {'credits':r['credits'] if r else 0,'currency':'demo credits','payments_live':False}
@app.post('/api/ai/generate')
def ai_generate(data:AIInput,authorization:str|None=Header(None)):
    u=user(authorization)
    if data.tool not in TEXT_TOOLS:raise HTTPException(400,'This tool is not available for generation')
    if data.language not in ('English','Tagalog','Bisaya'):raise HTTPException(400,'Unsupported language')
    prompt=limited(data.prompt,800);cost=AI_TOOLS[data.tool]
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        recent=c.execute('SELECT COUNT(*) FROM ai_generations WHERE user_id=? AND created_at>?',(u['id'],int(time.time())-3600)).fetchone()[0]
        if recent>=20:raise HTTPException(429,'Hourly limit reached. Try again later.')
        cur=c.execute('UPDATE ai_wallets SET credits=credits-? WHERE user_id=? AND credits>=?',(cost,u['id'],cost))
        if cur.rowcount!=1:raise HTTPException(402,'Insufficient demo credits')
        # A failed provider call rolls back the reservation and does not create history.
        result=provider_text(prompt,data.language,data.tool)
        c.execute('INSERT INTO credit_events(user_id,delta,reason,created_at) VALUES (?,?,?,?)',(u['id'],-cost,'AI generation: '+data.tool,int(time.time())))
        c.execute('INSERT INTO ai_generations(user_id,tool,prompt,result,cost,created_at) VALUES (?,?,?,?,?,?)',(u['id'],data.tool,prompt,result,cost,int(time.time())))
    return {'result':result,'credits_charged':cost,'mode':'ai'}
@app.get('/api/ai/history')
def ai_history(authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:r=c.execute('SELECT id,tool,prompt,result,cost,created_at FROM ai_generations WHERE user_id=? ORDER BY id DESC LIMIT 30',(u['id'],)).fetchall()
    return [dict(x) for x in r]

# Cash rewards are NOT activated automatically. Admin must verify welcome eligibility,
# each referred account, and every payout. No automatic money transfers.
@app.get('/api/rewards/wallet')
def rewards_wallet(authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:
        ensure_rewards(c,u['id'])
        w=c.execute('SELECT * FROM reward_wallets WHERE user_id=?',(u['id'],)).fetchone()
        code=c.execute('SELECT code FROM referral_codes WHERE user_id=?',(u['id'],)).fetchone()['code']
        approved=c.execute("SELECT COUNT(*) n FROM referrals WHERE referrer_id=? AND status='approved'",(u['id'],)).fetchone()['n']
        pending=c.execute("SELECT COUNT(*) n FROM referrals WHERE referrer_id=? AND status='pending'",(u['id'],)).fetchone()['n']
        paid=c.execute("SELECT COALESCE(SUM(amount),0) n FROM reward_claims WHERE user_id=? AND status IN ('approved','paid','pending')",(u['id'],)).fetchone()['n']
    earned=(50 if w['welcome_approved'] else 0)+10*approved
    return {'referral_code':code,'verified_referrals':approved,'pending_referrals':pending,'earned_php':earned,'reserved_or_paid_php':paid,'available_php':max(0,earned-paid),'minimum_withdrawal_php':100,'welcome_status':'approved' if w['welcome_approved'] else 'pending verification','terms':'₱50 eligible welcome bonus; ₱10 per verified referral; ₱100 minimum withdrawal; subject to manual verification and reward budget. No payout guaranteed before approval.'}

class QRClaim(BaseModel):
    qr_image_data_url:str=Field(min_length=100,max_length=500000)

@app.post('/api/rewards/withdraw')
def rewards_withdraw(data:QRClaim,authorization:str|None=Header(None)):
    u=user(authorization)
    if not re.fullmatch(r'data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+',data.qr_image_data_url):
        raise HTTPException(400,'Upload a PNG, JPEG or WebP GCash QR image')
    try: raw=base64.b64decode(data.qr_image_data_url.split(',',1)[1],validate=True)
    except Exception: raise HTTPException(400,'Invalid image encoding')
    if len(raw)>350000:raise HTTPException(400,'QR image must be smaller than 350KB')
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        ensure_rewards(c,u['id'])
        w=c.execute('SELECT welcome_approved FROM reward_wallets WHERE user_id=?',(u['id'],)).fetchone()
        n=c.execute("SELECT COUNT(*) n FROM referrals WHERE referrer_id=? AND status='approved'",(u['id'],)).fetchone()['n']
        reserved=c.execute("SELECT COALESCE(SUM(amount),0) n FROM reward_claims WHERE user_id=? AND status IN ('pending','approved','paid')",(u['id'],)).fetchone()['n']
        available=50*w['welcome_approved']+10*n-reserved
        if available<100:raise HTTPException(400,'Minimum withdrawal is ₱100. Check verified rewards balance.')
        c.execute('INSERT INTO reward_claims(user_id,amount,qr_data,created_at) VALUES (?,?,?,?)',(u['id'],available,data.qr_image_data_url,int(time.time())))
    return {'status':'pending','amount_php':available,'message':'Request submitted. Admin verification and manual payout required.'}

@app.post('/api/rewards/withdraw-messenger')
def rewards_withdraw_messenger(authorization:str|None=Header(None)):
    """Reserve verified balance; user separately sends GCash QR to official Messenger."""
    u=user(authorization)
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        ensure_rewards(c,u['id'])
        w=c.execute('SELECT welcome_approved FROM reward_wallets WHERE user_id=?',(u['id'],)).fetchone()
        n=c.execute("SELECT COUNT(*) n FROM referrals WHERE referrer_id=? AND status='approved'",(u['id'],)).fetchone()['n']
        reserved=c.execute("SELECT COALESCE(SUM(amount),0) n FROM reward_claims WHERE user_id=? AND status IN ('pending','approved','paid')",(u['id'],)).fetchone()['n']
        available=50*w['welcome_approved']+10*n-reserved
        if available<100:raise HTTPException(400,'Minimum withdrawal is ₱100 in approved rewards.')
        claim=c.execute('INSERT INTO reward_claims(user_id,amount,qr_data,created_at) VALUES (?,?,?,?)',(u['id'],available,'MESSENGER_QR_PENDING',int(time.time())))
        claim_id=claim.lastrowid
    return {'status':'pending','claim_id':claim_id,'amount_php':available,'message':'Send GCash QR via official WOW WEB STUDIO Facebook Messenger, including claim ID and registered email. Admin verifies before manual payout.'}

@app.get('/api/rewards/claims')
def my_reward_claims(authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c: rows=c.execute('SELECT id,amount,status,created_at FROM reward_claims WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()
    return [dict(r) for r in rows]

def admin_only(authorization):
    u=user(authorization)
    if u['role']!='admin':raise HTTPException(403,'Admin only')
    return u

@app.get('/api/admin/rewards')
def admin_rewards(authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        claims=c.execute('SELECT r.id,r.user_id,u.email,r.amount,r.status,r.created_at FROM reward_claims r JOIN users u ON u.id=r.user_id ORDER BY r.id DESC LIMIT 100').fetchall()
        refs=c.execute('SELECT r.id,r.referrer_id,r.referred_id,r.status,r.created_at FROM referrals r ORDER BY r.id DESC LIMIT 100').fetchall()
        welcomes=c.execute('SELECT w.user_id,u.email,w.welcome_approved FROM reward_wallets w JOIN users u ON u.id=w.user_id ORDER BY w.user_id DESC LIMIT 100').fetchall()
    return {'claims':[dict(x) for x in claims],'referrals':[dict(x) for x in refs],'welcome':[dict(x) for x in welcomes]}

@app.get('/api/admin/rewards/qr/{claim_id}')
def admin_claim_qr(claim_id:int,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c: row=c.execute('SELECT qr_data FROM reward_claims WHERE id=?',(claim_id,)).fetchone()
    if not row:raise HTTPException(404)
    return {'image_data_url':None if row['qr_data']=='MESSENGER_QR_PENDING' else row['qr_data'], 'via_messenger':row['qr_data']=='MESSENGER_QR_PENDING'}

class RewardDecision(BaseModel):
    kind:str
    item_id:int
    status:str

@app.post('/api/admin/rewards/decision')
def admin_reward_decision(data:RewardDecision,authorization:str|None=Header(None)):
    admin_only(authorization)
    if data.kind=='referral' and data.status in ('approved','rejected'):
        table='referrals'; allowed=('pending',)
    elif data.kind=='claim' and data.status in ('approved','rejected','paid'):
        table='reward_claims'; allowed=('pending','approved') if data.status=='paid' else ('pending',)
    elif data.kind=='welcome' and data.status in ('approved','rejected'):
        with conn() as c:
            c.execute('INSERT OR IGNORE INTO reward_wallets(user_id) VALUES (?)',(data.item_id,))
            c.execute('UPDATE reward_wallets SET welcome_approved=?,welcome_pending=0 WHERE user_id=? AND welcome_pending=1',(int(data.status=='approved'),data.item_id))
        return {'ok':True}
    else:raise HTTPException(400,'Invalid decision')
    with conn() as c:
        r=c.execute(f'SELECT status FROM {table} WHERE id=?',(data.item_id,)).fetchone()
        if not r or r['status'] not in allowed:raise HTTPException(409,'Not found or invalid transition')
        c.execute(f'UPDATE {table} SET status=? WHERE id=?',(data.status,data.item_id))
    return {'ok':True}

@app.get('/api/quran/daily')
def daily_quran():
    # Curated, stable selection; display reference and link for full authoritative context.
    verses=[('Al-Fatihah','1:5','You alone we worship and You alone we ask for help.'),('Ash-Sharh','94:5','So, surely with hardship comes ease.'),('Al-Baqarah','2:286','Allah does not burden a soul beyond that it can bear.'),('Ar-Rahman','55:13','Then which of your Lord’s favors will you both deny?'),('Al-Ikhlas','112:1','Say, “He is Allah—One.”')]
    from datetime import datetime,timedelta,timezone
    ph=datetime.now(timezone(timedelta(hours=8))).date()
    surah,ref,meaning=verses[ph.toordinal()%len(verses)]
    return {'date':str(ph),'surah':surah,'reference':ref,'english_excerpt':meaning,'source_url':'https://quran.com/'+ref,'note':'Selected verse excerpt; visit Quran.com for full Arabic text, translation and context.'}


# WOW JOBS: any registered user may post; posts are explicitly unverified.
def init_jobs():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),title TEXT NOT NULL,description TEXT NOT NULL,location TEXT NOT NULL,job_type TEXT NOT NULL,salary TEXT NOT NULL,contact TEXT NOT NULL,created_at INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS job_applications(id INTEGER PRIMARY KEY,job_id INTEGER NOT NULL REFERENCES jobs(id),applicant_id INTEGER NOT NULL REFERENCES users(id),message TEXT NOT NULL,contact TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(job_id,applicant_id));
        CREATE TABLE IF NOT EXISTS job_reports(id INTEGER PRIMARY KEY,job_id INTEGER NOT NULL REFERENCES jobs(id),reporter_id INTEGER NOT NULL REFERENCES users(id),reason TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(job_id,reporter_id));
        CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(active,created_at);
        """)
init_jobs()

class JobIn(BaseModel):
    title:str
    description:str
    location:str
    job_type:str='Other'
    salary:str='Negotiable'
    contact:str

class JobApplicationIn(BaseModel):
    message:str
    contact:str

class JobReportIn(BaseModel):
    reason:str

@app.get('/jobs')
def jobs_page():
    return FileResponse(os.path.join(BASE,'static','jobs.html'))

@app.get('/api/jobs')
def browse_jobs(q:str='',page:int=1,job_type:str=''):
    page=max(1,min(page,1000));q=q.strip()[:80];job_type=job_type.strip()[:40]
    with conn() as c:
        rows=c.execute("""SELECT j.id,j.title,j.description,j.location,j.job_type,j.salary,j.contact,j.created_at,u.name AS posted_by,0 AS employer_verified FROM jobs j JOIN users u ON u.id=j.user_id WHERE j.active=1 AND (j.title LIKE ? OR j.description LIKE ? OR j.location LIKE ?) AND (?='' OR j.job_type=?) ORDER BY j.created_at DESC,j.id DESC LIMIT 30 OFFSET ?""",(f'%{q}%',f'%{q}%',f'%{q}%',job_type,job_type,(page-1)*30)).fetchall()
    return [dict(r) for r in rows]

@app.post('/api/jobs')
def create_job(data:JobIn,authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:
        r=c.execute('INSERT INTO jobs(user_id,title,description,location,job_type,salary,contact,created_at) VALUES (?,?,?,?,?,?,?,?)',(u['id'],limited(data.title,120),limited(data.description,3000),limited(data.location,120),limited(data.job_type,40),limited(data.salary,100),limited(data.contact,180),int(time.time())))
    return {'id':r.lastrowid,'employer_verified':False}

@app.get('/api/jobs/mine')
def my_jobs(authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c: rows=c.execute('SELECT * FROM jobs WHERE user_id=? ORDER BY created_at DESC',(u['id'],)).fetchall()
    return [dict(r) for r in rows]

@app.delete('/api/jobs/{job_id}')
def delete_job(job_id:int,authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:
        r=c.execute('SELECT user_id FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not r:raise HTTPException(404,'Job not found')
        if r['user_id']!=u['id'] and u['role']!='admin':raise HTTPException(403,'Not your job')
        c.execute('UPDATE jobs SET active=0 WHERE id=?',(job_id,))
    return {'ok':True}

@app.post('/api/jobs/{job_id}/apply')
def apply_job(job_id:int,data:JobApplicationIn,authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:
        job=c.execute('SELECT user_id FROM jobs WHERE id=? AND active=1',(job_id,)).fetchone()
        if not job:raise HTTPException(404,'Job not found')
        if job['user_id']==u['id']:raise HTTPException(400,'Cannot apply to your own job')
        try:
            r=c.execute('INSERT INTO job_applications(job_id,applicant_id,message,contact,created_at) VALUES (?,?,?,?,?)',(job_id,u['id'],limited(data.message,2000),limited(data.contact,180),int(time.time())))
        except sqlite3.IntegrityError:raise HTTPException(409,'Already applied')
    return {'id':r.lastrowid,'status':'submitted'}

@app.get('/api/jobs/{job_id}/applications')
def job_applications(job_id:int,authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:
        job=c.execute('SELECT user_id FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not job:raise HTTPException(404,'Job not found')
        if job['user_id']!=u['id'] and u['role']!='admin':raise HTTPException(403)
        rows=c.execute('SELECT a.id,a.message,a.contact,a.created_at,u.name AS applicant FROM job_applications a JOIN users u ON u.id=a.applicant_id WHERE a.job_id=? ORDER BY a.created_at DESC',(job_id,)).fetchall()
    return [dict(r) for r in rows]

@app.post('/api/jobs/{job_id}/report')
def report_job(job_id:int,data:JobReportIn,authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:
        if not c.execute('SELECT id FROM jobs WHERE id=? AND active=1',(job_id,)).fetchone():raise HTTPException(404)
        try:c.execute('INSERT INTO job_reports(job_id,reporter_id,reason,created_at) VALUES (?,?,?,?)',(job_id,u['id'],limited(data.reason,500),int(time.time())))
        except sqlite3.IntegrityError:raise HTTPException(409,'Already reported')
    return {'status':'reported'}

@app.get('/api/admin/jobs/reports')
def admin_job_reports(authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c: rows=c.execute('SELECT r.id,r.job_id,r.reason,r.created_at,j.title FROM job_reports r JOIN jobs j ON j.id=r.job_id ORDER BY r.created_at DESC LIMIT 200').fetchall()
    return [dict(r) for r in rows]


# WOW NINA product catalog (admin managed)
def init_nina():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS nina_products (id INTEGER PRIMARY KEY, title TEXT NOT NULL, brand TEXT NOT NULL, price REAL NOT NULL, sizes TEXT NOT NULL, stock INTEGER NOT NULL, condition TEXT NOT NULL, description TEXT NOT NULL, image_path TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL)""")
init_nina()

class NinaProduct(BaseModel):
    title:str
    brand:str=''
    price:float=Field(ge=0,le=100000000)
    sizes:str=''
    stock:int=Field(ge=0,le=1000000)
    condition:str='Brand New'
    description:str=''
    active:bool=True

@app.get('/api/wow-nina/products')
def nina_list(admin:bool=False, authorization:str|None=Header(None)):
    if admin: admin_only(authorization)
    with conn() as c:
        rows=c.execute('SELECT * FROM nina_products '+('' if admin else 'WHERE active=1 ' )+'ORDER BY created_at DESC,id DESC').fetchall()
    return {'products':[dict(r) for r in rows]}

@app.post('/api/admin/wow-nina/products')
def nina_create(data:NinaProduct,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        cur=c.execute('INSERT INTO nina_products(title,brand,price,sizes,stock,condition,description,created_at,active) VALUES (?,?,?,?,?,?,?,?,?)',(limited(data.title,120),data.brand[:80],data.price,data.sizes[:150],data.stock,data.condition[:40],data.description[:1500],int(time.time()),int(data.active)))
        return {'ok':True,'id':cur.lastrowid}

@app.put('/api/admin/wow-nina/products/{pid}')
def nina_update(pid:int,data:NinaProduct,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        cur=c.execute('UPDATE nina_products SET title=?,brand=?,price=?,sizes=?,stock=?,condition=?,description=?,active=? WHERE id=?',(limited(data.title,120),data.brand[:80],data.price,data.sizes[:150],data.stock,data.condition[:40],data.description[:1500],int(data.active),pid))
        if not cur.rowcount: raise HTTPException(404,'Product not found')
    return {'ok':True}

@app.delete('/api/admin/wow-nina/products/{pid}')
def nina_delete(pid:int,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        c.execute('UPDATE nina_products SET active=0 WHERE id=?',(pid,))
    return {'ok':True}

@app.post('/api/admin/wow-nina/products/{pid}/photo')
async def nina_photo(pid:int,photo:UploadFile=File(...),authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        if not c.execute('SELECT id FROM nina_products WHERE id=?',(pid,)).fetchone(): raise HTTPException(404,'Product not found')
    import io
    from PIL import Image, UnidentifiedImageError
    raw=await photo.read(5*1024*1024+1)
    if len(raw)>5*1024*1024: raise HTTPException(413,'Max photo size is 5 MB')
    try:
        im=Image.open(io.BytesIO(raw)); im.verify()
        im=Image.open(io.BytesIO(raw)).convert('RGB'); im.thumbnail((1400,1400))
    except (UnidentifiedImageError,ValueError,OSError): raise HTTPException(400,'Invalid image')
    folder=os.getenv('UPLOAD_DIR',os.path.join(BASE,'static','uploads'))
    os.makedirs(folder,exist_ok=True)
    filename='nina_'+str(pid)+'_'+secrets.token_hex(8)+'.webp'
    im.save(os.path.join(folder,filename),'WEBP',quality=82)
    # Serve via dedicated route so UPLOAD_DIR can live outside the app tree.
    with conn() as c: c.execute('UPDATE nina_products SET image_path=? WHERE id=?',(filename,pid))
    return {'ok':True,'image_url':'/api/wow-nina/photo/'+filename}

@app.get('/api/wow-nina/photo/{filename}')
def nina_serve_photo(filename:str):
    if not re.fullmatch(r'nina_[0-9]+_[0-9a-f]{16}\.webp',filename): raise HTTPException(404,'Not found')
    folder=os.getenv('UPLOAD_DIR',os.path.join(BASE,'static','uploads'))
    path=os.path.join(folder,filename)
    if not os.path.isfile(path): raise HTTPException(404,'Photo unavailable')
    return FileResponse(path,media_type='image/webp')

@app.get('/admin/wow-nina')
def nina_admin_page(): return FileResponse(os.path.join(BASE,'static','nina-admin.html'))


# Platform-wide admin: digital products and centralized moderation access.
def init_digital_catalog():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS digital_products (id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', price REAL NOT NULL DEFAULT 0, buy_url TEXT NOT NULL, image_url TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL)""")
init_digital_catalog()

class DigitalProduct(BaseModel):
    title:str
    description:str=''
    price:float=Field(ge=0,le=100000000)
    buy_url:str
    image_url:str=''
    active:bool=True

def valid_url(value):
    from urllib.parse import urlsplit
    u=urlsplit(value.strip())
    if u.scheme!='https' or not u.hostname or u.username or u.password or len(value)>1200: raise HTTPException(400,'Use a valid HTTPS link')
    return value.strip()

@app.get('/api/digital-shop/products')
def digital_products(admin:bool=False,authorization:str|None=Header(None)):
    if admin:admin_only(authorization)
    with conn() as c:
        rows=c.execute('SELECT * FROM digital_products '+('' if admin else 'WHERE active=1 ')+'ORDER BY created_at DESC,id DESC').fetchall()
    return {'products':[dict(r) for r in rows]}

@app.post('/api/admin/digital-shop/products')
def digital_create(data:DigitalProduct,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        cur=c.execute('INSERT INTO digital_products(title,description,price,buy_url,image_url,active,created_at) VALUES(?,?,?,?,?,?,?)',(limited(data.title,120),data.description[:1500],data.price,valid_url(data.buy_url),valid_url(data.image_url) if data.image_url else '',int(data.active),int(time.time())))
        return {'ok':True,'id':cur.lastrowid}

@app.put('/api/admin/digital-shop/products/{pid}')
def digital_update(pid:int,data:DigitalProduct,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        cur=c.execute('UPDATE digital_products SET title=?,description=?,price=?,buy_url=?,image_url=?,active=? WHERE id=?',(limited(data.title,120),data.description[:1500],data.price,valid_url(data.buy_url),valid_url(data.image_url) if data.image_url else '',int(data.active),pid))
        if not cur.rowcount:raise HTTPException(404,'Not found')
    return {'ok':True}

@app.delete('/api/admin/digital-shop/products/{pid}')
def digital_hide(pid:int,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        cur=c.execute('UPDATE digital_products SET active=0 WHERE id=?',(pid,))
        if not cur.rowcount:raise HTTPException(404,'Not found')
    return {'ok':True}

@app.get('/admin')
def platform_admin():return FileResponse(os.path.join(BASE,'static','platform-admin.html'))


# Platform-wide administrator dashboard and recent activity.
def init_platform_admin():
    with conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS admin_notifications_seen(admin_id INTEGER PRIMARY KEY, last_seen INTEGER NOT NULL DEFAULT 0)")
init_platform_admin()

@app.get('/api/admin/platform/overview')
def platform_overview(authorization:str|None=Header(None)):
    admin=admin_only(authorization)
    with conn() as c:
        stats={}
        for name,query in {
            'members':'SELECT COUNT(*) FROM users',
            'signups_today':"SELECT COUNT(*) FROM users WHERE created_at>=strftime('%s','now','start of day')",
            'community_posts':'SELECT COUNT(*) FROM posts WHERE active=1',
            'marketplace_listings':'SELECT COUNT(*) FROM listings WHERE active=1',
            'services':'SELECT COUNT(*) FROM services WHERE active=1',
            'jobs':'SELECT COUNT(*) FROM jobs WHERE active=1',
            'pending_referrals':"SELECT COUNT(*) FROM referrals WHERE status='pending'",
            'pending_withdrawals':"SELECT COUNT(*) FROM reward_claims WHERE status='pending'",
            'digital_products':'SELECT COUNT(*) FROM digital_products WHERE active=1',
            'wow_nina_products':'SELECT COUNT(*) FROM nina_products WHERE active=1',
        }.items():
            try:stats[name]=c.execute(query).fetchone()[0]
            except sqlite3.OperationalError:stats[name]=0
        events=[]
        sources=[('signup','SELECT id,name AS detail,created_at FROM users'),('community','SELECT id,body AS detail,created_at FROM posts'),('marketplace','SELECT id,title AS detail,created_at FROM listings'),('service','SELECT id,title AS detail,created_at FROM services'),('referral','SELECT id,status AS detail,created_at FROM referrals'),('withdrawal','SELECT id,status AS detail,created_at FROM reward_claims'),('job','SELECT id,title AS detail,created_at FROM jobs')]
        for kind,q in sources:
            try:
                for r in c.execute(q+' ORDER BY created_at DESC LIMIT 30').fetchall():events.append({'type':kind,'id':r['id'],'detail':str(r['detail'])[:140],'created_at':r['created_at']})
            except sqlite3.OperationalError:pass
        events=sorted(events,key=lambda e:e['created_at'],reverse=True)[:80]
        seen=c.execute('SELECT last_seen FROM admin_notifications_seen WHERE admin_id=?',(admin['id'],)).fetchone()
        last=seen['last_seen'] if seen else 0
        unread=sum(e['created_at']>last for e in events)
    return {'stats':stats,'events':events,'unread':unread,'last_seen':last,'news_mode':'public RSS feed, refresh on request; subject to publisher availability'}

@app.post('/api/admin/platform/notifications/read')
def platform_mark_read(authorization:str|None=Header(None)):
    a=admin_only(authorization)
    with conn() as c:c.execute('INSERT INTO admin_notifications_seen(admin_id,last_seen) VALUES(?,?) ON CONFLICT(admin_id) DO UPDATE SET last_seen=excluded.last_seen',(a['id'],int(time.time())))
    return {'ok':True}

@app.get('/api/news/daily')
def daily_news():
    # Read-only public news: no fabricated stories. Short excerpts and publisher links.
    import urllib.request,xml.etree.ElementTree as ET,email.utils,datetime
    feeds=[('BBC World','https://feeds.bbci.co.uk/news/world/rss.xml'),('BBC Technology','https://feeds.bbci.co.uk/news/technology/rss.xml'),('GMA News Philippines','https://www.gmanetwork.com/news/rss/news/nation/feed.xml'),('Philippine News Agency','https://www.pna.gov.ph/rss-feed')]
    stories=[]
    for source,url in feeds:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'WOWSuperApp/1.0 news feed reader'})
            with urllib.request.urlopen(req,timeout=4) as response:
                data=response.read(250000)
            root=ET.fromstring(data)
            for item in root.findall('./channel/item')[:7]:
                title=(item.findtext('title') or '').strip();link=(item.findtext('link') or '').strip();published=(item.findtext('pubDate') or '').strip()
                if title and link.startswith('https://'):
                    stories.append({'title':title[:180],'url':link,'source':source,'region':'Philippines' if source in ('GMA News Philippines','Philippine News Agency') else 'World','published':published})
        except Exception:continue
    return {'stories':stories[:24],'updated_at':int(time.time()),'live':bool(stories),'message':'Headlines supplied by their publishers. Feed may be unavailable; no stories are invented.'}


# Original daily motivation: admin-managed, deterministic Philippine calendar day.
from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_MOTIVATION = [
 "Small progress is still progress. Keep moving, even when nobody is watching.",
 "Your beginning does not decide your ending. Your choices today matter.",
 "You can be kind and still have boundaries. Both are strengths.",
 "Not every quiet season is an empty one. Some seasons are for growing.",
 "A difficult day does not erase the courage it took to show up.",
 "Make room for learning. You do not have to know everything to begin.",
 "Rest when you need to, then return to what matters to you.",
 "The dream becomes more real each time you take one practical step.",
 "Your pace is yours. Consistency matters more than comparison.",
 "A new day is another opportunity to choose what deserves your energy.",
 "Let your work speak, but do not forget to enjoy the journey.",
 "You can start again without calling your earlier efforts a failure.",
 "Build something meaningful, one honest decision at a time.",
 "Even the smallest act of courage can change the direction of a day.",
 "Focus on what you can improve, not on what you cannot control."
]

def init_motivation():
    with conn() as c:
        c.execute('CREATE TABLE IF NOT EXISTS motivation_quotes(id INTEGER PRIMARY KEY, quote TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL)')
        if c.execute('SELECT COUNT(*) FROM motivation_quotes').fetchone()[0] == 0:
            c.executemany('INSERT INTO motivation_quotes(quote,created_at) VALUES (?,?)',[(q,int(time.time())) for q in DEFAULT_MOTIVATION])
init_motivation()

@app.get('/api/motivation/daily')
def motivation_daily():
    day=datetime.now(ZoneInfo('Asia/Manila')).date()
    with conn() as c:
        quotes=c.execute('SELECT id,quote FROM motivation_quotes WHERE active=1 ORDER BY id').fetchall()
    if not quotes:return {'quote':None,'author':'Muzayyanah','date':day.isoformat()}
    chosen=quotes[day.toordinal()%len(quotes)]
    return {'id':chosen['id'],'quote':chosen['quote'],'author':'Muzayyanah','date':day.isoformat(),'timezone':'Asia/Manila'}

class MotivationInput(BaseModel):
    quote:str=Field(min_length=5,max_length=500)

@app.get('/api/admin/motivation')
def motivation_list(authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:rows=c.execute('SELECT id,quote,active,created_at FROM motivation_quotes ORDER BY id DESC').fetchall()
    return {'quotes':[dict(r) for r in rows]}

@app.post('/api/admin/motivation')
def motivation_add(body:MotivationInput,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        cur=c.execute('INSERT INTO motivation_quotes(quote,created_at) VALUES (?,?)',(body.quote.strip(),int(time.time())))
        return {'ok':True,'id':cur.lastrowid}

@app.put('/api/admin/motivation/{quote_id}')
def motivation_edit(quote_id:int,body:MotivationInput,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        cur=c.execute('UPDATE motivation_quotes SET quote=? WHERE id=?',(body.quote.strip(),quote_id))
        if not cur.rowcount:raise HTTPException(404,'Quote not found')
    return {'ok':True}

@app.delete('/api/admin/motivation/{quote_id}')
def motivation_hide(quote_id:int,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        cur=c.execute('UPDATE motivation_quotes SET active=0 WHERE id=?',(quote_id,))
        if not cur.rowcount:raise HTTPException(404,'Quote not found')
    return {'ok':True}

@app.get('/admin/motivation')
def motivation_admin_page(authorization:str|None=Header(None)):
    return FileResponse(os.path.join(BASE,'static','motivation-admin.html'))

# WOW Marketing Studio: admin-only draft, visual and short video creator.
# Assets are served via authenticated endpoints; nothing is auto-published.
from fastapi.responses import StreamingResponse
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import subprocess, tempfile, pathlib

MARKETING_DIR=os.getenv('MARKETING_ASSET_DIR',os.path.join(BASE,'marketing_assets'))
os.makedirs(MARKETING_DIR,exist_ok=True)

def init_marketing():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS marketing_drafts(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL,brand TEXT NOT NULL,topic TEXT NOT NULL,channel TEXT NOT NULL,caption TEXT NOT NULL,headline TEXT NOT NULL,cta TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)""")
init_marketing()

class MarketingCreate(BaseModel):
    brand:str=Field(min_length=2,max_length=60)
    topic:str=Field(min_length=3,max_length=220)
    channel:str=Field(default='Facebook',max_length=40)
    cta:str=Field(default='Explore now',max_length=80)
    use_ai:bool=False
    language:str='English'

class MarketingStatus(BaseModel):
    status:str

def marketing_get(draft_id,authorization):
    admin_only(authorization)
    with conn() as c:r=c.execute('SELECT * FROM marketing_drafts WHERE id=?',(draft_id,)).fetchone()
    if not r:raise HTTPException(404,'Draft not found')
    return dict(r)

@app.get('/admin/marketing')
def marketing_page():
    return FileResponse(os.path.join(BASE,'static','marketing-admin.html'))

@app.post('/api/admin/marketing/drafts')
def marketing_create(body:MarketingCreate,authorization:str|None=Header(None)):
    admin=admin_only(authorization)
    brand=limited(body.brand,60); topic=limited(body.topic,220); cta=limited(body.cta,80)
    channel=body.channel if body.channel in ('Facebook','Instagram','TikTok','YouTube Shorts') else 'Facebook'
    headline=topic[:90]
    caption=f"🚀 {brand.upper()}\n\n{topic}\n\n✨ Discover what is possible with {brand}.\n📲 {cta}: https://wow-super-app.onrender.com\n\n#WOWSuperApp #ExploreMore #Philippines"
    if body.use_ai:
        if body.language not in ('English','Tagalog','Bisaya'):raise HTTPException(400,'Unsupported language')
        caption=provider_text(f'Brand: {brand}\nPromotion: {topic}\nPlatform: {channel}\nCall to action: {cta}',body.language,'marketing caption')
    now=int(time.time())
    with conn() as c:
        recent=c.execute('SELECT COUNT(*) FROM marketing_drafts WHERE owner_id=? AND created_at>?',(admin['id'],now-3600)).fetchone()[0]
        if recent>=20:raise HTTPException(429,'Hourly draft limit reached')
        cur=c.execute('INSERT INTO marketing_drafts(owner_id,brand,topic,channel,caption,headline,cta,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',(admin['id'],brand,topic,channel,caption,headline,cta,now,now))
        return {'id':cur.lastrowid,'caption':caption,'status':'pending','note':('AI-generated' if body.use_ai else 'Template-generated')+' draft. Review before publishing.'}

@app.get('/api/admin/marketing/drafts')
def marketing_list(authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:rows=c.execute('SELECT * FROM marketing_drafts ORDER BY created_at DESC,id DESC LIMIT 100').fetchall()
    return {'drafts':[dict(r) for r in rows]}

@app.put('/api/admin/marketing/drafts/{draft_id}/status')
def marketing_status(draft_id:int,body:MarketingStatus,authorization:str|None=Header(None)):
    marketing_get(draft_id,authorization)
    if body.status not in ('pending','approved','rejected'):raise HTTPException(400,'Invalid status')
    with conn() as c:c.execute('UPDATE marketing_drafts SET status=?,updated_at=? WHERE id=?',(body.status,int(time.time()),draft_id))
    return {'ok':True,'status':body.status,'published':False}

def marketing_font(size,bold=False):
    loc='/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf'
    try:return ImageFont.truetype(loc,size)
    except:return ImageFont.load_default()

def marketing_image(d,frame=0):
    im=Image.new('RGB',(720,1280),(6,17,35));dr=ImageDraw.Draw(im)
    dr.rounded_rectangle((32,34,688,1246),radius=42,outline=(34,149,248),width=5)
    dr.rounded_rectangle((58,78,662,180),radius=25,fill=(12,42,83))
    dr.text((85,108),'WOW SUPER APP',font=marketing_font(43,True),fill=(93,196,255))
    title=['DISCOVER','EXPLORE','JOIN TODAY','ONE APP. MORE.'][frame%4] if frame else d['brand'].upper()
    dr.text((66,280),title[:22],font=marketing_font(54,True),fill='white')
    from textwrap import wrap
    y=410
    for line in wrap(d['topic'],width=24)[:7]:
        dr.text((70,y),line,font=marketing_font(34,True),fill=(214,235,255));y+=58
    dr.rounded_rectangle((68,925,650,1035),radius=30,fill=(22,135,244))
    dr.text((93,958),d['cta'][:25],font=marketing_font(36,True),fill='white')
    dr.text((70,1130),'wow-super-app.onrender.com',font=marketing_font(24),fill=(132,187,234))
    return im

@app.get('/api/admin/marketing/drafts/{draft_id}/visual.png')
def marketing_visual(draft_id:int,authorization:str|None=Header(None)):
    d=marketing_get(draft_id,authorization)
    b=BytesIO();marketing_image(d).save(b,format='PNG');b.seek(0)
    return StreamingResponse(b,media_type='image/png',headers={'Content-Disposition':f'attachment; filename="wow-ad-{draft_id}.png"'})

@app.get('/api/admin/marketing/drafts/{draft_id}/video.mp4')
def marketing_video(draft_id:int,authorization:str|None=Header(None)):
    d=marketing_get(draft_id,authorization)
    # 12s silent vertical motion-card draft, not a recording of actual UI.
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(4):marketing_image(d,i+1).save(os.path.join(tmp,f'{i}.png'))
        playlist=os.path.join(tmp,'frames.txt')
        with open(playlist,'w') as f:
            for i in range(4):f.write(f"file '{i}.png'\nduration 3\n")
            f.write("file '3.png'\n")
        output=os.path.join(tmp,'ad.mp4')
        try:
            subprocess.run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',playlist,'-vf','fps=24,format=yuv420p','-c:v','libx264','-preset','veryfast','-movflags','+faststart',output],check=True,timeout=35,cwd=tmp)
        except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):raise HTTPException(503,'Video renderer unavailable on this server')
        data=pathlib.Path(output).read_bytes()
    return StreamingResponse(BytesIO(data),media_type='video/mp4',headers={'Content-Disposition':f'attachment; filename="wow-ad-{draft_id}.mp4"'})

# One admin entry point for platform overview, AI and hiring moderation.
@app.get('/super-admin')
@app.get('/admin/super')
def unified_admin_alias():
    return FileResponse(os.path.join(BASE,'static','platform-admin.html'))

@app.get('/admin/rewards')
def rewards_admin_page():
    return FileResponse(os.path.join(BASE,'static','rewards-admin.html'))

@app.get('/api/admin/jobs')
def admin_jobs(page:int=1,q:str='',authorization:str|None=Header(None)):
    admin_only(authorization)
    page=max(1,min(page,1000));term='%'+q.strip()[:80]+'%'
    with conn() as c:
        total=c.execute('SELECT COUNT(*) FROM jobs WHERE title LIKE ? OR location LIKE ?',(term,term)).fetchone()[0]
        rows=c.execute('''SELECT j.*,u.name AS posted_by,
            (SELECT COUNT(*) FROM job_applications a WHERE a.job_id=j.id) AS applications,
            (SELECT COUNT(*) FROM job_reports r WHERE r.job_id=j.id) AS reports
            FROM jobs j JOIN users u ON u.id=j.user_id
            WHERE j.title LIKE ? OR j.location LIKE ?
            ORDER BY j.created_at DESC,j.id DESC LIMIT 30 OFFSET ?''',(term,term,(page-1)*30)).fetchall()
    return {'jobs':[dict(r) for r in rows],'page':page,'total':total}

@app.post('/api/admin/jobs/{job_id}/close')
def admin_close_job(job_id:int,authorization:str|None=Header(None)):
    admin_only(authorization)
    with conn() as c:
        cur=c.execute('UPDATE jobs SET active=0 WHERE id=?',(job_id,))
        if not cur.rowcount:raise HTTPException(404,'Job not found')
    return {'ok':True,'active':False}
