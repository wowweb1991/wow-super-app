"""Public Islamic community posts with member-only likes and comments."""
import secrets,time
from datetime import datetime,timezone
from fastapi import Header,HTTPException
from pydantic import BaseModel,Field
from public_pages import page,esc,ORIGIN
class CommentData(BaseModel):body:str=Field(min_length=1,max_length=1000)
def install_community(app,conn,user):
    with conn() as c:c.executescript('''CREATE TABLE IF NOT EXISTS community_likes(post_id INTEGER NOT NULL REFERENCES posts(id),user_id INTEGER NOT NULL REFERENCES users(id),created_at INTEGER NOT NULL,PRIMARY KEY(post_id,user_id));
    CREATE TABLE IF NOT EXISTS community_comments(id TEXT PRIMARY KEY,post_id INTEGER NOT NULL REFERENCES posts(id),user_id INTEGER NOT NULL REFERENCES users(id),body TEXT NOT NULL,created_at INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1);''')
    def active_post(c,pid):
        r=c.execute('SELECT p.*,u.name AS author FROM posts p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.active=1',(pid,)).fetchone()
        if not r:raise HTTPException(404,'Post not found')
        return r
    @app.get('/community',include_in_schema=False)
    def public_community():
        with conn() as c:rows=c.execute('SELECT p.*,u.name AS author FROM posts p JOIN users u ON u.id=p.user_id WHERE p.active=1 ORDER BY p.created_at DESC,p.id DESC LIMIT 60').fetchall()
        cards=''.join(f'<article class="card"><p class="meta">By {esc(r["author"])}</p><p class="text">{esc(r["body"][:400])}</p><a href="/community/{r["id"]}">Read · Like · Comment · Share →</a></article>' for r in rows)
        content='<span class="eyebrow">Faith · Family · Kindness</span><h1>Our Islamic community.</h1><p class="intro">Share reminders, duas, reflections and helpful learning. Add reliable sources when quoting the Qur’an or hadith. Member posts are not automatically verified religious guidance.</p><div class="actions"><a class="btn" href="/?community=1">Sign in & share a post</a><a class="btn secondary" href="/community-guidelines">Community guidelines</a></div><div class="grid">'+(cards or '<p>Share a thoughtful reminder to begin the conversation.</p>')+'</div>'
        return page('Islamic Community — Reminders, Duas & Reflections','Read and share respectful Islamic reminders, duas and reflections in the WOW community.','/community',content)
    @app.get('/community/{post_id}',include_in_schema=False)
    def post_page(post_id:int):
        with conn() as c:r=active_post(c,post_id)
        title=r['body'].split('\n')[0][:90] or 'Islamic community post';date=datetime.fromtimestamp(r['created_at'],timezone.utc).isoformat()
        content=f'<a href="/community">← Islamic Community</a><article class="panel body-copy" style="margin-top:25px" id="community-post" data-post="{post_id}"><span class="eyebrow">Community reminder</span><h1>{esc(title)}</h1><p class="meta">Shared by {esc(r["author"])} · {esc(date[:10])}</p><div id="post-body" class="post-body">{esc(r["body"])}</div><p class="post-source">Member-shared content. Check cited sources and seek qualified guidance for religious rulings.</p><div class="actions"><button id="like" type="button">Like</button><button id="facebook" type="button" class="secondary">Copy Full Post & Share to Facebook</button></div><p id="share-status" class="status" role="status"></p><p class="notice">Facebook does not automatically insert the full text. This button copies the post and opens sharing; paste it into your Facebook caption before posting.</p><textarea id="copy-fallback" rows="9" readonly hidden aria-label="Full post ready to copy"></textarea></article><section class="panel body-copy" style="margin-top:25px"><h2>Comments</h2><p id="social-status" class="status" role="status"></p><div id="comments"></div><form id="comment-form"><label>Your comment<textarea name="body" rows="3" maxlength="1000" required placeholder="Keep it respectful and relevant…"></textarea></label><button>Post comment</button></form><p class="notice">Sign in to like or comment. Everyone can read and share public posts.</p></section>'
        schema={'@context':'https://schema.org','@type':'SocialMediaPosting','headline':title,'articleBody':r['body'],'datePublished':date,'author':{'@type':'Person','name':r['author']},'url':ORIGIN+'/community/'+str(post_id)}
        return page(title,r['body'],'/community/'+str(post_id),content,schema,script='/static/community-post.js')
    @app.get('/api/community/posts/{post_id}/social')
    def social(post_id:int,authorization:str|None=Header(None)):
        viewer=None
        if authorization:
            try:viewer=user(authorization)
            except HTTPException:pass
        with conn() as c:
            active_post(c,post_id)
            count=c.execute('SELECT COUNT(*) FROM community_likes WHERE post_id=?',(post_id,)).fetchone()[0]
            liked=bool(viewer and c.execute('SELECT 1 FROM community_likes WHERE post_id=? AND user_id=?',(post_id,viewer['id'])).fetchone())
            rows=c.execute('SELECT cc.id,cc.user_id,cc.body,cc.created_at,u.name AS author FROM community_comments cc JOIN users u ON u.id=cc.user_id WHERE cc.post_id=? AND cc.active=1 ORDER BY cc.created_at,cc.id LIMIT 200',(post_id,)).fetchall()
        comments=[{'id':r['id'],'body':r['body'],'created_at':r['created_at'],'author':r['author'],'can_delete':bool(viewer and (viewer['id']==r['user_id'] or viewer['role']=='admin'))} for r in rows]
        return {'likes':count,'liked':liked,'comments':comments,'signed_in':bool(viewer)}
    @app.post('/api/community/posts/{post_id}/like')
    def like(post_id:int,authorization:str|None=Header(None)):
        viewer=user(authorization)
        with conn() as c:
            active_post(c,post_id)
            exists=c.execute('SELECT 1 FROM community_likes WHERE post_id=? AND user_id=?',(post_id,viewer['id'])).fetchone()
            if exists:c.execute('DELETE FROM community_likes WHERE post_id=? AND user_id=?',(post_id,viewer['id']))
            else:c.execute('INSERT INTO community_likes(post_id,user_id,created_at) VALUES (?,?,?)',(post_id,viewer['id'],int(time.time())))
        return {'ok':True,'liked':not bool(exists)}
    @app.post('/api/community/posts/{post_id}/comments')
    def comment(post_id:int,data:CommentData,authorization:str|None=Header(None)):
        viewer=user(authorization);body=data.body.strip()
        if not body:raise HTTPException(400,'Enter a comment.')
        with conn() as c:
            active_post(c,post_id)
            recent=c.execute('SELECT COUNT(*) FROM community_comments WHERE user_id=? AND created_at>?',(viewer['id'],int(time.time())-3600)).fetchone()[0]
            if recent>=60:raise HTTPException(429,'Please wait before adding more comments.')
            cid=secrets.token_hex(12);c.execute('INSERT INTO community_comments(id,post_id,user_id,body,created_at) VALUES (?,?,?,?,?)',(cid,post_id,viewer['id'],body,int(time.time())))
        return {'ok':True,'id':cid}
    @app.delete('/api/community/comments/{comment_id}')
    def delete_comment(comment_id:str,authorization:str|None=Header(None)):
        viewer=user(authorization)
        with conn() as c:
            r=c.execute('SELECT user_id FROM community_comments WHERE id=? AND active=1',(comment_id,)).fetchone()
            if not r:raise HTTPException(404,'Comment not found')
            if viewer['id']!=r['user_id'] and viewer['role']!='admin':raise HTTPException(403,'Only the author or admin can remove this comment.')
            c.execute('UPDATE community_comments SET active=0 WHERE id=?',(comment_id,))
        return {'ok':True}
