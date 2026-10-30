import os
import secrets
import hmac
from functools import wraps
from flask import Flask, request, session, redirect, url_for, render_template_string, flash
from supabase import create_client

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', '')
if not app.secret_key:
    raise RuntimeError('Set FLASK_SECRET_KEY in Render Environment')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=os.environ.get('LOCAL_DEV') != '1', SESSION_COOKIE_SAMESITE='Lax')
URL = os.environ.get('SUPABASE_URL', '')
KEY = os.environ.get('SUPABASE_PUBLISHABLE_KEY', '') or os.environ.get('SUPABASE_ANON_KEY', '')
if not URL or not KEY:
    raise RuntimeError('Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in Render Environment')

def client():
    return create_client(URL, KEY)

def user_client():
    db = client()
    if session.get('access_token') and session.get('refresh_token'):
        try:
            auth = db.auth.set_session(session['access_token'], session['refresh_token'])
            if auth.session:
                session['access_token'] = auth.session.access_token
                session['refresh_token'] = auth.session.refresh_token
        except Exception:
            session.clear()
    return db

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('access_token'):
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapped

# WOW SUPER APP DESIGN PROMPT (kept in this single Python file):
# Modern mobile-first social marketplace. Crisp black-and-white identity,
# white crescent and five-point star, bold simple WOW wordmark, clean sans-serif.
# Keep marketplace photos, social media logos, content previews and accent icons
# FULL COLOR. No people in the brand cover, no gold, no author byline.
# Rounded cards, generous spacing, high contrast, accessible focus states.
STYLE='''<style>
:root{color-scheme:dark;--bg:#08090d;--panel:#15171c;--line:#343840;--fg:#fff;--muted:#b5bbc5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,Arial,sans-serif}
a{color:#fff;text-decoration-thickness:1px;text-underline-offset:4px}a:hover{color:#dceaff}
header{position:sticky;top:0;z-index:5;background:#0d0e11ee;backdrop-filter:blur(12px);border-bottom:1px solid #292b30;padding:12px max(18px,calc((100vw - 1100px)/2));display:flex;align-items:center;gap:20px;justify-content:space-between;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:9px;text-decoration:none;font-size:17px;font-weight:900;letter-spacing:.02em}.brand svg{width:32px;height:32px}
nav{display:flex;flex-wrap:wrap;gap:12px}nav a{font-size:13px;color:#d9dce3;text-decoration:none}nav a:hover{color:#fff}
main{max-width:1080px;margin:30px auto;padding:0 18px 50px}.card{background:var(--panel);border:1px solid var(--line);border-radius:19px;padding:22px;margin:16px 0;overflow-wrap:anywhere}
h1{font-size:clamp(28px,5vw,48px);line-height:1.12;letter-spacing:-.045em;margin:0 0 16px}h2{line-height:1.25;letter-spacing:-.02em}p{overflow-wrap:anywhere}
input,textarea,select{box-sizing:border-box;width:100%;padding:13px;margin:7px 0 14px;border:1px solid #6a6d75;border-radius:10px;background:#fff;color:#111}input:focus,textarea:focus,select:focus{outline:3px solid #6faeff}
button,.cta{display:inline-block;background:#fff;color:#08090d;border:0;border-radius:11px;padding:12px 20px;cursor:pointer;font-weight:750;text-decoration:none}button:hover,.cta:hover{background:#dce7ff;color:#08090d}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}.muted,small{color:var(--muted)}.alert{color:#ffb1b1}img{max-width:100%;border-radius:12px}
.hero{position:relative;isolation:isolate;overflow:hidden;background:radial-gradient(ellipse at 85% 0%,#202a3b 0%,transparent 46%),linear-gradient(135deg,#12141a,#050608);border:1px solid #35383e;border-radius:24px;padding:clamp(25px,5vw,54px);min-height:260px}
.hero:after{content:"";position:absolute;right:-5%;bottom:-65px;width:70%;height:140px;border-top:1px solid #ffffff33;border-radius:50%;transform:rotate(-8deg);z-index:-1}
.hero-title{font-size:clamp(40px,8vw,84px);font-weight:950;line-height:1;letter-spacing:-.08em}.hero .tag{font-size:12px;letter-spacing:.25em;font-weight:700;color:#c6cbd4}
.symbol{display:block;width:92px;height:92px;margin-bottom:14px}.feature-icon{font-size:32px;display:block;margin-bottom:10px}
.social-row{display:flex;flex-wrap:wrap;gap:10px;margin:15px 0}.social{display:inline-flex;gap:9px;align-items:center;text-decoration:none;padding:10px 14px;border-radius:10px;background:#24262d;border:1px solid #444650;font-weight:700}.fb{background:#1465db}.tt{background:#151515}.messenger{background:#176bfc}
@media(max-width:600px){header{position:static}nav{gap:10px}main{margin-top:15px}.card{padding:17px}}
.hero{background:radial-gradient(circle at 82% 10%,#55431e 0%,transparent 38%),linear-gradient(130deg,#171717,#060607)!important;border-color:#8e7440!important}.hero:before{content:'☪';position:absolute;right:7%;top:4%;font-size:clamp(80px,17vw,170px);color:#caa65d33;pointer-events:none}.card{transition:transform .2s,border-color .2s}.card:hover{border-color:#a98a52;transform:translateY(-2px)}.gold{color:#e1bd72}.goldline{border-top:1px solid #a98a52;padding-top:16px}.news-card a{color:#e1bd72}.pill{display:inline-block;background:#332c1e;border:1px solid #9b7e47;border-radius:40px;padding:5px 11px;color:#f3d69b;font-size:12px}.quran-ar{font-size:clamp(27px,5vw,44px);line-height:2.1;direction:rtl;text-align:center}.wallpaper{width:min(100%,330px);aspect-ratio:9/19.5;background:radial-gradient(circle at 50% 0%,#41361f,#090909 45%);border:2px solid #b38e49;border-radius:28px;padding:30px;display:flex;flex-direction:column;justify-content:space-between;text-align:center;margin:18px auto}.wallpaper .quran-ar{font-size:30px} </style>'''
LOGO='''<svg viewBox="0 0 100 100" role="img" aria-label="WOW crescent and star" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="48" fill="#08090d"/><path d="M63 13A38 38 0 1 0 82 78 36 36 0 1 1 63 13Z" fill="white"/><path d="m68 25 5 12 13 1-10 8 3 13-11-7-11 7 3-13-10-8 13-1Z" fill="white"/></svg>'''
BASE='''<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="google-site-verification" content="Ow2ifCK2UXxOyoOerqZGiKv5zZvbe8QQn2gpuibgc0s" /><meta name="theme-color" content="#08090d"><meta name="description" content="WOW SUPER APP: Marketplace, community, jobs, Qur’an, world news, and web services."><title>WOW SUPER APP</title>'''+STYLE+'''</head><body><header><a class="brand" href="/">'''+LOGO+'''<span>WOW SUPER APP</span></a><nav><a href="/">Home</a><a href="/marketplace">Marketplace</a><a href="/community">Community</a><a href="/services">Services</a><a href="/ai">AI Studio</a><a href="/social">Social</a><a href="/bonus">₱50 Bonus</a><a href="/invite">Invite & Earn</a><a href="/quran">Daily Qur’an</a><a href="/news">World News</a><a href="/jobs">Jobs</a><a href="/bonus/admin">Bonus Admin</a><a href="/admin">Admin</a><a href="/logout">Logout</a></nav></header><main>{% with messages=get_flashed_messages() %}{% for m in messages %}<p class="alert">{{m}}</p>{% endfor %}{% endwith %}{{content|safe}}</main></body></html>'''

