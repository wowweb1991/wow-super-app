import os
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

STYLE='''<style>body{margin:0;background:#090e1e;color:#edf2ff;font:16px system-ui}header{background:#141d36;padding:20px;display:flex;flex-wrap:wrap;gap:15px;align-items:center;justify-content:space-between}a{color:#93b4ff}nav a{margin-right:14px}main{max-width:980px;margin:35px auto;padding:0 18px}.card{background:#171f36;border:1px solid #34456c;border-radius:18px;padding:24px;margin:16px 0}h1{color:#85a9ff}input,textarea,select{box-sizing:border-box;width:100%;padding:13px;margin:7px 0 14px;border:0;border-radius:9px;background:#f3f5fc;color:#101526}button{background:#3865e7;color:white;border:0;border-radius:9px;padding:12px 20px;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}.muted{color:#b4bfd8}.alert{color:#ffb1b1}img{max-width:100%;border-radius:12px}small{color:#b4bfd8}</style>'''
BASE='''<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>WOW SUPER APP</title>'''+STYLE+'''</head><body><header><strong>✨ WOW SUPER APP</strong><nav><a href="/">Home</a><a href="/marketplace">Marketplace</a><a href="/community">Community</a><a href="/services">Services</a><a href="/ai">AI Studio</a><a href="/admin">Admin</a><a href="/logout">Logout</a></nav></header><main>{% with messages=get_flashed_messages() %}{% for m in messages %}<p class="alert">{{m}}</p>{% endfor %}{% endwith %}{{content|safe}}</main></body></html>'''
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
    return page('''<h1>Build, sell and connect.</h1><p>Marketplace · Community · Services · AI Studio</p><div class="grid">{% for title,path,desc in items %}<div class="card"><h2>{{title}}</h2><p>{{desc}}</p><a href="{{path}}">Explore</a></div>{% endfor %}</div><p>{% if email %}Signed in: {{email}}{% else %}<a href="/login">Log in</a> or <a href="/signup">Create account</a>{% endif %}</p>''',email=session.get('email'),items=[('🛍️ Marketplace','/marketplace','Discover products and contact sellers.'),('💬 Community','/community','Share updates and discuss.'),('🛠️ Services','/services','Find services and send inquiries.'),('✨ AI Studio','/ai','Content prompt helper.')])

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
    return page('''<h1>🛠️ Services</h1><div class="card"><h2>Offer a service</h2><form method="post"><input name="title" required placeholder="Service title"><textarea name="description" required placeholder="Description"></textarea><input name="contact" required placeholder="Contact"><button>Publish service</button></form></div>{% for s in rows %}<div class="card"><h2>{{s.title}}</h2><p>{{s.description}}</p><p>Contact: {{s.contact}}</p><form method="post"><input type="hidden" name="kind" value="inquiry"><input type="hidden" name="service_id" value="{{s.id}}"><textarea name="message" placeholder="Your inquiry" required></textarea><button>Send inquiry</button></form></div>{% else %}<p>No services yet.</p>{% endfor %}''',rows=query_rows('services'))

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

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
