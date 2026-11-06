"""Opt-in public profiles with bounded pictures, themes and featured products."""
import base64,io,json,re,time
from fastapi import Header,HTTPException,Request
from fastapi.responses import Response,FileResponse
from PIL import Image,ImageOps,UnidentifiedImageError
from pydantic import BaseModel,Field,ValidationError
from public_pages import page,esc,ORIGIN
THEMES={'blue':'#1765d1','green':'#167448','purple':'#7651bc','pink':'#b63779','red':'#ba3049','gold':'#956515'}
class ProfileData(BaseModel):
    handle:str=Field(min_length=3,max_length=40)
    display_name:str=Field(min_length=1,max_length=80)
    bio:str=Field(default='',max_length=700)
    location:str=Field(default='',max_length=100)
    theme:str='blue'
    pattern:str='solid'
    avatar:str=Field(default='',max_length=350000)
    cover:str=Field(default='',max_length=500000)
    featured:list[int]=Field(default_factory=list,max_length=3)
    is_public:bool=False

def clean_profile_image(data,kind):
    if not data:return ''
    try:
        if not data.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')):raise ValueError()
        raw=base64.b64decode(data.split(',',1)[1],validate=True)
        if len(raw)>300000:raise ValueError()
        with Image.open(io.BytesIO(raw)) as original:
            if original.width*original.height>16000000:raise ValueError()
            image=ImageOps.exif_transpose(original).convert('RGB');image.thumbnail((500,500) if kind=='avatar' else (1200,600));out=io.BytesIO();image.save(out,'WEBP',quality=78)
            if out.tell()>(90000 if kind=='avatar' else 190000):raise ValueError()
        return 'data:image/webp;base64,'+base64.b64encode(out.getvalue()).decode()
    except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError):raise HTTPException(400,'Profile photo is invalid or too large. Choose a smaller JPG, PNG or WebP image.')