def page(content, **data):
    from flask import render_template_string
    inner=render_template_string(content, **data)
    return render_template_string(BASE, content=inner)

def get_user(db):
    try:
        return db.auth.get_user().user
    except Exception:
        session.clear()
        return None

def query_rows(table, order='created_at'):
    try:
        return user_client().table(table).select('*').order(order, desc=True).limit(100).execute().data or []
    except Exception:
        flash('Could not load data. Run schema.sql in Supabase SQL Editor.')
        return []

@app.route('/')
def home():
    return page('''<section class="hero"><div class="symbol">'''+LOGO+'''</div><div class="hero-title">WOW</div><div class="tag">SUPER APP</div><h2>Shop. Connect. Create.</h2><p class="muted">Marketplace · Community · Services · AI Studio · Social Connect</p><a class="cta" href="/marketplace">Explore Marketplace</a></section><div class="grid">{% for icon,title,path,desc in items %}<div class="card"><span class="feature-icon">{{icon}}</span><h2>{{title}}</h2><p class="muted">{{desc}}</p><a href="{{path}}">Explore →</a></div>{% endfor %}</div><p>{% if email %}Signed in: {{email}}{% else %}<a href="/login">Log in</a> or <a href="/signup">Create account</a>{% endif %}</p>''',email=session.get('email'),items=[('🛍️','Marketplace','/marketplace','Discover products and contact sellers.'),('💬','Community','/community','Share updates, comments and likes.'),('🛠️','Services','/services','Find services and send inquiries.'),('✨','AI Studio','/ai','Create reusable content prompts.'),('💸','₱50 Bonus','/bonus','Apply for a welcome reward after verification.'),('🤝','Invite & Earn','/invite','₱10 per approved qualified referral.'),('🌙','Daily Qur’an','/quran','Read and save a lock-screen verse.'),('🌍','World News','/news','Read current headlines from external news feeds.'),('💼','Jobs & Hiring','/jobs','Browse jobs or post vacancies.'),('🌐','Social Connect','/social','Share to Facebook, open TikTok and Messenger.')])

