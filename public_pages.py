"""Shared safe rendering for public, crawlable WOW pages."""
import html,json
from fastapi.responses import HTMLResponse
ORIGIN='https://wow-super-app.onrender.com'
def esc(value):return html.escape(str(value),quote=True)
def structured(value):return json.dumps(value,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
def page(title,description,path,content,jsonld=None,script='',noindex=False):
    canonical=ORIGIN+path
    schema='<script type="application/ld+json">'+structured(jsonld)+'</script>' if jsonld else ''
    return HTMLResponse(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} | WOW SUPER APP</title><meta name="description" content="{esc(description[:160])}"><meta name="robots" content="{'noindex,nofollow' if noindex else 'index,follow'}"><link rel="canonical" href="{esc(canonical)}"><meta property="og:type" content="website"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description[:250])}"><meta property="og:url" content="{esc(canonical)}"><meta property="og:image" content="{ORIGIN}/static/assets/wow-super-app-hero.webp"><meta name="twitter:card" content="summary_large_image"><link rel="stylesheet" href="/static/public-pages.css?v=20261107">{schema}</head><body><header class="top"><a class="brand" href="/">WOW <span>SUPER APP</span></a><nav><a href="/marketplace">Marketplace</a><a href="/community">Community</a><a href="/members">Members</a><a href="/profile/edit">My Profile</a></nav></header><main>{content}</main><footer>WOW SUPER APP · Connect in faith. Grow together.<br><a href="/community-guidelines">Community guidelines</a> · <a href="/seller-form">Seller form</a></footer>{'<script src="'+script+'"></script>' if script else ''}</body></html>''',headers={'Cache-Control':'no-store' if noindex else 'public, max-age=60'})
