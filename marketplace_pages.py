"""Public product pages and member-only order inquiries."""
import secrets,time
from fastapi import Header,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,Field
from public_pages import page,esc,ORIGIN

class CommentMessage(BaseModel):
    message:str=Field(min_length=1,max_length=1000)

class ProductInquiry(BaseModel):
    listing_id:int
    quantity:int=Field(default=1,ge=1,le=1000)
    message:str=Field(min_length=2,max_length=1000)

def install_marketplace(app,conn,user):
    with conn() as c:c.execute("CREATE TABLE IF NOT EXISTS marketplace_inquiries(id TEXT PRIMARY KEY,listing_id INTEGER NOT NULL REFERENCES listings(id),seller_id INTEGER NOT NULL REFERENCES users(id),buyer_id INTEGER NOT NULL REFERENCES users(id),quantity INTEGER NOT NULL,message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at INTEGER NOT NULL)")
    @app.get('/marketplace',include_in_schema=False)
    def public_marketplace(q:str='',p:int=1):
        q=q.strip()[:80];p=max(1,min(1000,p))
        with conn() as c:rows=c.execute("SELECT l.id,l.title,l.description,l.price,l.category,u.name AS seller FROM listings l JOIN users u ON u.id=l.user_id WHERE l.active=1 AND (l.title LIKE ? OR l.description LIKE ?) ORDER BY l.created_at DESC,l.id DESC LIMIT 25 OFFSET ?",('%'+q+'%','%'+q+'%',(p-1)*24)).fetchall()
        cards=''.join(f'<article class="card"><small>{esc(r["category"])}</small><h2><a href="/marketplace/{r["id"]}">{esc(r["title"])}</a></h2><p>{esc(r["description"][:180])}</p><div class="price">₱{float(r["price"]):,.2f}</div><p class="meta">Seller: {esc(r["seller"])}</p><a class="btn secondary" href="/marketplace/{r["id"]}">View product →</a></article>' for r in rows[:24])
        if not cards:cards='<div class="panel"><h2>No matching products yet.</h2><p>Local sellers are welcome to submit their products for review.</p><a href="/seller-form">Submit a product →</a></div>'
        paging=(f'<a class="btn secondary" href="/marketplace?p={p-1}&amp;q={esc(q)}">Previous</a>' if p>1 else '')+(f'<a class="btn secondary" href="/marketplace?p={p+1}&amp;q={esc(q)}">Next</a>' if len(rows)>24 else '')
        content=f'<section class="intro"><span class="eyebrow">WOW Islamic community marketplace</span><h1>Discover local products.</h1><p>Browse publicly. Sign in to send an order request or inquiry. Sellers must follow our halal and respectful community guidelines.</p><div class="actions"><a class="btn" href="/seller-form">Sell with WOW</a><a class="btn secondary" href="/marketplace/inquiries">My order inquiries</a></div></section><form class="search" action="/marketplace"><input name="q" value="{esc(q)}" maxlength="80" aria-label="Search products" placeholder="Search products…"><button>Search</button></form><div class="grid">{cards}</div><div class="actions">{paging}</div><p class="notice">WOW facilitates product discovery and order inquiries. Payments and delivery are arranged directly with the seller; there is no online payment checkout.</p>'
        return page('Halal & Local Marketplace','Browse local products on WOW SUPER APP. Public product pages with member-only order inquiries.','/marketplace',content,noindex=bool(q))
    @app.get('/marketplace/inquiries',include_in_schema=False)
    def inquiry_page():
        return page('My Marketplace Inquiries','Private buyer and seller order inquiries.','/marketplace/inquiries','<h1>My order inquiries.</h1><p>Messages you sent as a buyer and received as a seller.</p><p id="status" class="status">Checking your account…</p><div id="inquiries"></div>',script='/static/marketplace-inquiries.js',noindex=True)
    @app.get('/marketplace/{listing_id}',include_in_schema=False)
    def product_page(listing_id:int):
        with conn() as c:r=c.execute('SELECT l.*,u.name AS seller FROM listings l JOIN users u ON u.id=l.user_id WHERE l.id=? AND l.active=1',(listing_id,)).fetchone()
        if not r:raise HTTPException(404,'Product not found')
        schema={'@context':'https://schema.org','@type':'Product','name':r['title'],'description':r['description'],'category':r['category'],'offers':{'@type':'Offer','price':str(r['price']),'priceCurrency':'PHP','url':ORIGIN+'/marketplace/'+str(listing_id),'seller':{'@type':'Person','name':r['seller']}}}
        content=f'<a href="/marketplace">← Browse Marketplace</a><article class="panel body-copy" style="margin-top:24px"><span class="eyebrow">{esc(r["category"])}</span><h1>{esc(r["title"])}</h1><p class="price">₱{float(r["price"]):,.2f}</p><p class="meta">Listed by {esc(r["seller"])}</p><div class="text">{esc(r["description"])}</div></article><section class="panel body-copy" style="margin-top:22px"><h2>Ask the seller / request an order</h2><p id="account-status">Sign in to send a message.</p><a id="signin" class="btn" href="/?next=/marketplace/{listing_id}">Sign in or register →</a><form id="inquiry-form" data-listing="{listing_id}" hidden><label>Quantity<input name="quantity" type="number" min="1" max="1000" value="1" required></label><label>Your message<textarea name="message" rows="4" minlength="2" maxlength="1000" placeholder="Ask about availability, delivery, sizes or how to order…" required></textarea></label><button>Send order inquiry</button></form><p id="status" class="status" role="status"></p><p class="notice">An inquiry is not a completed purchase. Confirm stock, the final price, payment and delivery with the seller. Public listings are not a guarantee of seller or product verification.</p></section>'
        return page(r['title'],r['description'],'/marketplace/'+str(listing_id),content,schema,script='/static/marketplace-product.js')
    @app.post('/api/marketplace/inquiries')
    def send_inquiry(data:ProductInquiry,authorization:str|None=Header(None)):
        buyer=user(authorization);message=data.message.strip()
        if len(message)<2:raise HTTPException(400,'Enter a message.')
        with conn() as c:
            listing=c.execute('SELECT id,user_id FROM listings WHERE id=? AND active=1',(data.listing_id,)).fetchone()
            if not listing:raise HTTPException(404,'Product not found')
            if listing['user_id']==buyer['id']:raise HTTPException(400,'You cannot send an order inquiry to yourself.')
            recent=c.execute('SELECT COUNT(*) FROM marketplace_inquiries WHERE buyer_id=? AND created_at>?',(buyer['id'],int(time.time())-3600)).fetchone()[0]
            if recent>=30:raise HTTPException(429,'Please wait before sending more inquiries.')
            ref='ORDER-'+secrets.token_hex(8).upper()
            c.execute('INSERT INTO marketplace_inquiries(id,listing_id,seller_id,buyer_id,quantity,message,created_at) VALUES (?,?,?,?,?,?,?)',(ref,data.listing_id,listing['user_id'],buyer['id'],data.quantity,message,int(time.time())))
        return {'ok':True,'reference':ref}
    @app.get('/api/marketplace/inquiries')
    def get_inquiries(authorization:str|None=Header(None)):
        viewer=user(authorization)
        with conn() as c:rows=c.execute('SELECT i.*,l.title,b.name AS buyer,s.name AS seller FROM marketplace_inquiries i JOIN listings l ON l.id=i.listing_id JOIN users b ON b.id=i.buyer_id JOIN users s ON s.id=i.seller_id WHERE i.buyer_id=? OR i.seller_id=? ORDER BY i.created_at DESC LIMIT 100',(viewer['id'],viewer['id'])).fetchall()
        return {'inquiries':[dict(r) for r in rows],'viewer_id':viewer['id']}
    with conn() as c:c.execute('CREATE TABLE IF NOT EXISTS marketplace_replies(id TEXT PRIMARY KEY,inquiry_id TEXT NOT NULL REFERENCES marketplace_inquiries(id),user_id INTEGER NOT NULL REFERENCES users(id),message TEXT NOT NULL,created_at INTEGER NOT NULL)')
    @app.get('/api/marketplace/inquiries/{reference}')
    def conversation(reference:str,authorization:str|None=Header(None)):
        viewer=user(authorization)
        with conn() as c:
            inquiry=c.execute('SELECT * FROM marketplace_inquiries WHERE id=?',(reference,)).fetchone()
            if not inquiry or viewer['id'] not in (inquiry['seller_id'],inquiry['buyer_id']):raise HTTPException(404,'Inquiry not found')
            replies=c.execute('SELECT r.message,r.created_at,u.name AS author FROM marketplace_replies r JOIN users u ON u.id=r.user_id WHERE r.inquiry_id=? ORDER BY r.created_at,r.id LIMIT 200',(reference,)).fetchall()
        return {'replies':[dict(r) for r in replies]}
    @app.post('/api/marketplace/inquiries/{reference}/replies')
    def reply(reference:str,data:CommentMessage,authorization:str|None=Header(None)):
        viewer=user(authorization);message=data.message.strip()
        if not message:raise HTTPException(400,'Enter a reply.')
        with conn() as c:
            inquiry=c.execute('SELECT * FROM marketplace_inquiries WHERE id=?',(reference,)).fetchone()
            if not inquiry or viewer['id'] not in (inquiry['seller_id'],inquiry['buyer_id']):raise HTTPException(404,'Inquiry not found')
            recent=c.execute('SELECT COUNT(*) FROM marketplace_replies WHERE user_id=? AND created_at>?',(viewer['id'],int(time.time())-3600)).fetchone()[0]
            if recent>=100:raise HTTPException(429,'Please wait before sending more replies.')
            c.execute('INSERT INTO marketplace_replies(id,inquiry_id,user_id,message,created_at) VALUES (?,?,?,?,?)',(secrets.token_hex(12),reference,viewer['id'],message,int(time.time())))
        return {'ok':True}
