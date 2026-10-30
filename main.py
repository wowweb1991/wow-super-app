import os
import requests
from flask import Flask, request, redirect, session, render_template_string, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'development-only-change-me')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=True, SESSION_COOKIE_SAMESITE='Lax')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_PUBLISHABLE_KEY', '')

STYLE = '''<meta name="viewport" content="width=device-width,initial-scale=1"><style>body{font-family:system-ui;background:#090d19;color:white;margin:0}main{max-width:440px;margin:9vh auto;padding:26px;background:#151b2c;border:1px solid #344262;border-radius:20px}h1{color:#7caaff}input,button{box-sizing:border-box;width:100%;padding:14px;margin:8px 0;border-radius:10px;border:0;font-size:16px}button{background:#2868ee;color:white;font-weight:bold}input{background:#f3f6ff}a{color:#91b5ff}.error{color:#ff9b9b}.success{color:#9cf2c7}small{color:#bdc6dc}</style>'''

def page(body, **context):
    return render_template_string(STYLE + '<main><h1>WOW SUPER APP</h1>' + body + '</main>', **context)

def auth_call(endpoint, payload):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {}, 'Supabase configuration is missing in Render Environment.'
    try:
        r = requests.post(SUPABASE_URL + '/auth/v1/' + endpoint,
            headers={'apikey': SUPABASE_KEY, 'Content-Type': 'application/json'},
            json=payload, timeout=15)
        data = r.json()
        if not r.ok:
            return {}, data.get('msg') or data.get('error_description') or data.get('message') or 'Authentication failed.'
        return data, None
    except (requests.RequestException, ValueError):
        return {}, 'Could not contact authentication server. Try again.'

@app.get('/')
def home():
    if session.get('email'):
        return redirect(url_for('dashboard'))
    return page('<p>Marketplace · Community · Services · AI</p><p>Welcome! Create your account to get started.</p><a href="/signup">Create Account</a> · <a href="/login">Login</a>')

@app.route('/signup', methods=['GET','POST'])
def signup():
    message = ''
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        password = request.form.get('password','')
        if len(password) < 8:
            message = 'Password must contain at least 8 characters.'
        else:
            data, error = auth_call('signup', {'email': email, 'password': password})
            if error:
                message = error
            else:
                return page('<p class="success">Registration submitted. Check your email and click the confirmation link, then log in.</p><a href="/login">Go to Login</a>')
    return page('''<h2>Create Account</h2><p class="error">{{message}}</p><form method="post"><input type="email" name="email" placeholder="Email address" required><input type="password" name="password" placeholder="Password (8+ characters)" minlength="8" required><button>Create Account</button></form><a href="/login">Already registered? Login</a>''', message=message)

@app.route('/login', methods=['GET','POST'])
def login():
    message = ''
    if request.method == 'POST':
        data, error = auth_call('token?grant_type=password', {'email': request.form.get('email','').strip(), 'password': request.form.get('password','')})
        if error:
            message = error
        elif data.get('access_token'):
            session.clear()
            session['access_token'] = data['access_token']
            session['email'] = data.get('user',{}).get('email','')
            return redirect(url_for('dashboard'))
        else:
            message = 'Login unsuccessful.'
    return page('''<h2>Login</h2><p class="error">{{message}}</p><form method="post"><input type="email" name="email" placeholder="Email address" required><input type="password" name="password" placeholder="Password" required><button>Login</button></form><a href="/signup">Create Account</a>''', message=message)

@app.get('/dashboard')
def dashboard():
    token = session.get('access_token')
    if not token:
        return redirect(url_for('login'))
    try:
        r = requests.get(SUPABASE_URL + '/auth/v1/user', headers={'apikey': SUPABASE_KEY, 'Authorization': 'Bearer ' + token}, timeout=15)
        if r.status_code == 401:
            session.clear()
            return redirect(url_for('login'))
        r.raise_for_status()
        email = r.json().get('email','Member')
    except (requests.RequestException, ValueError):
        return page('<p>Could not verify your session. Please try again.</p><a href="/logout">Logout</a>'), 503
    return page('''<h2>Member Dashboard</h2><p>Welcome, {{email}}!</p><p>🛍 Marketplace · 💬 Community · 🛠 Services · ✨ AI Studio</p><small>More features coming soon. Payments and AI generation are not active yet.</small><p><a href="/logout">Logout</a></p>''', email=email)

@app.get('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

