"""Admin-only Runway text-to-video, with durable job tracking and no auto retries."""
import json
import os
import time
import uuid
import urllib.request
import urllib.error
from urllib.parse import urlparse
from typing import Literal
from fastapi import Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

MODEL='gen4.5'
SECONDS=5
DAILY_LIMIT=3
TERMINAL={'SUCCEEDED','FAILED','CANCELLED','UNKNOWN'}

class VideoInput(BaseModel):
    request_id: uuid.UUID
    prompt: str=Field(min_length=3,max_length=800)
    ratio: Literal['720:1280','1280:720']='720:1280'
    confirm_paid: bool=False

class UncertainSubmission(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def runway_request(path, payload=None):
    key=os.getenv('RUNWAYML_API_SECRET','').strip()
    if not key: raise HTTPException(503,'Runway API key is not configured.')
    req=urllib.request.Request('https://api.dev.runwayml.com/v1/'+path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization':'Bearer '+key,'X-Runway-Version':'2024-11-06','Content-Type':'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=25) as response:
            data=json.loads(response.read(1048576))
        if not isinstance(data,dict):raise ValueError('Invalid response')
        return data
    except urllib.error.HTTPError as error:
        if error.code>=500 or error.code in (301,302,303,307,308):raise UncertainSubmission() from None
        messages={401:'Runway rejected the API key.',403:'Runway access denied. Check the project permissions.',
            402:'Add API credits in the Runway Developer Portal.',429:'Runway is busy or the project has reached its limit.',
            400:'Runway rejected the request. Check the prompt and project credits.',422:'Runway rejected the video settings.'}
        raise HTTPException(502,messages.get(error.code,'Runway rejected this request.')) from None
    except (urllib.error.URLError,TimeoutError,ValueError,OSError):
        raise UncertainSubmission() from None

def public_job(row):
    item=dict(row)
    item.pop('owner_id',None)
    item['outputs']=json.loads(item.pop('output_json'))
    item['model']=MODEL
    item['seconds']=SECONDS
    return item

def install_video(app,conn,admin_only,base):
    with conn() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS ai_video_jobs(
            job_id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
            prompt TEXT NOT NULL, ratio TEXT NOT NULL, status TEXT NOT NULL,
            provider_id TEXT NOT NULL DEFAULT '', output_json TEXT NOT NULL DEFAULT '[]',
            created_at INTEGER NOT NULL, checked_at INTEGER NOT NULL DEFAULT 0,
            error TEXT NOT NULL DEFAULT '')''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_video_created ON ai_video_jobs(created_at)')

    @app.get('/admin/video')
    def video_page():
        return FileResponse(os.path.join(base,'static','admin-video.html'))

    @app.get('/api/admin/video/config')
    def video_config(authorization:str|None=Header(None)):
        admin_only(authorization)
        return {'configured':bool(os.getenv('RUNWAYML_API_SECRET','').strip()),'model':MODEL,
            'seconds':SECONDS,'estimated_runway_credits':60,'estimated_usd':0.60,
            'daily_limit':DAILY_LIMIT,'trial_credits_used':False}

    @app.get('/api/admin/video/jobs')
    def video_jobs(authorization:str|None=Header(None)):
        admin=admin_only(authorization)
        with conn() as db:
            rows=db.execute('SELECT * FROM ai_video_jobs WHERE owner_id=? ORDER BY created_at DESC LIMIT 30',(admin['id'],)).fetchall()
        return {'jobs':[public_job(r) for r in rows]}

    @app.post('/api/admin/video/jobs')
    def create_video(body:VideoInput,authorization:str|None=Header(None)):
        admin=admin_only(authorization)
        if not body.confirm_paid:raise HTTPException(400,'Confirm the Runway API charge before generating.')
        if not os.getenv('RUNWAYML_API_SECRET','').strip():raise HTTPException(503,'Runway API key is not configured.')
        prompt=body.prompt.strip()
        if len(prompt)<3:raise HTTPException(400,'Enter a video prompt.')
        job_id=str(body.request_id);now=int(time.time())
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM ai_video_jobs WHERE job_id=?',(job_id,)).fetchone()
            if old:
                if old['owner_id']!=admin['id']:raise HTTPException(404,'Video not found')
                if old['prompt']!=prompt or old['ratio']!=body.ratio:raise HTTPException(409,'Use a new request for changed video details.')
                return public_job(old)
            # Count all reserved attempts, including ambiguous network failures.
            count=db.execute('SELECT COUNT(*) FROM ai_video_jobs WHERE created_at>=?',(now-now%86400,)).fetchone()[0]
            if count>=DAILY_LIMIT:raise HTTPException(429,'Daily video limit reached. Check existing jobs first. Limit resets at 08:00 Philippine time.')
            db.execute('INSERT INTO ai_video_jobs(job_id,owner_id,prompt,ratio,status,created_at) VALUES (?,?,?,?,?,?)',
                (job_id,admin['id'],prompt,body.ratio,'SUBMITTING',now))
        # Provider HTTP calls never hold the database transaction open.
        # No retries on submission: an ambiguous timeout might already have incurred a charge.
        provider_id='';status='UNKNOWN';error='Submission is unconfirmed. Check Runway tasks before starting another video.'
        try:
            result=runway_request('text_to_video',{'model':MODEL,'promptText':prompt,'ratio':body.ratio,'duration':SECONDS})
            provider_id=str(uuid.UUID(result['id']))
            status='PENDING';error=''
        except HTTPException as exc:
            status='FAILED';error=str(exc.detail)
        except (UncertainSubmission,KeyError,ValueError,TypeError):
            pass
        with conn() as db:
            db.execute('UPDATE ai_video_jobs SET provider_id=?,status=?,error=? WHERE job_id=?',(provider_id,status,error,job_id))
            row=db.execute('SELECT * FROM ai_video_jobs WHERE job_id=?',(job_id,)).fetchone()
        return public_job(row)

    @app.get('/api/admin/video/jobs/{job_id}')
    def check_video(job_id:uuid.UUID,authorization:str|None=Header(None)):
        admin=admin_only(authorization);job_id=str(job_id);now=int(time.time())
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM ai_video_jobs WHERE job_id=? AND owner_id=?',(job_id,admin['id'])).fetchone()
            if not row:raise HTTPException(404,'Video not found')
            item=public_job(row)
            if item['status'] in TERMINAL or not item['provider_id'] or now-item['checked_at']<5:return item
            db.execute('UPDATE ai_video_jobs SET checked_at=? WHERE job_id=?',(now,job_id))
        try:
            result=runway_request('tasks/'+str(uuid.UUID(item['provider_id'])))
        except (UncertainSubmission,HTTPException):
            item['error']='Cannot refresh Runway right now. The existing task is saved; try Check status later.'
            return item
        status=result.get('status')
        if status not in {'PENDING','THROTTLED','RUNNING','SUCCEEDED','FAILED','CANCELLED'}:
            item['error']='Runway returned an unfamiliar status. Check the Developer Portal.'
            return item
        outputs=[]
        for link in result.get('output',[]) if isinstance(result.get('output',[]),list) else []:
            if isinstance(link,str):
                parsed=urlparse(link)
                if parsed.scheme=='https' and parsed.hostname and not parsed.username and not parsed.password:
                    outputs.append(link)
        error='Runway could not complete this video. Check its task details and billing.' if status in {'FAILED','CANCELLED'} else ''
        if status=='SUCCEEDED' and not outputs:
            # Do not cache an unusable success permanently; allow later refresh.
            item['error']='Video is finishing. Check status again shortly.'
            return item
        with conn() as db:
            db.execute('UPDATE ai_video_jobs SET status=?,output_json=?,error=? WHERE job_id=?',
                (status,json.dumps(outputs),error,job_id))
            row=db.execute('SELECT * FROM ai_video_jobs WHERE job_id=?',(job_id,)).fetchone()
        return public_job(row)