@app.route('/social')
def social():
    return page('''<h1>Social Connect</h1><p class="muted">Connect with your audience using official sharing links. Social account login and automatic posting require separate developer approval and configuration.</p><div class="grid"><div class="card"><h2>Facebook</h2><p>Share WOW SUPER APP on Facebook.</p><a class="social fb" href="https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fwow-super-app.onrender.com" target="_blank" rel="noopener noreferrer">f &nbsp; Share on Facebook</a></div><div class="card"><h2>TikTok</h2><p>Open TikTok to create and share a video. Automatic posting is not enabled.</p><a class="social tt" href="https://www.tiktok.com/" target="_blank" rel="noopener noreferrer">♪ &nbsp; Open TikTok</a></div><div class="card"><h2>Messenger</h2><p>Open Messenger to message people. A seller-specific link can be added to each listing.</p><a class="social messenger" href="https://www.messenger.com/" target="_blank" rel="noopener noreferrer">● &nbsp; Open Messenger</a></div></div>''')

@app.route('/signup',methods=['GET','POST'])
def signup():
    if request.method=='POST':
        try:
            client().auth.sign_up({'email':request.form['email'].strip(),'password':request.form['password']})
            flash('Account submitted. Check email for confirmation if enabled, then log in.')
            return redirect('/login')
        except Exception as e: flash('Signup failed. Check email, password and Supabase Auth settings.')
    return page('''<div class="card"><h1>Create Account</h1><form method="post"><input type="email" name="email" placeholder="Email" required><input type="password" name="password" minlength="8" placeholder="Password (8+ characters)" required><button>Create Account</button></form><a href="/login">Already registered?</a></div>''')

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        try:
            result=client().auth.sign_in_with_password({'email':request.form['email'].strip(),'password':request.form['password']})
            session.clear();session['access_token']=result.session.access_token;session['refresh_token']=result.session.refresh_token;session['email']=result.user.email;session['uid']=result.user.id
            return redirect('/')
        except Exception: flash('Login failed. Check credentials or confirm your email.')
    return page('''<div class="card"><h1>Login</h1><form method="post"><input type="email" name="email" placeholder="Email" required><input type="password" name="password" placeholder="Password" required><button>Login</button></form><a href="/signup">Create account</a></div>''')

@app.route('/logout')
def logout():
    session.clear();return redirect('/')

@app.route('/marketplace',methods=['GET','POST'])
@login_required
def marketplace():
    db=user_client();user=get_user(db)
    if not user:return redirect('/login')
    if request.method=='POST':
        try:
            db.table('products').insert({'user_id':user.id,'title':request.form['title'][:120],'description':request.form['description'][:2000],'price':float(request.form['price']),'image_url':request.form.get('image_url','')[:1000],'contact':request.form['contact'][:200]}).execute()
            flash('Product posted.');return redirect('/marketplace')
        except Exception:flash('Unable to post product. Check your fields and database policies.')
    return page('''<h1>🛍️ Marketplace</h1><div class="card"><h2>Sell a product</h2><form method="post"><input name="title" placeholder="Product name" required maxlength="120"><textarea name="description" placeholder="Description" required></textarea><input name="price" type="number" step="0.01" min="0" placeholder="Price (PHP)" required><input name="image_url" type="url" placeholder="Public image URL (optional)"><input name="contact" placeholder="Contact link or details" required><button>Publish</button></form></div><div class="grid">{% for p in rows %}<div class="card">{% if p.image_url %}<img src="{{p.image_url}}" alt="Product image">{% endif %}<h2>{{p.title}}</h2><p>{{p.description}}</p><strong>₱{{p.price}}</strong><p>Contact: {{p.contact}}</p></div>{% else %}<p>No products yet.</p>{% endfor %}</div>''',rows=query_rows('products'))

