import os, sqlite3, secrets, hashlib, hmac, time, base64, re
from contextlib import contextmanager
from fastapi import FastAPI, Request, HTTPException, Header
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

# AI Studio: honest template-based demonstration, not an external AI model.
# Credits cannot be purchased or minted by the client. Payment fulfillment requires verified server-side webhooks.
AI_TOOLS={'caption':0,'description':2,'poster':5,'logo':10,'video':30,'website':50}
class AIInput(BaseModel):
    tool:str
    prompt:str=Field(min_length=3,max_length=800)
@app.get('/api/ai/tools')
def ai_tools():return {'tools':[{'id':k,'credits':v,'mode':'template-demo' if k in ('caption','description') else 'coming-soon'} for k,v in AI_TOOLS.items()],'payments_live':False}
@app.get('/api/ai/wallet')
def ai_wallet(authorization:str|None=Header(None)):
    u=user(authorization)
    with conn() as c:
        r=c.execute('SELECT credits FROM ai_wallets WHERE user_id=?',(u['id'],)).fetchone()
    return {'credits':r['credits'] if r else 0,'currency':'demo credits','payments_live':False}
@app.post('/api/ai/generate')
def ai_generate(data:AIInput,authorization:str|None=Header(None)):
    u=user(authorization)
    if data.tool not in AI_TOOLS:raise HTTPException(400,'Unknown tool')
    if data.tool not in ('caption','description'):raise HTTPException(501,'This generator requires an AI provider integration and is not live yet. No credits charged.')
    prompt=limited(data.prompt,800)
    cost=AI_TOOLS[data.tool]
    if data.tool=='caption': result=f'✨ Discover {prompt}!\n\nMade for people who value quality and creativity. Message us to learn more!\n\n#WOWSuperApp #DiscoverMore #SupportLocal'
    else:result=f'{prompt}\n\nExplore the details, connect with the creator, and send an inquiry to learn more.'
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        if cost:
            cur=c.execute('UPDATE ai_wallets SET credits=credits-? WHERE user_id=? AND credits>=?',(cost,u['id'],cost))
            if cur.rowcount!=1:raise HTTPException(402,'Insufficient demo credits')
            c.execute('INSERT INTO credit_events(user_id,delta,reason,created_at) VALUES (?,?,?,?)',(u['id'],-cost,'demo generation: '+data.tool,int(time.time())))
        c.execute('INSERT INTO ai_generations(user_id,tool,prompt,result,cost,created_at) VALUES (?,?,?,?,?,?)',(u['id'],data.tool,prompt,result,cost,int(time.time())))
    return {'result':result,'credits_charged':cost,'mode':'template-demo'}
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
    return {'image_data_url':row['qr_data']}

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
