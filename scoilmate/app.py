"""Minimal preview only: no accounts, student data, grading or database."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="ScoilMate preview", docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/static/branding', StaticFiles(directory=ROOT / 'assets' / 'branding'), name='branding')


@app.get('/health')
def health():
    return {'status': 'ok', 'app': 'ScoilMate', 'mode': 'preview'}


@app.get('/', response_class=HTMLResponse)
def landing():
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ScoilMate — Junior Cycle learning preview</title>
<link rel="icon" href="/static/branding/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/static/branding/scoilmate-icon-32.png">
<link rel="apple-touch-icon" href="/static/branding/scoilmate-icon-180.png">
<style>
:root{font-family:system-ui,sans-serif;color:#181744;background:#f3f8f8}body{margin:0;padding:2rem 1rem}main{max-width:58rem;margin:auto}header{display:flex;align-items:center;gap:1.4rem}img{width:100px;height:100px}h1{font-size:clamp(2.3rem,7vw,4rem);margin:.1em 0}p{line-height:1.6}.notice{background:#fff5cd;border-left:5px solid #806100;padding:1rem}.subjects{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem;margin:2rem 0}article{background:white;border:1px solid #c6d3dd;border-radius:1rem;padding:1.4rem}a{color:#292583}footer{margin-top:2rem;font-size:.95rem}
</style></head><body><main>
<header><img src="/static/branding/scoilmate-icon-192.png" alt="ScoilMate book and shamrock logo"><div><h1>ScoilMate</h1><p>Your Junior Cycle learning companion</p></div></header>
<p class="notice"><strong>Planning preview — not ready for student use.</strong> This page tests branding and local connectivity only. Accounts, quizzes, hints, progress tracking and administration are not implemented. Do not enter or send personal data.</p>
<h2>Learn. Practise. Understand.</h2><p>The planned learning loop combines short topic help, original practice questions, optional hints and clear explanations. It supplements teaching; it is not an official resource or an exam simulator.</p>
<section class="subjects" aria-label="Planned subjects"><article><h3>English</h3><p>Reading, writing and preparation for oral-language learning.</p></article><article><h3 lang="ga">Gaeilge</h3><p>Distinct T1 and T2 pathways, with level-appropriate content requiring educator review.</p></article><article><h3>History</h3><p>Evidence, interpretation and historical contexts at common level.</p></article></section>
<p><a href="/health">Check preview health</a></p><footer>Local testing preview · No student database · No login · No analytics. Direct HTTP is for a trusted test LAN only; production will require HTTPS behind nginx.</footer>
</main></body></html>'''