@app.route('/community',methods=['GET','POST'])
@login_required
def community():
    db=user_client();user=get_user(db)
    if not user:return redirect('/login')
    if request.method=='POST':
        try:
            db.table('posts').insert({'user_id':user.id,'body':request.form['body'][:2000]}).execute();return redirect('/community')
        except Exception:flash('Could not publish post.')
    return page('''<h1>💬 Community</h1><div class="card"><form method="post"><textarea name="body" maxlength="2000" placeholder="Share an update" required></textarea><button>Post</button></form></div>{% for p in rows %}<div class="card"><p>{{p.body}}</p><small>{{p.created_at}}</small><p><a href="/community/{{p.id}}">Comments & likes</a></p></div>{% else %}<p>No posts yet.</p>{% endfor %}''',rows=query_rows('posts'))

@app.route('/community/<post_id>',methods=['GET','POST'])
@login_required
def post_detail(post_id):
    db=user_client();user=get_user(db)
    if not user:return redirect('/login')
    if request.method=='POST':
        try:
            if request.form.get('action')=='like':db.table('likes').upsert({'user_id':user.id,'post_id':post_id},on_conflict='user_id,post_id').execute()
            else:db.table('comments').insert({'user_id':user.id,'post_id':post_id,'body':request.form['body'][:1000]}).execute()
            return redirect('/community/'+post_id)
        except Exception:flash('Action could not be saved.')
    try:
        post=db.table('posts').select('*').eq('id',post_id).single().execute().data
        comments=db.table('comments').select('*').eq('post_id',post_id).order('created_at').execute().data
        likes=db.table('likes').select('id').eq('post_id',post_id).execute().data
    except Exception:return redirect('/community')
    return page('''<div class="card"><h1>Community post</h1><p>{{post.body}}</p><form method="post"><button name="action" value="like">❤️ Like ({{likes|length}})</button></form></div><div class="card"><h2>Comments</h2>{% for c in comments %}<p>{{c.body}}</p>{% endfor %}<form method="post"><textarea name="body" required maxlength="1000"></textarea><button>Comment</button></form></div>''',post=post,comments=comments,likes=likes)

@app.route('/services',methods=['GET','POST'])
@login_required
def services():
    db=user_client();user=get_user(db)
    if not user:return redirect('/login')
    if request.method=='POST':
        try:
            if request.form.get('kind')=='inquiry':
                db.table('inquiries').insert({'user_id':user.id,'service_id':request.form['service_id'],'message':request.form['message'][:1000]}).execute();flash('Inquiry sent.')
            else:
                db.table('services').insert({'user_id':user.id,'title':request.form['title'][:120],'description':request.form['description'][:2000],'contact':request.form['contact'][:200]}).execute();flash('Service published.')
            return redirect('/services')
        except Exception:flash('Could not save service or inquiry.')
    return page('''<h1>🛠️ Services</h1><section class="hero"><span class="pill">Featured Studio</span><h2>WOW Web Studio</h2><p>Website design & development · Online stores · Digital menus & ordering · Business and travel websites · Landing pages & portfolios · Website redesign · Basic logo design</p><p>Free quotations available. Contact us to confirm the scope of each service.</p><a class="cta" href="https://wowweb1991.github.io/wow-studio/" target="_blank" rel="noopener">Visit WOW Web Studio</a> <a href="https://www.facebook.com/share/1Lq7Mgskiz/" target="_blank" rel="noopener">Request a Free Quote</a></section><div class="card"><h2>Offer a service</h2><form method="post"><input name="title" required placeholder="Service title"><textarea name="description" required placeholder="Description"></textarea><input name="contact" required placeholder="Contact"><button>Publish service</button></form></div>{% for s in rows %}<div class="card"><h2>{{s.title}}</h2><p>{{s.description}}</p><p>Contact: {{s.contact}}</p><form method="post"><input type="hidden" name="kind" value="inquiry"><input type="hidden" name="service_id" value="{{s.id}}"><textarea name="message" placeholder="Your inquiry" required></textarea><button>Send inquiry</button></form></div>{% else %}<p>No services yet.</p>{% endfor %}''',rows=query_rows('services'))

@app.route('/ai')
@login_required
def ai():
    return page('''<h1>✨ AI Studio</h1><div class="card"><p>AI generation is not enabled yet. This free prompt builder helps prepare a prompt you can paste into an AI tool.</p><form onsubmit="event.preventDefault();document.getElementById('out').textContent='Create a compelling '+document.getElementById('kind').value+' for '+document.getElementById('topic').value+'. Include a strong hook, clear benefits, friendly tone, and a call to action.'"><select id="kind"><option>social media caption</option><option>product description</option><option>service advertisement</option></select><input id="topic" required placeholder="Business or topic"><button>Generate prompt</button></form><p id="out"></p></div>''')