def install_profiles(app,conn,user,base):
    with conn() as c:c.execute("CREATE TABLE IF NOT EXISTS user_profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id),handle TEXT NOT NULL UNIQUE,display_name TEXT NOT NULL,bio TEXT NOT NULL DEFAULT '',location TEXT NOT NULL DEFAULT '',theme TEXT NOT NULL DEFAULT 'blue',pattern TEXT NOT NULL DEFAULT 'solid',avatar TEXT NOT NULL DEFAULT '',cover TEXT NOT NULL DEFAULT '',featured TEXT NOT NULL DEFAULT '[]',is_public INTEGER NOT NULL DEFAULT 0,updated_at INTEGER NOT NULL)")
    @app.get('/profile/edit',include_in_schema=False)
    def edit_profile():return FileResponse(str(base)+'/static/profile-edit.html',headers={'Cache-Control':'no-store'})
    @app.get('/api/profile/me')
    def my_profile(authorization:str|None=Header(None)):
        viewer=user(authorization)
        with conn() as c:
            row=c.execute('SELECT * FROM user_profiles WHERE user_id=?',(viewer['id'],)).fetchone()
            listings=c.execute('SELECT id,title FROM listings WHERE user_id=? AND active=1 ORDER BY created_at DESC LIMIT 100',(viewer['id'],)).fetchall()
        data=dict(row) if row else {'handle':'member-'+str(viewer['id']),'display_name':viewer['name'],'bio':'','location':'','theme':'blue','pattern':'solid','avatar':'','cover':'','featured':'[]','is_public':0}
        data['featured']=json.loads(data['featured']);data['is_public']=bool(data['is_public'])
        return {'profile':data,'listings':[dict(r) for r in listings]}
    @app.put('/api/profile/me')
    async def update_profile(request:Request,authorization:str|None=Header(None)):
        viewer=user(authorization);raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>900000:raise HTTPException(413,'Profile photos are too large.')
        try:data=ProfileData.model_validate_json(bytes(raw))
        except ValidationError:raise HTTPException(422,'Check your profile fields and choose up to three featured products.')
        handle=data.handle.strip().lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,39}',handle) or handle in {'admin','support','wow','marketplace','community','login','register','profile','api','edit','official'}:raise HTTPException(400,'Choose a 3–40 character handle using letters, numbers and hyphens.')
        if not data.display_name.strip():raise HTTPException(400,'Enter your display name.')
        if data.theme not in THEMES or data.pattern not in ('solid','dots','gradient'):raise HTTPException(400,'Choose an available theme and background.')
        avatar=clean_profile_image(data.avatar,'avatar');cover=clean_profile_image(data.cover,'cover')
        featured=list(dict.fromkeys(data.featured))
        with conn() as c:
            for item_id in featured:
                if not c.execute('SELECT id FROM listings WHERE id=? AND user_id=? AND active=1',(item_id,viewer['id'])).fetchone():raise HTTPException(400,'Only your own active products can be featured.')
            taken=c.execute('SELECT user_id FROM user_profiles WHERE handle=?',(handle,)).fetchone()
            if taken and taken['user_id']!=viewer['id']:raise HTTPException(409,'That profile handle is already taken.')
            c.execute('INSERT INTO user_profiles(user_id,handle,display_name,bio,location,theme,pattern,avatar,cover,featured,is_public,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET handle=excluded.handle,display_name=excluded.display_name,bio=excluded.bio,location=excluded.location,theme=excluded.theme,pattern=excluded.pattern,avatar=excluded.avatar,cover=excluded.cover,featured=excluded.featured,is_public=excluded.is_public,updated_at=excluded.updated_at',(viewer['id'],handle,data.display_name.strip(),data.bio.strip(),data.location.strip(),data.theme,data.pattern,avatar,cover,json.dumps(featured),int(data.is_public),int(time.time())))
        return {'ok':True,'url':'/members/'+handle,'is_public':data.is_public}
    @app.get('/api/profile-media/{handle}/{kind}')
    def profile_media(handle:str,kind:str):
        if kind not in ('avatar','cover'):raise HTTPException(404)
        with conn() as c:r=c.execute('SELECT avatar,cover FROM user_profiles WHERE handle=? AND is_public=1',(handle,)).fetchone()
        if not r or not r[kind]:raise HTTPException(404)
        return Response(base64.b64decode(r[kind].split(',',1)[1]),media_type='image/webp',headers={'Cache-Control':'public,max-age=300','X-Content-Type-Options':'nosniff'})
    @app.get('/members',include_in_schema=False)
    def members():
        with conn() as c:rows=c.execute('SELECT handle,display_name,bio,avatar,location FROM user_profiles WHERE is_public=1 ORDER BY updated_at DESC LIMIT 60').fetchall()
        cards=''
        for r in rows:
            avatar=f'<img class="profile-avatar" src="/api/profile-media/{esc(r["handle"])}/avatar" alt="{esc(r["display_name"])}" loading="lazy">' if r['avatar'] else f'<div class="profile-avatar" aria-hidden="true">{esc(r["display_name"][:1])}</div>'
            cards+=f'<article class="card member-card">{avatar}<h2><a href="/members/{esc(r["handle"])}">{esc(r["display_name"])}</a></h2><p>{esc(r["bio"][:160])}</p><small>{esc(r["location"])}</small></article>'
        return page('Meet the WOW Community','Discover public member profiles in the WOW Islamic community.','/members','<span class="eyebrow">Faith · Family · Community</span><h1>Meet our community.</h1><p>Members choose whether to publish their profiles. Contact numbers and private account information are not shown.</p><a class="btn" href="/profile/edit">Create or edit my profile</a><div class="grid">'+(cards or '<p>Public member profiles will appear here.</p>')+'</div>')
    @app.get('/members/{handle}',include_in_schema=False)
    def public_profile(handle:str):
        with conn() as c:
            r=c.execute('SELECT * FROM user_profiles WHERE handle=? AND is_public=1',(handle,)).fetchone()
            if not r:raise HTTPException(404,'Profile is not public')
            products=c.execute('SELECT id,title,description,price FROM listings WHERE user_id=? AND active=1 ORDER BY created_at DESC LIMIT 60',(r['user_id'],)).fetchall()
            posts=c.execute('SELECT id,body,created_at FROM posts WHERE user_id=? AND active=1 ORDER BY created_at DESC LIMIT 10',(r['user_id'],)).fetchall()
        color=THEMES.get(r['theme'],THEMES['blue']);pattern=r['pattern'] if r['pattern'] in ('solid','dots','gradient') else 'solid'
        cover=f'<img class="profile-cover" src="/api/profile-media/{esc(handle)}/cover" alt="Cover image selected by {esc(r["display_name"])}">' if r['cover'] else '<div class="profile-cover" aria-hidden="true"></div>'
        avatar=f'<img class="profile-avatar" src="/api/profile-media/{esc(handle)}/avatar" alt="{esc(r["display_name"])}">' if r['avatar'] else f'<div class="profile-avatar" aria-hidden="true">{esc(r["display_name"][:1])}</div>'
        featured=json.loads(r['featured']);products=sorted(products,key=lambda x:(0 if x['id'] in featured else 1,-x['id']))
        cards=''.join(f'<article class="card"><small>{"Featured product" if x["id"] in featured else "Product"}</small><h3><a href="/marketplace/{x["id"]}">{esc(x["title"])}</a></h3><p class="price">₱{float(x["price"]):,.2f}</p><p>{esc(x["description"][:150])}</p></article>' for x in products)
        postcards=''.join(f'<article class="card"><p class="text">{esc(x["body"][:300])}</p><a href="/community/{x["id"]}">Read, like, comment & share →</a></article>' for x in posts)
        content=f'<div class="profile-space profile-pattern-{pattern}" style="--profile-accent:{color};padding:20px;border-radius:20px;border-top:5px solid {color}">{cover}<div class="profile-head">{avatar}<div><h1>{esc(r["display_name"])}</h1><span>@{esc(handle)}</span></div></div><section class="panel"><p class="text">{esc(r["bio"])}</p><p class="meta">{esc(r["location"])}</p></section><h2>Products</h2><div class="grid">{cards or "<p>No public products yet.</p>"}</div><h2>Community posts</h2><div class="grid">{postcards or "<p>No public posts yet.</p>"}</div></div>'
        schema={'@context':'https://schema.org','@type':'ProfilePage','mainEntity':{'@type':'Person','name':r['display_name'],'description':r['bio'],'url':ORIGIN+'/members/'+handle}}
        return page(r['display_name']+' — WOW community profile',r['bio'] or 'Public WOW community profile.','/members/'+handle,content,schema)
