from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse
from aiogram import Bot,Dispatcher
from aiogram.types import Update
from .config import settings
from .db import init_db,Session,WebSession,User,FraudSignal
from .bot import setup
from sqlalchemy import select
import hashlib,hmac,json
from datetime import datetime,timezone

app=FastAPI(title="HydroCoin Bot")
bot=Bot(settings.BOT_TOKEN);dp=Dispatcher();setup(dp)

@app.on_event("startup")
async def startup():await init_db()

@app.get("/health")
async def health():return {"status":"ok"}


def validate_webapp_init_data(init_data:str)->int|None:
    if not init_data:return None
    from urllib.parse import parse_qsl
    data=dict(parse_qsl(init_data,keep_blank_values=True))
    received=data.pop("hash",None)
    if not received:return None
    check="\n".join(f"{k}={v}" for k,v in sorted(data.items()))
    secret=hmac.new(b"WebAppData",settings.BOT_TOKEN.encode(),hashlib.sha256).digest()
    calc=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc,received):return None
    try:return int(json.loads(data["user"])["id"])
    except:return None

@app.get("/webapp",response_class=HTMLResponse)
async def webapp(token:str=""):
    return HTMLResponse(f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>HydroCoin</title></head>
<body style="font-family:sans-serif;text-align:center;padding:35px"><h2>HydroCoin xavfsizlik tekshiruvi</h2><p id="p">Tekshirilmoqda...</p>
<script src="https://telegram.org/js/telegram-web-app.js"></script><script>
(async()=>{{const t=new URLSearchParams(location.search).get("token");const tg=window.Telegram.WebApp;tg.ready();
const r=await fetch("/webapp/verify",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{token:t,init_data:tg.initData}})}});const j=await r.json();
document.getElementById("p").textContent=j.message;if(j.ok)setTimeout(()=>tg.close(),700)}})();</script></body></html>""")

@app.post("/webapp/verify")
async def verify(request:Request):
    d=await request.json();token=str(d.get("token",""));tgid=validate_webapp_init_data(d.get("init_data",""))
    if not tgid:return {"ok":False,"message":"Telegram WebApp tasdig‘i muvaffaqiyatsiz."}
    h=hashlib.sha256(token.encode()).hexdigest()
    async with Session() as s:
        ws=(await s.execute(select(WebSession).where(WebSession.token_hash==h,WebSession.used==False))).scalar_one_or_none()
        if not ws:return {"ok":False,"message":"Havola eskirgan yoki ishlatilgan."}
        u=await s.get(User,ws.user_id)
        if not u or u.tg_id!=tgid:return {"ok":False,"message":"Account mos kelmadi."}
        ws.used=True;ws.used_at=datetime.now(timezone.utc);u.web_verified=True
        s.add(FraudSignal(user_id=u.id,kind="webapp_verified",value="telegram_initdata_ok",score=0));await s.commit()
    return {"ok":True,"message":"Tekshiruv muvaffaqiyatli. Botga qayting."}

@app.post("/webhook")
async def webhook(request:Request):
    update=Update.model_validate(await request.json(),context={"bot":bot})
    await dp.feed_update(bot,update)
    return {"ok":True}