@app.route('/admin')
@login_required
def admin():
    db=user_client();user=get_user(db)
    if not user:return redirect('/login')
    admin_ids=[x.strip() for x in os.environ.get('ADMIN_USER_IDS','').split(',') if x.strip()]
    if user.id not in admin_ids:return page('<h1>Admin</h1><p>Access restricted to configured administrator user IDs.</p>'),403
    counts={}
    for table in ['products','posts','services','inquiries']:
        try:counts[table]=len(db.table(table).select('id').limit(1000).execute().data)
        except Exception:counts[table]='Unavailable'
    return page('''<h1>Admin Dashboard</h1><p class="muted">Counts show up to 1,000 rows each and are limited by database policies. For full moderation, use Supabase dashboard.</p><div class="grid">{% for k,v in counts.items() %}<div class="card"><h2>{{k}}</h2><p>{{v}}</p></div>{% endfor %}</div>''',counts=counts)


# CASH BONUS: This records eligibility requests and manual GCash payouts.
# No automatic transfers, no stored wallet balance, no guarantee of payout.
def bonus_csrf():
    if 'bonus_csrf' not in session:
        session['bonus_csrf'] = secrets.token_urlsafe(32)
    return session['bonus_csrf']

def check_bonus_csrf():
    return hmac.compare_digest(session.get('bonus_csrf',''), request.form.get('csrf','')) and bool(session.get('bonus_csrf'))

@app.route('/bonus', methods=['GET','POST'])
@login_required
def bonus():
    db=user_client(); user=get_user(db)
    if not user:return redirect('/login')
    if request.method=='POST':
        if not check_bonus_csrf():return page('<h1>Invalid form token</h1>'),400
        try:
            action=request.form.get('action')
            if action=='claim':
                result=db.rpc('wow_bonus_claim',{}).execute()
            elif action=='request':
                result=db.rpc('wow_bonus_request_payout',{
                    'p_number':request.form.get('gcash_number','').strip(),
                    'p_name':request.form.get('gcash_name','').strip()
                }).execute()
            else:return page('<h1>Invalid action</h1>'),400
            flash(str(result.data or 'Request recorded'))
        except Exception:
            flash('Request could not be processed. Check eligibility, campaign status, and submitted details.')
        return redirect('/bonus')
    try:
        rows=db.table('wow_bonus_claims').select('id,amount_pesos,status,created_at,requested_at,paid_at').eq('user_id',user.id).limit(1).execute().data or []
    except Exception:
        rows=[];flash('Bonus database not ready. Run WOW_BONUS_SETUP.sql first.')
    return page("""<section class="hero"><h1>₱50 Welcome Bonus</h1>
    <p>Real-money promotional offer for eligible new accounts. Subject to verification, availability, approval and campaign terms.</p>
    <p><strong>Not a wallet balance. No cash has been paid unless status says Paid.</strong></p></section>
    {% if claim %}<div class="card"><h2>Application status: {{claim.status|upper}}</h2>
    <p>Proposed reward: ₱{{claim.amount_pesos}}</p>
    {% if claim.status == 'pending' %}
    <h3>Request manual GCash payout</h3>
    <form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="request">
    <input name="gcash_name" maxlength="100" placeholder="GCash account holder name" required>
    <input name="gcash_number" pattern="09[0-9]{9}" maxlength="11" placeholder="GCash number: 09XXXXXXXXX" required>
    <button>Submit for review</button></form>{% endif %}
    {% if claim.status == 'requested' %}<p>Awaiting admin eligibility review.</p>{% endif %}
    {% if claim.status == 'approved' %}<p>Approved for manual payout; transfer has NOT been confirmed.</p>{% endif %}
    {% if claim.status == 'paid' %}<p>Payment recorded as completed by administrator.</p>{% endif %}
    {% if claim.status == 'rejected' %}<p>Application not approved.</p>{% endif %}
    </div>{% else %}<div class="card"><p>Only verified new accounts created after the campaign launches can apply. One claim per account; duplicate or fraudulent applications may be rejected.</p>
    <form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="claim"><button>Apply for ₱50 reward</button></form></div>{% endif %}
    <p class="muted">Do not share your GCash PIN or OTP. Only your GCash name and number are needed for a payout request.</p>""",claim=rows[0] if rows else None,csrf=bonus_csrf())

