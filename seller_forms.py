"""Public seller intake and an administrator-only review inbox."""
import base64, hashlib, io, json, secrets, time
from pathlib import Path
from fastapi import Header, HTTPException, Request
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, ValidationError

class SellerIntake(BaseModel):
    shop: str = Field(min_length=1,max_length=120)
    name: str = Field(min_length=1,max_length=100)
    location: str = Field(min_length=1,max_length=200)
    contact: str = Field(min_length=1,max_length=160)
    facebook: str = Field(default='',max_length=300)
    product: str = Field(min_length=1,max_length=140)
    category: str = Field(min_length=1,max_length=80)
    brand: str = Field(default='',max_length=100)
    price: float = Field(ge=0,le=100000000,allow_inf_nan=False)
    condition: str = Field(min_length=1,max_length=60)
    stock: int = Field(ge=0,le=1000000)
    variants: str = Field(default='',max_length=500)
    description: str = Field(min_length=1,max_length=2000)
    flaws: str = Field(default='',max_length=500)
    ordering: str = Field(min_length=1,max_length=500)
    payment: str = Field(min_length=1,max_length=300)
    pickup: str = Field(default='',max_length=300)
    delivery: str = Field(min_length=1,max_length=500)
    delivery_fee: str = Field(min_length=1,max_length=150)
    preparation: str = Field(min_length=1,max_length=200)
    returns: str = Field(min_length=1,max_length=500)
    consent: bool
    photos: list[str] = Field(min_length=1,max_length=5)
    website: str = Field(default='',max_length=200)

def install_seller_forms(app,conn,admin_only,base):
    with conn() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS seller_intake(id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at INTEGER NOT NULL, rate_key TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_seller_intake_created ON seller_intake(created_at);''')
    @app.get('/seller-form',include_in_schema=False)
    def seller_form():
        return FileResponse(Path(base)/'static/seller-form.html')
    @app.get('/admin/sellers',include_in_schema=False)
    def seller_review():
        return FileResponse(Path(base)/'static/seller-review.html',headers={'Cache-Control':'no-store'})
    @app.post('/api/seller-submissions')
    async def submit_seller(request:Request):
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>1800000:raise HTTPException(413,'Photos are too large. Choose up to five smaller images.')
        try:data=SellerIntake.model_validate_json(bytes(raw))
        except (ValidationError,ValueError):raise HTTPException(422,'Complete every required field and attach 1–5 product photos.')
        if data.website or not data.consent:raise HTTPException(400,'Please confirm permission to submit this listing.')
        values=data.model_dump(exclude={'website'})
        for key,value in values.items():
            if isinstance(value,str):
                values[key]=value.strip()
                if not values[key] and key in ('shop','name','location','contact','product','category','condition','description','ordering','payment','delivery','delivery_fee','preparation','returns'):
                    raise HTTPException(422,'Required fields cannot be blank.')
        processed=[]
        for photo in data.photos:
            try:
                if not photo.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')):raise ValueError()
                image_bytes=base64.b64decode(photo.split(',',1)[1],validate=True)
                if len(image_bytes)>250000:raise ValueError()
                with Image.open(io.BytesIO(image_bytes)) as original:
                    if original.width*original.height>16000000:raise ValueError()
                    image=original.convert('RGB');image.thumbnail((1000,1000))
                    out=io.BytesIO();image.save(out,'WEBP',quality=80)
                processed.append('data:image/webp;base64,'+base64.b64encode(out.getvalue()).decode())
            except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError):
                raise HTTPException(400,'A product photo is invalid or too large. Choose JPG, PNG or WebP images.')
        values['photos']=processed
        now=int(time.time());ref='WOW-'+secrets.token_hex(8).upper()
        rate_key=hashlib.sha256((request.client.host if request.client else 'unknown').encode()).hexdigest()
        with conn() as c:
            recent=c.execute('SELECT COUNT(*) FROM seller_intake WHERE rate_key=? AND created_at>?',(rate_key,now-3600)).fetchone()[0]
            if recent>=30:raise HTTPException(429,'Too many submissions. Please try again later.')
            c.execute('INSERT INTO seller_intake(id,payload,status,created_at,rate_key) VALUES (?,?,?,?,?)',(ref,json.dumps(values,ensure_ascii=False),'pending',now,rate_key))
        return {'ok':True,'reference':ref,'status':'pending','message':'Submitted for admin review. This product is not yet publicly listed.'}
    @app.get('/api/admin/seller-submissions')
    def seller_inbox(authorization:str|None=Header(None)):
        admin_only(authorization)
        with conn() as c:rows=c.execute('SELECT id,payload,status,created_at FROM seller_intake ORDER BY created_at DESC LIMIT 100').fetchall()
        items=[]
        for r in rows:
            data=json.loads(r['payload']);items.append({'id':r['id'],'shop':data['shop'],'product':data['product'],'price':data['price'],'status':r['status'],'created_at':r['created_at']})
        return {'submissions':items}
    @app.get('/api/admin/seller-submissions/{reference}')
    def seller_detail(reference:str,authorization:str|None=Header(None)):
        admin_only(authorization)
        with conn() as c:r=c.execute('SELECT id,payload,status,created_at FROM seller_intake WHERE id=?',(reference,)).fetchone()
        if not r:raise HTTPException(404,'Submission not found')
        return {'id':r['id'],'data':json.loads(r['payload']),'status':r['status'],'created_at':r['created_at']}
