import os, tempfile, unittest, subprocess, re
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

sandbox=tempfile.TemporaryDirectory()
os.environ['DATABASE_PATH']=sandbox.name+'/test.db'
os.environ['MARKETING_ASSET_DIR']=sandbox.name+'/assets'
os.environ.pop('OPENAI_API_KEY',None)
import main

class AIServicesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(main.app)
        cls.tokens=[]
        for i in range(2):
            r=cls.client.post('/api/register',json={'name':f'User {i}','email':f'u{i}@example.com','password':'test-password'})
            cls.tokens.append({'Authorization':'Bearer '+r.json()['token']})
        with main.conn() as c:c.execute("UPDATE users SET role='admin' WHERE email='u0@example.com'")

    def test_generation_and_isolation(self):
        c=self.client;h=self.tokens[1]
        payload={'tool':'description','prompt':'WOW NINA shirts','language':'Bisaya'}
        self.assertEqual(c.post('/api/ai/generate',json=payload).status_code,401)
        before=c.get('/api/ai/wallet',headers=h).json()['credits']
        self.assertEqual(c.post('/api/ai/generate',json=payload,headers=h).status_code,503)
        self.assertEqual(c.get('/api/ai/wallet',headers=h).json()['credits'],before)
        with patch.object(main,'provider_text',return_value='Test AI draft'):
            r=c.post('/api/ai/generate',json=payload,headers=h)
            self.assertEqual(r.json()['result'],'Test AI draft')
        self.assertEqual(c.get('/api/ai/wallet',headers=h).json()['credits'],before-2)
        self.assertEqual(len(c.get('/api/ai/history',headers=h).json()),1)
        self.assertEqual(c.get('/api/ai/history',headers=self.tokens[0]).json(),[])
        with patch.object(main,'provider_text',side_effect=HTTPException(502,'Provider failed')):
            self.assertEqual(c.post('/api/ai/generate',json=payload,headers=h).status_code,502)
        self.assertEqual(c.get('/api/ai/wallet',headers=h).json()['credits'],before-2)

    def test_admin_and_assets(self):
        c=self.client;h=self.tokens[0];payload={'brand':'WOW SUPER APP','topic':'Create and connect','cta':'Join today'}
        self.assertEqual(c.post('/api/admin/marketing/drafts',json=payload,headers=self.tokens[1]).status_code,403)
        r=c.post('/api/admin/marketing/drafts',json=payload,headers=h);self.assertEqual(r.status_code,200)
        path='/api/admin/marketing/drafts/'+str(r.json()['id'])
        self.assertEqual(c.get(path+'/visual.png',headers=self.tokens[1]).status_code,403)
        r=c.get(path+'/visual.png',headers=h);self.assertTrue(r.content.startswith(b'\x89PNG'))
        r=c.get(path+'/video.mp4',headers=h);self.assertEqual(r.status_code,200);self.assertIn(b'ftyp',r.content[:32])
        self.assertEqual(c.put(path+'/status',json={'status':'approved'},headers=h).json()['published'],False)
        self.assertEqual(c.put(path+'/status',json={'status':'published'},headers=h).status_code,400)

    def test_unified_hiring_admin(self):
        c=self.client;admin=self.tokens[0];member=self.tokens[1]
        payload={'title':'Shop assistant','description':'Help customers in store','location':'Mabini','contact':'employer@example.com'}
        r=c.post('/api/jobs',json=payload,headers=member);self.assertEqual(r.status_code,200);job=r.json()['id']
        self.assertEqual(c.get('/api/admin/jobs').status_code,401)
        self.assertEqual(c.get('/api/admin/jobs',headers=member).status_code,403)
        self.assertEqual(c.post(f'/api/admin/jobs/{job}/close',headers=member).status_code,403)
        c.post(f'/api/jobs/{job}/apply',json={'message':'Application','contact':'applicant@example.com'},headers=admin)
        c.post(f'/api/jobs/{job}/report',json={'reason':'Please review this post'},headers=admin)
        d=c.get('/api/admin/jobs?q=Shop',headers=admin).json()
        self.assertEqual(d['jobs'][0]['applications'],1);self.assertEqual(d['jobs'][0]['reports'],1)
        self.assertEqual(c.post(f'/api/admin/jobs/{job}/close',headers=admin).status_code,200)
        self.assertFalse(c.get('/api/admin/jobs',headers=admin).json()['jobs'][0]['active'])
        self.assertEqual(c.post(f'/api/jobs/{job}/apply',json={'message':'Application','contact':'x@example.com'},headers=admin).status_code,404)
        self.assertEqual(c.post('/api/admin/jobs/99999/close',headers=admin).status_code,404)
        for route in ['/admin','/super-admin','/admin/super','/admin/rewards']:
            self.assertEqual(c.get(route).status_code,200)

    def test_routes_and_scripts(self):
        for path in ['/ai-services','/admin/marketing']:
            self.assertEqual(self.client.get(path).status_code,200)
        for name in ['ai-services.html','marketing-admin.html','index.html','platform-admin.html']:
            for i,s in enumerate(re.findall(r'<script>(.*?)</script>',Path('static',name).read_text(),re.S)):
                p=Path(sandbox.name,f'{name}-{i}.js');p.write_text(s)
                subprocess.run(['node','--check',str(p)],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