@app.route('/bonus/admin',methods=['GET','POST'])
@login_required
def bonus_admin():
    db=user_client();user=get_user(db)
    if not user:return redirect('/login')
    try:
        admins=db.table('wow_bonus_claims').select('id').limit(1).execute()
        # RLS alone does not reveal whether current user is an admin; use a restricted RPC.
        is_admin=db.rpc('wow_bonus_is_admin',{}).execute().data
    except Exception:
        return page('<h1>Bonus admin unavailable</h1><p>Run the SQL setup and add your admin UUID.</p>'),503
    if not is_admin:return page('<h1>Access denied</h1>'),403
    if request.method=='POST':
        if not check_bonus_csrf():return page('<h1>Invalid form token</h1>'),400
        try:
            db.rpc('wow_bonus_admin_action',{
                'p_claim':request.form.get('claim_id',''),
                'p_action':request.form.get('action',''),
                'p_note':request.form.get('note','')[:500],
                'p_reference':request.form.get('reference','')[:100]
            }).execute()
            flash('Status updated. Mark Paid ONLY after completing the GCash transfer yourself.')
        except Exception:flash('Admin action failed. Check claim status and transaction reference.')
        return redirect('/bonus/admin')
    try:
        rows=db.table('wow_bonus_claims').select('*').order('created_at',desc=True).limit(100).execute().data or []
    except Exception:rows=[]
    return page("""<h1>Bonus Admin — Manual GCash</h1>
    <p>Verify unique real persons and campaign eligibility before approval. Never mark Paid until GCash confirms the transfer.</p>
    {% for c in rows %}<div class="card"><h3>Claim {{c.id}}</h3><p>Status: {{c.status}} · ₱{{c.amount_pesos}}</p>
    <p>User ID: {{c.user_id}}</p><p>GCash: {{c.gcash_name or 'Not submitted'}} · {{c.gcash_number or 'Not submitted'}}</p>
    <form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="claim_id" value="{{c.id}}">
    <input name="note" placeholder="Review note (optional)"><input name="reference" placeholder="GCash transaction reference (required for Paid)">
    {% if c.status == 'requested' %}<button name="action" value="approve">Approve</button>{% endif %}
    {% if c.status in ['pending','requested'] %}<button name="action" value="reject">Reject</button>{% endif %}
    {% if c.status == 'approved' %}<button name="action" value="paid">Mark Paid after transfer</button>{% endif %}
    </form></div>{% else %}<p>No claims.</p>{% endfor %}""",rows=rows,csrf=bonus_csrf())

# ADDITIONAL WOW FEATURES
import datetime
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
import requests as http_requests
from flask import Response

# Selected, source-checked verses. No fabricated Qur'an text.
VERSES = [
    ('94:5', 'Ash-Sharh', 'فَإِنَّ مَعَ الْعُسْرِ يُسْرًا', 'So, surely with hardship comes ease.'),
    ('94:6', 'Ash-Sharh', 'إِنَّ مَعَ الْعُسْرِ يُسْرًا', 'Surely with hardship comes ease.'),
    ('20:114', 'Ta-Ha', 'وَقُل رَّبِّ زِدْنِي عِلْمًا', 'And say, “My Lord, increase me in knowledge.”'),
    ('2:152', 'Al-Baqarah', 'فَاذْكُرُونِي أَذْكُرْكُمْ', 'So remember Me; I will remember you.'),
]

def today_verse():
    return VERSES[datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().toordinal() % len(VERSES)]

@app.get('/quran')
def quran():
    verse = today_verse()
    return page('''<section class="hero"><span class="pill">Daily Qur’an</span><h1>🌙 A verse for today</h1><p>Read, reflect, and save your lock-screen design.</p></section>
    <div class="wallpaper" id="wallpaper"><div class="gold">☪ &nbsp; DAILY QUR’AN</div><div><div class="quran-ar">{{v[2]}}</div><p>{{v[3]}}</p><p class="gold">Surah {{v[1]}} · {{v[0]}}</p></div><small>WOW SUPER APP</small></div>
    <div class="card"><h2>Save Lock Screen</h2><p>Download a 1080 × 2340 SVG wallpaper. Set it as your lock screen manually in phone settings.</p><a class="cta" href="/quran/wallpaper">Download wallpaper</a><p class="muted">Translation is a short English rendering. Check the verse in a trusted mushaf or Qur’an reference.</p></div>''',v=verse)

@app.get('/quran/wallpaper')
def quran_wallpaper():
    # SVG keeps Arabic text selectable/renderable without requiring image packages.
    import html
    v=today_verse()
    arabic=html.escape(v[2]); translation=html.escape(v[3]); reference=html.escape(v[1]+' · '+v[0])
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="2340" viewBox="0 0 1080 2340"><defs><linearGradient id="g" x2="0" y2="1"><stop stop-color="#252015"/><stop offset="0.5" stop-color="#080808"/><stop offset="1" stop-color="#111"/></linearGradient></defs><rect width="1080" height="2340" fill="url(#g)"/><rect x="45" y="45" width="990" height="2250" rx="80" fill="none" stroke="#b69553" stroke-width="4"/><text x="540" y="300" fill="#e0bb70" font-size="95" text-anchor="middle">☪</text><text x="540" y="430" fill="#e0bb70" font-size="46" letter-spacing="6" text-anchor="middle">DAILY QUR’AN</text><text x="540" y="1060" fill="white" font-family="Noto Naskh Arabic,serif" font-size="78" text-anchor="middle" direction="rtl">{arabic}</text><text x="540" y="1250" fill="white" font-family="sans-serif" font-size="35" text-anchor="middle" textLength="850" lengthAdjust="spacingAndGlyphs">{translation}</text><text x="540" y="1390" fill="#e0bb70" font-size="39" text-anchor="middle">{reference}</text><text x="540" y="2120" fill="#bbb" font-size="34" text-anchor="middle">WOW SUPER APP</text></svg>'''
    return Response(svg,mimetype='image/svg+xml',headers={'Content-Disposition':'attachment; filename="wow-quran-lockscreen.svg"','Cache-Control':'no-store'})

@app.get('/news')
def news():
    feeds=[('World','https://feeds.bbci.co.uk/news/world/rss.xml'),('Business','https://feeds.bbci.co.uk/news/business/rss.xml'),('Technology','https://feeds.bbci.co.uk/news/technology/rss.xml')]
    category=request.args.get('category','World')
    feed=dict(feeds).get(category,feeds[0][1]); stories=[]; error=False
    try:
        r=http_requests.get(feed,timeout=7,headers={'User-Agent':'WOWSuperApp/1.0 (+https://wow-super-app.onrender.com)'})
        r.raise_for_status(); root=ET.fromstring(r.content)
        for item in root.findall('.//channel/item')[:15]:
            title=item.findtext('title','').strip(); link=item.findtext('link','').strip()
            if not link.startswith('https://'):continue
            stories.append({'title':title,'link':link,'date':item.findtext('pubDate',''),'source':'BBC News'})
    except Exception:error=True
    return page('''<section class="hero"><span class="pill">World News</span><h1>🌍 Daily World News</h1><p>Live external headlines. Article dates and original sources are shown below.</p></section>
    <div class="card">{% for c in categories %}<a style="margin-right:18px" href="/news?category={{c}}">{{c}}</a>{% endfor %}</div>
    {% if error %}<div class="card">News feed temporarily unavailable. Please try again later. No headlines are fabricated.</div>{% endif %}
    {% for s in stories %}<div class="card news-card"><small>{{s.source}} · {{s.date}}</small><h2>{{s.title}}</h2><a href="{{s.link}}" target="_blank" rel="noopener noreferrer">Read original article ↗</a></div>{% else %}<p>No current headlines available.</p>{% endfor %}''',stories=stories,error=error,categories=[x[0] for x in feeds])

@app.route('/jobs',methods=['GET','POST'])
def jobs():
    if request.method=='POST':
        if not session.get('access_token'):return redirect('/login')
        db=user_client(); user=get_user(db)
        if not user:return redirect('/login')
        if not check_bonus_csrf():return page('<h1>Invalid form token</h1>'),400
        try:
            db.table('wow_jobs').insert({'user_id':user.id,'title':request.form['title'][:120],'company':request.form['company'][:120], 'location':request.form['location'][:150], 'details':request.form['details'][:3000],'contact':request.form['contact'][:250]}).execute()
            flash('Job posted.');return redirect('/jobs')
        except Exception:flash('Unable to post job. Run the new Supabase SQL setup.')
    rows=query_rows('wow_jobs') if session.get('access_token') else []
    return page('''<section class="hero"><span class="pill">Jobs & Hiring</span><h1>💼 Find work. Hire talent.</h1><p>Job listings and direct employer contacts. Verify employers before sharing personal details.</p></section>
    {% if logged %}<div class="card"><h2>Post a job</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input name="title" placeholder="Job title" required maxlength="120"><input name="company" placeholder="Company" required maxlength="120"><input name="location" placeholder="Location / Remote" required><textarea name="details" placeholder="Responsibilities, salary if available, requirements" required></textarea><input name="contact" placeholder="Employer contact / application link" required><button>Post job</button></form></div>{% else %}<div class="card"><a href="/login">Log in to view and post jobs</a></div>{% endif %}
    <div class="grid">{% for j in rows %}<div class="card"><h2>{{j.title}}</h2><p class="gold">{{j.company}}</p><p>📍 {{j.location}}</p><p>{{j.details}}</p><p>Apply/contact: {{j.contact}}</p></div>{% endfor %}</div>''',rows=rows,logged=bool(session.get('access_token')),csrf=bonus_csrf())

@app.route('/invite',methods=['GET','POST'])
@login_required
def invite():
    db=user_client(); user=get_user(db)
    if not user:return redirect('/login')
    if request.method=='POST':
        if not check_bonus_csrf():return page('<h1>Invalid form token</h1>'),400
        try:
            result=db.rpc('wow_referral_register',{'p_code':request.form.get('code','').strip()}).execute()
            flash(str(result.data))
        except Exception:flash('Referral registration not accepted. Check eligibility or campaign status.')
        return redirect('/invite')
    code=str(user.id).replace('-','')[:12]
    try:
        rows=db.table('wow_referrals').select('id,status,created_at').eq('referrer_id',user.id).order('created_at',desc=True).limit(100).execute().data or []
    except Exception:rows=[]
    link=url_for('invite',_external=True)+'?ref='+code
    return page('''<section class="hero"><span class="pill">Invite & Earn</span><h1>🤝 ₱10 per qualified referral</h1><p>Cash rewards require verification, admin approval and manual GCash transfer. No payout is guaranteed merely by sharing a link.</p></section>
    <div class="card"><h2>Your invite link</h2><input readonly value="{{link}}" onclick="this.select()"><p>Referral code: <strong>{{code}}</strong></p><p>Share the link with friends. They must create and verify their own account, then enter your code.</p></div>
    <div class="card"><h2>Enter referral code</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input name="code" value="{{incoming}}" placeholder="Referral code" minlength="12" maxlength="12" required><button>Submit referral code</button></form></div>
    <div class="card"><h2>Referrals</h2>{% for r in rows %}<p>₱10 · {{r.status|upper}} · {{r.created_at}}</p>{% else %}<p>No recorded referrals yet.</p>{% endfor %}</div>''',link=link,code=code,incoming=request.args.get('ref','')[:12],rows=rows,csrf=bonus_csrf())

@app.route('/invite/admin',methods=['GET','POST'])
@login_required
def invite_admin():
    db=user_client();user=get_user(db)
    if not user:return redirect('/login')
    try:
        if not db.rpc('wow_bonus_is_admin',{}).execute().data:return page('<h1>Access denied</h1>'),403
    except Exception:return page('<h1>Database setup required</h1>'),503
    if request.method=='POST':
        if not check_bonus_csrf():return page('<h1>Invalid form token</h1>'),400
        try:
            db.rpc('wow_referral_admin_action',{'p_id':request.form.get('id',''),'p_action':request.form.get('action',''),'p_reference':request.form.get('reference','')[:100]}).execute()
            flash('Referral updated. Mark Paid only after GCash transfer is confirmed.')
        except Exception:flash('Could not update referral. Check eligibility, campaign cap and status.')
        return redirect('/invite/admin')
    try:rows=db.table('wow_referrals').select('*').order('created_at',desc=True).limit(100).execute().data or []
    except Exception:rows=[]
    return page('''<h1>Referral Admin</h1><p>Check genuine, distinct users before approval. Use the verified referrer's GCash details collected separately and securely.</p>{% for r in rows %}<div class="card"><p>ID: {{r.id}}</p><p>Referrer: {{r.referrer_id}}</p><p>Referred: {{r.referred_id}}</p><p>₱10 · {{r.status}}</p><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="id" value="{{r.id}}"><input name="reference" placeholder="Actual GCash reference (Paid only)">{% if r.status=='pending' %}<button name="action" value="approve">Approve</button><button name="action" value="reject">Reject</button>{% elif r.status=='approved' %}<button name="action" value="paid">Mark Paid after transfer</button>{% endif %}</form></div>{% else %}<p>No referrals.</p>{% endfor %}''',rows=rows,csrf=bonus_csrf())

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
