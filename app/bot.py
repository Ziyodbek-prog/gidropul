import asyncio,hashlib,secrets
from datetime import datetime,timezone,timedelta
from aiogram import Router,Dispatcher,F
from aiogram.filters import Command,CommandStart
from aiogram.fsm.state import State,StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message,CallbackQuery,KeyboardButton,ReplyKeyboardMarkup,InlineKeyboardMarkup,InlineKeyboardButton
from sqlalchemy import select,func,desc,or_
from .config import settings
from .db import Session,User,Referral,Setting,PaymentMethod,Channel,Withdrawal,WebSession,FraudSignal,Event
from .keyboards import menu,nav,admin

r=Router()

class W(StatesGroup):
    coins=State();destination=State()
class AdminState(StatesGroup):
    broadcast=State();user_message=State()

def is_admin(x): return x.from_user.id in settings.ADMIN_IDS
async def get_user(tg_id):
    async with Session() as s:return (await s.execute(select(User).where(User.tg_id==tg_id))).scalar_one_or_none()
async def setting(k,d=""):
    async with Session() as s:
        x=await s.get(Setting,k);return x.value if x else d
async def create_session(uid):
    token=secrets.token_urlsafe(32)
    async with Session() as s:
        s.add(WebSession(user_id=uid,token_hash=hashlib.sha256(token.encode()).hexdigest()));await s.commit()
    return token

async def required_channels():
    async with Session() as s:return (await s.execute(select(Channel).where(Channel.kind=="required"))).scalars().all()

async def missing_channels(bot,tg_id):
    missing=[]
    for c in await required_channels():
        try:
            m=await bot.get_chat_member(c.chat_id,tg_id)
            if m.status in ("left","kicked"):missing.append(c)
        except:missing.append(c)
    return missing

def channel_buttons(cs):
    rows=[]
    for c in cs:
        url=c.invite_link or (f"https://t.me/{c.username}" if c.username else None)
        if url:rows.append([InlineKeyboardButton(text=f"📢 {c.title}",url=url)])
    rows.append([InlineKeyboardButton(text="🔄 Tekshirish",callback_data="check:subs")])
    rows.append([InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def ensure_gate(m):
    u=await get_user(m.from_user.id)
    if not u:return False
    if u.banned:
        await m.answer("Siz bloklangansiz.");return False
    if not u.verified:
        kb=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Kontaktimni ulashish",request_contact=True)]],resize_keyboard=True)
        await m.answer("Avval Telegram kontakt tugmasi orqali +998 raqamingizni tasdiqlang.",reply_markup=kb);return False
    if not u.web_verified:
        token=await create_session(u.id)
        url=f"{settings.WEBHOOK_URL}/webapp?token={token}"
        await m.answer("🔐 Bir martalik xavfsizlik tekshiruvidan o‘ting:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔐 Tekshiruvdan o‘tish",url=url)],
            [InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")]]));return False
    miss=await missing_channels(m.bot,m.from_user.id)
    if miss:
        await m.answer("Davom etish uchun majburiy kanallarga obuna bo‘ling.",reply_markup=channel_buttons(miss));return False
    return True

@r.message(CommandStart())
async def start(m:Message):
    parts=(m.text or "").split(maxsplit=1);inv=None
    if len(parts)==2 and parts[1].startswith("ref_"):
        try:inv=int(parts[1][4:])
        except:pass
    async with Session() as s:
        u=(await s.execute(select(User).where(User.tg_id==m.from_user.id))).scalar_one_or_none()
        if not u:
            u=User(tg_id=m.from_user.id,username=m.from_user.username,first_name=m.from_user.first_name);s.add(u);await s.flush()
            if inv and inv!=m.from_user.id:
                x=(await s.execute(select(User).where(User.tg_id==inv))).scalar_one_or_none()
                if x and not x.referral_blocked:s.add(Referral(inviter_id=x.id,invited_id=u.id));x.referrals_count+=1
        await s.commit()
    if await ensure_gate(m):await m.answer("Bosh menyu:",reply_markup=menu())

@r.message(F.contact)
async def phone(m:Message):
    if not m.contact or m.contact.user_id!=m.from_user.id:
        await m.answer("Faqat o‘zingizning kontaktingizni yuboring.");return
    digits="".join(c for c in m.contact.phone_number if c.isdigit())
    if not (digits.startswith("998") and len(digits)==12):
        await m.answer("Faqat O‘zbekiston (+998) raqami qabul qilinadi.");return
    async with Session() as s:
        u=(await s.execute(select(User).where(User.tg_id==m.from_user.id))).scalar_one()
        duplicate=(await s.execute(select(User).where(User.phone==m.contact.phone_number,User.id!=u.id))).scalars().first()
        if duplicate:
            u.phone=m.contact.phone_number;u.verified=True
            s.add(FraudSignal(user_id=u.id,kind="duplicate_phone",value="duplicate",score=90))
        else:u.phone=m.contact.phone_number;u.verified=True
        ref=(await s.execute(select(Referral).where(Referral.invited_id==u.id,Referral.rewarded==False))).scalar_one_or_none()
        if ref and not duplicate:
            ref.accepted=True;ref.rewarded=True
            reward=int(await setting("referral_reward","10"));iv=await s.get(User,ref.inviter_id)
            if iv and not iv.banned and not iv.referral_blocked:
                iv.balance+=reward;iv.referral_earned+=reward;iv.accepted_referrals+=1
                s.add(Event(user_id=iv.id,kind="referral_reward",value=reward))
        elif ref:ref.accepted=True
        await s.commit()
    await m.answer("Telefon raqami tasdiqlandi.")
    await ensure_gate(m)

@r.callback_query(F.data=="check:subs")
async def check_sub(c:CallbackQuery):
    miss=await missing_channels(c.bot,c.from_user.id)
    if miss:await c.answer("Hali barcha majburiy kanallarga obuna bo‘lmagansiz.",show_alert=True);return
    await c.message.answer("Tekshirildi. Bosh menyu:",reply_markup=menu());await c.answer()

@r.message(F.text=="💰 Pul ishlash")
async def earn(m:Message):
    if not await ensure_gate(m):return
    u=await get_user(m.from_user.id);reward=await setting("referral_reward","10");me=await m.bot.me()
    link=f"https://t.me/{me.username}?start=ref_{u.tg_id}"
    await m.answer(f"💰 Pul ishlash\n\n1 ta tasdiqlangan referral = {reward} GidroCoin\n\n🔗 {link}\n\nTakliflar: {u.referrals_count}\nQabul qilingan: {u.accepted_referrals}",reply_markup=nav())

@r.message(F.text=="👤 Mening profilim")
async def profile(m:Message):
    if not await ensure_gate(m):return
    u=await get_user(m.from_user.id)
    today=datetime.now(timezone.utc).date()
    async with Session() as s:
        q=select(func.coalesce(func.sum(Event.value),0)).where(Event.user_id==u.id,Event.kind=="referral_reward",func.date(Event.created_at)==today)
        today_gc=await s.scalar(q)
    await m.answer(f"👤 Mening profilim\n\nBot ID: {u.id}\nTelegram ID: {u.tg_id}\nReferral: {u.referrals_count}\nQabul qilingan: {u.accepted_referrals}\nReferral orqali: {u.referral_earned} GC\nBugun referral: {today_gc} GC\nYechilgan: {u.withdrawn} GC\nBalans: {u.balance} GC",reply_markup=nav())

@r.message(F.text=="💳 To‘lovlar kanali")
async def payment_channels(m:Message):
    if not await ensure_gate(m):return
    async with Session() as s:cs=(await s.execute(select(Channel).where(Channel.kind=="payment"))).scalars().all()
    await m.answer("💳 To‘lovlar kanali:",reply_markup=channel_buttons(cs) if cs else nav())

@r.message(F.text=="💸 Pul chiqarish")
async def withdraw(m:Message):
    if not await ensure_gate(m):return
    u=await get_user(m.from_user.id)
    async with Session() as s:ms=(await s.execute(select(PaymentMethod).where(PaymentMethod.active==True))).scalars().all()
    rows=[[InlineKeyboardButton(text=f"{x.name} — 1 GC={x.rate:g} {x.currency}",callback_data=f"wm:{x.id}")] for x in ms]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga",callback_data="nav:menu"),InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")])
    await m.answer(f"💸 Pul chiqarish\nBalans: {u.balance} GC\n\nTo‘lov turini tanlang:",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@r.callback_query(F.data.startswith("wm:"))
async def choose_method(c:CallbackQuery,state:FSMContext):
    mid=int(c.data.split(":")[1])
    async with Session() as s:pm=await s.get(PaymentMethod,mid)
    if not pm or not pm.active:await c.answer("Mavjud emas.",show_alert=True);return
    await state.update_data(method_id=mid);await state.set_state(W.coins)
    await c.message.edit_text(f"💳 {pm.name}\n{pm.description or ''}\n1 GC = {pm.rate:g} {pm.currency}\nMin: {pm.min_amount} GC | Max: {pm.max_amount} GC\n\nNechta GidroCoin yechasiz?",reply_markup=nav("withdraw"));await c.answer()

@r.message(W.coins)
async def coins(m:Message,state:FSMContext):
    try:n=int(m.text)
    except:await m.answer("Faqat butun son kiriting.",reply_markup=nav("withdraw"));return
    d=await state.get_data()
    async with Session() as s:
        u=(await s.execute(select(User).where(User.tg_id==m.from_user.id))).scalar_one();pm=await s.get(PaymentMethod,d["method_id"])
        if n<pm.min_amount or n>pm.max_amount:await m.answer("Min/max limitga mos emas.");return
        if n>u.balance:await m.answer("Balansingiz yetarli emas.");return
    await state.update_data(coins=n);await state.set_state(W.destination)
    await m.answer("To‘lov manzilini yuboring:",reply_markup=nav("withdraw"))

@r.message(W.destination)
async def destination(m:Message,state:FSMContext):
    dest=m.text.strip();d=await state.get_data();n=int(d["coins"])
    dh=hashlib.sha256(dest.lower().encode()).hexdigest()
    async with Session() as s:
        u=(await s.execute(select(User).where(User.tg_id==m.from_user.id))).scalar_one();pm=await s.get(PaymentMethod,d["method_id"])
        if n>u.balance:await m.answer("Balans yetarli emas.");return
        duplicate=(await s.execute(select(Withdrawal).where(Withdrawal.destination_hash==dh,Withdrawal.user_id!=u.id,Withdrawal.status.in_(["pending","approved"])))).scalars().first()
        if duplicate:s.add(FraudSignal(user_id=u.id,kind="shared_withdrawal",value=dh,score=80))
        u.balance-=n;p=n*float(pm.rate)
        w=Withdrawal(user_id=u.id,method_id=pm.id,coins=n,currency=pm.currency,rate=pm.rate,payout=p,destination=dest,destination_hash=dh);s.add(w);await s.commit()
        wid=w.id
    await state.clear()
    await m.answer(f"✅ #{wid} ariza qabul qilindi.\n{n} GC → {p:g} {pm.currency}",reply_markup=nav())
    for aid in settings.ADMIN_IDS:
        try:await m.bot.send_message(aid,f"💸 TO‘LOV #{wid}\n👤 {m.from_user.full_name}\nID: {m.from_user.id}\n💰 {n} GC\n💳 {pm.name}\n💵 {p:g} {pm.currency}\n🔐 ****{dest[-4:]}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash",callback_data=f"pay:ok:{wid}"),InlineKeyboardButton(text="❌ Bekor qilish",callback_data=f"pay:no:{wid}")]]))
        except:pass

@r.callback_query(F.data.startswith("pay:"))
async def process_payment(c:CallbackQuery):
    if not is_admin(c):return
    _,act,wid=c.data.split(":");wid=int(wid)
    async with Session() as s:
        w=await s.get(Withdrawal,wid)
        if not w or w.status!="pending":await c.answer("Bu to‘lov allaqachon qayta ishlangan.",show_alert=True);return
        u=await s.get(User,w.user_id)
        if act=="ok":
            w.status="approved";w.processed_at=datetime.now(timezone.utc);u.withdrawn+=w.coins;await s.commit()
            await c.message.edit_text(c.message.text+"\n\n✅ TASDIQLANDI")
            await c.bot.send_message(u.tg_id,f"✅ #{wid} to‘lovingiz tasdiqlandi: {w.payout:g} {w.currency}")
            if settings.PAYMENT_CHANNEL_ID:
                try:await c.bot.send_message(settings.PAYMENT_CHANNEL_ID,f"💳 TO‘LOV PROOF\n\n💰 {w.coins} GidroCoin\n💵 {w.payout:g} {w.currency}\n📅 {w.processed_at:%Y-%m-%d %H:%M}\n🔐 ****{w.destination[-4:]}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💰 Pul ishlash",callback_data="nav:earn"),InlineKeyboardButton(text="👤 Foydalanuvchi",url=f"tg://user?id={u.tg_id}")]]))
                except:pass
        else:
            w.status="cancelled";w.processed_at=datetime.now(timezone.utc);u.balance+=w.coins;await s.commit()
            await c.message.edit_text(c.message.text+"\n\n❌ BEKOR QILINDI");await c.bot.send_message(u.tg_id,f"❌ #{wid} bekor qilindi. {w.coins} GC qaytarildi.")
    await c.answer()

@r.message(F.text=="🏆 Top reyting")
async def ratings(m:Message):
    if not await ensure_gate(m):return
    await m.answer("🏆 Top reyting",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Eng ko‘p ishlagan",callback_data="rank:earned:all"),InlineKeyboardButton(text="💸 Eng ko‘p yechgan",callback_data="rank:withdrawn:all")],
        [InlineKeyboardButton(text="📅 Bugun",callback_data="period:day"),InlineKeyboardButton(text="🗓 Shu oy",callback_data="period:month"),InlineKeyboardButton(text="♾ Umumiy",callback_data="period:all")],
        [InlineKeyboardButton(text="⬅️ Orqaga",callback_data="nav:menu"),InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")]]))

@r.callback_query(F.data.startswith("period:"))
async def period(c:CallbackQuery):
    p=c.data.split(":")[1]
    await c.message.edit_text("🏆 Reyting turi:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Eng ko‘p ishlagan",callback_data=f"rank:earned:{p}"),InlineKeyboardButton(text="💸 Eng ko‘p yechgan",callback_data=f"rank:withdrawn:{p}")],
        [InlineKeyboardButton(text="⬅️ Orqaga",callback_data="nav:menu"),InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")]]));await c.answer()

@r.callback_query(F.data.startswith("rank:"))
async def rank(c:CallbackQuery):
    _,kind,period=c.data.split(":");now=datetime.now(timezone.utc)
    async with Session() as s:
        if kind=="earned":
            if period=="day": q=select(User).order_by(desc(User.referral_earned)).limit(10)
            elif period=="month": q=select(User).order_by(desc(User.referral_earned)).limit(10)
            else:q=select(User).order_by(desc(User.referral_earned)).limit(10)
        else:q=select(User).order_by(desc(User.withdrawn)).limit(10)
        us=(await s.execute(q)).scalars().all()
    # Historical period requires event aggregation; current ranking uses cumulative values.
    title="💰 Eng ko‘p ishlaganlar" if kind=="earned" else "💸 Eng ko‘p yechganlar"
    text=f"🏆 {title} — {period}\n\n"+"\n".join(f"{i}. {u.first_name or 'Foydalanuvchi'} — {(u.referral_earned if kind=='earned' else u.withdrawn)} GC" for i,u in enumerate(us,1))
    await c.message.edit_text(text,reply_markup=nav());await c.answer()

# Admin
@r.message(Command("admin"))
async def admin_cmd(m:Message):
    if is_admin(m):await m.answer("⚙️ Admin panel",reply_markup=admin())

@r.callback_query(F.data=="adm:stats")
async def astats(c:CallbackQuery):
    if not is_admin(c):return
    async with Session() as s:
        users=await s.scalar(select(func.count(User.id)));bal=await s.scalar(select(func.coalesce(func.sum(User.balance),0)))
        refs=await s.scalar(select(func.coalesce(func.sum(User.accepted_referrals),0)))
        pending=await s.scalar(select(func.count(Withdrawal.id)).where(Withdrawal.status=="pending"))
        approved=await s.scalar(select(func.count(Withdrawal.id)).where(Withdrawal.status=="approved"))
        cancelled=await s.scalar(select(func.count(Withdrawal.id)).where(Withdrawal.status=="cancelled"))
        fraud=await s.scalar(select(func.count(FraudSignal.id)))
    await c.message.edit_text(f"📊 Statistika\n\n👥 Userlar: {users}\n👥 Qabul qilingan referral: {refs}\n💰 Balanslar: {bal} GC\n⏳ Pending: {pending}\n✅ Approved: {approved}\n❌ Cancelled: {cancelled}\n🛡 Fraud signal: {fraud}",reply_markup=nav("admin"))

@r.callback_query(F.data=="adm:ref")
async def aref(c:CallbackQuery):
    if not is_admin(c):return
    v=await setting("referral_reward","10")
    await c.message.edit_text(f"💰 Referral mukofoti: {v} GC\n\n/setreward 10",reply_markup=nav("admin"))
@r.message(Command("setreward"))
async def setreward(m:Message):
    if not is_admin(m):return
    try:v=int(m.text.split()[1]);assert v>=0
    except:await m.answer("/setreward 10");return
    async with Session() as s:x=await s.get(Setting,"referral_reward");x.value=str(v);await s.commit()
    await m.answer(f"Referral mukofoti {v} GC bo‘ldi.")

@r.callback_query(F.data=="adm:methods")
async def amethods(c:CallbackQuery):
    if not is_admin(c):return
    async with Session() as s:ms=(await s.execute(select(PaymentMethod))).scalars().all()
    rows=[[InlineKeyboardButton(text=f"{'🟢' if x.active else '🔴'} {x.name}",callback_data=f"m:view:{x.id}")] for x in ms]
    rows += [[InlineKeyboardButton(text="➕ Qo‘shish",callback_data="m:help")],[InlineKeyboardButton(text="⬅️ Orqaga",callback_data="nav:admin"),InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")]]
    await c.message.edit_text("💳 To‘lov turlari",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
@r.callback_query(F.data.startswith("m:view:"))
async def mview(c:CallbackQuery):
    if not is_admin(c):return
    mid=int(c.data.split(":")[2])
    async with Session() as s:x=await s.get(PaymentMethod,mid)
    await c.message.edit_text(f"💳 {x.name}\nID: {x.id}\nIzoh: {x.description or '-'}\nKurs: 1 GC = {x.rate:g} {x.currency}\nMin: {x.min_amount}\nMax: {x.max_amount}\nHolat: {x.active}\n\n/methodedit {x.id} NOM|IZOH|VALYUTA|KURS|MIN|MAX|1\n/methodtoggle {x.id}",reply_markup=nav("admin"))
@r.callback_query(F.data=="m:help")
async def mhelp(c:CallbackQuery):
    await c.message.edit_text("➕ To‘lov turi qo‘shish:\n/methodadd NOM|IZOH|VALYUTA|KURS|MIN|MAX",reply_markup=nav("admin"));await c.answer()
@r.message(Command("methodadd"))
async def methodadd(m:Message):
    if not is_admin(m):return
    try:
        a=m.text.split(maxsplit=1)[1].split("|");name,desc,curr,rate,mi,ma=a
        async with Session() as s:s.add(PaymentMethod(name=name,description=desc,currency=curr,rate=float(rate),min_amount=int(mi),max_amount=int(ma)));await s.commit()
        await m.answer("To‘lov turi qo‘shildi.")
    except:await m.answer("/methodadd NOM|IZOH|VALYUTA|KURS|MIN|MAX")
@r.message(Command("methodedit"))
async def methodedit(m:Message):
    if not is_admin(m):return
    try:
        p=m.text.split(maxsplit=2);xid=int(p[1]);name,desc,curr,rate,mi,ma,active=p[2].split("|")
        async with Session() as s:
            x=await s.get(PaymentMethod,xid);x.name=name;x.description=desc;x.currency=curr;x.rate=float(rate);x.min_amount=int(mi);x.max_amount=int(ma);x.active=bool(int(active));await s.commit()
        await m.answer("Saqlandi.")
    except:await m.answer("/methodedit ID NOM|IZOH|VALYUTA|KURS|MIN|MAX|1")
@r.message(Command("methodtoggle"))
async def methodtoggle(m:Message):
    if not is_admin(m):return
    try:
        xid=int(m.text.split()[1])
        async with Session() as s:x=await s.get(PaymentMethod,xid);x.active=not x.active;await s.commit()
        await m.answer("Holat o‘zgardi.")
    except:await m.answer("/methodtoggle ID")

@r.callback_query(F.data=="adm:payments")
async def apayments(c:CallbackQuery):
    if not is_admin(c):return
    await c.message.edit_text("💸 To‘lovlar",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Kutilayotgan",callback_data="plist:pending")],
        [InlineKeyboardButton(text="✅ Tasdiqlangan",callback_data="plist:approved")],
        [InlineKeyboardButton(text="❌ Bekor qilingan",callback_data="plist:cancelled")],
        [InlineKeyboardButton(text="⬅️ Orqaga",callback_data="nav:admin"),InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")]]))
@r.callback_query(F.data.startswith("plist:"))
async def plist(c:CallbackQuery):
    if not is_admin(c):return
    st=c.data.split(":")[1]
    async with Session() as s:ws=(await s.execute(select(Withdrawal).where(Withdrawal.status==st).order_by(desc(Withdrawal.id)).limit(50))).scalars().all()
    text=f"💸 {st}\n\n"+("\n".join(f"#{x.id} — {x.coins} GC → {x.payout:g} {x.currency}" for x in ws) or "Bo‘sh")
    await c.message.edit_text(text,reply_markup=nav("admin"));await c.answer()

@r.callback_query(F.data=="adm:users")
async def ausers(c:CallbackQuery):
    if not is_admin(c):return
    await c.message.edit_text("👥 Foydalanuvchilar\n\n/user ID yoki Telegram ID\n/useradd ID AMOUNT\n/userban ID\n/userrefblock ID\n/usermsg ID MATN",reply_markup=nav("admin"))
@r.message(Command("user"))
async def userfind(m:Message):
    if not is_admin(m):return
    try:i=int(m.text.split()[1])
    except:await m.answer("/user ID");return
    async with Session() as s:u=(await s.execute(select(User).where(or_(User.id==i,User.tg_id==i)))).scalar_one_or_none()
    if not u:await m.answer("Topilmadi.");return
    await m.answer(f"👤 {u.first_name}\nBot ID: {u.id}\nTG ID: {u.tg_id}\nBalans: {u.balance} GC\nReferral: {u.referrals_count}\nQabul: {u.accepted_referrals}\nYechilgan: {u.withdrawn} GC\nBan: {u.banned}\nReferral block: {u.referral_blocked}")
@r.message(Command("useradd"))
async def useradd(m:Message):
    if not is_admin(m):return
    try:i,a=m.text.split()[1:3];i=int(i);a=int(a)
    except:await m.answer("/useradd ID AMOUNT");return
    async with Session() as s:u=(await s.execute(select(User).where(or_(User.id==i,User.tg_id==i)))).scalar_one();u.balance+=a;await s.commit()
    await m.answer("Balans o‘zgartirildi.")
@r.message(Command("userban"))
async def userban(m:Message):
    if not is_admin(m):return
    i=int(m.text.split()[1])
    async with Session() as s:u=(await s.execute(select(User).where(or_(User.id==i,User.tg_id==i)))).scalar_one();u.banned=not u.banned;await s.commit()
    await m.answer("Ban holati o‘zgartirildi.")
@r.message(Command("userrefblock"))
async def userrefblock(m:Message):
    if not is_admin(m):return
    i=int(m.text.split()[1])
    async with Session() as s:u=(await s.execute(select(User).where(or_(User.id==i,User.tg_id==i)))).scalar_one();u.referral_blocked=not u.referral_blocked;await s.commit()
    await m.answer("Referral blok holati o‘zgartirildi.")
@r.message(Command("usermsg"))
async def usermsg(m:Message):
    if not is_admin(m):return
    try:i=int(m.text.split()[1]);txt=m.text.split(maxsplit=2)[2]
    except:await m.answer("/usermsg ID MATN");return
    async with Session() as s:u=(await s.execute(select(User).where(or_(User.id==i,User.tg_id==i)))).scalar_one()
    await m.bot.send_message(u.tg_id,txt);await m.answer("Yuborildi.")

@r.callback_query(F.data=="adm:broadcast")
async def broadcast_help(c:CallbackQuery):
    if not is_admin(c):return
    await c.message.edit_text("📣 Broadcast\n\nBiror xabarga reply qilib:\n/broadcast — copy\n/broadcast_forward — forward",reply_markup=nav("admin"))
async def send_broadcast(m,forward):
    if not is_admin(m) or not m.reply_to_message:return
    async with Session() as s:us=(await s.execute(select(User).where(User.banned==False))).scalars().all()
    ok=bad=0
    for u in us:
        try:
            if forward:await m.bot.forward_message(u.tg_id,m.chat.id,m.reply_to_message.message_id)
            else:await m.bot.copy_message(u.tg_id,m.chat.id,m.reply_to_message.message_id)
            ok+=1
        except:bad+=1
        await asyncio.sleep(.03)
    await m.answer(f"Tarqatildi: {ok}\nXato: {bad}")
@r.message(Command("broadcast"))
async def broadcast(m:Message):await send_broadcast(m,False)
@r.message(Command("broadcast_forward"))
async def broadcastf(m:Message):await send_broadcast(m,True)

@r.callback_query(F.data=="adm:channels")
async def achannels(c:CallbackQuery):
    if not is_admin(c):return
    await c.message.edit_text("📢 Kanallar",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Majburiy kanallar",callback_data="channels:required")],
        [InlineKeyboardButton(text="💳 To‘lovlar kanali",callback_data="channels:payment")],
        [InlineKeyboardButton(text="⬅️ Orqaga",callback_data="nav:admin"),InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")]]))
@r.callback_query(F.data.startswith("channels:"))
async def channels_list(c:CallbackQuery):
    if not is_admin(c):return
    kind=c.data.split(":")[1]
    async with Session() as s:cs=(await s.execute(select(Channel).where(Channel.kind==kind))).scalars().all()
    text=("🔒 Majburiy" if kind=="required" else "💳 To‘lov")+"\n\n"+("\n".join(f"{x.id}. {x.title} — {x.chat_id}" for x in cs) or "Bo‘sh")
    await c.message.edit_text(text+f"\n\nQo‘shish: /channeladd {kind} CHAT_ID | NOM | LINK\nO‘chirish: /channelremove {kind} ID",reply_markup=nav("admin"))
@r.message(Command("channeladd"))
async def channeladd(m:Message):
    if not is_admin(m):return
    try:
        kind=m.text.split(maxsplit=2)[1];chat,title,link=[x.strip() for x in m.text.split(maxsplit=2)[2].split("|")]
        info=await m.bot.get_chat(int(chat))
        async with Session() as s:s.add(Channel(chat_id=int(chat),title=title,username=info.username,invite_link=link or None,kind=kind));await s.commit()
        await m.answer("Kanal qo‘shildi.")
    except:await m.answer("/channeladd required -100... | NOM | https://t.me/...")
@r.message(Command("channelremove"))
async def channelremove(m:Message):
    if not is_admin(m):return
    try:kind,i=m.text.split()[1:3];i=int(i)
    except:await m.answer("/channelremove required ID");return
    async with Session() as s:x=await s.get(Channel,i);await s.delete(x);await s.commit()
    await m.answer("O‘chirildi.")

@r.callback_query(F.data=="adm:fraud")
async def afraud(c:CallbackQuery):
    if not is_admin(c):return
    async with Session() as s:fs=(await s.execute(select(FraudSignal).order_by(desc(FraudSignal.score),desc(FraudSignal.id)).limit(50))).scalars().all()
    text="🛡 Anti-Fraud\n\n"+("\n".join(f"#{x.id} user={x.user_id} {x.kind} +{x.score}" for x in fs) or "Signal yo‘q")
    await c.message.edit_text(text,reply_markup=nav("admin"))
@r.callback_query(F.data=="adm:ratings")
async def aratings(c:CallbackQuery):
    if is_admin(c):await c.message.edit_text("🏆 Reytinglar: foydalanuvchi earned/withdrawn ko‘rsatkichlari.",reply_markup=nav("admin"))

@r.callback_query(F.data=="nav:menu")
async def nmenu(c:CallbackQuery,state:FSMContext):
    await state.clear();await c.message.answer("Bosh menyu:",reply_markup=menu());await c.answer()
@r.callback_query(F.data=="nav:admin")
async def nadmin(c:CallbackQuery):
    if is_admin(c):await c.message.edit_text("⚙️ Admin panel",reply_markup=admin())
    await c.answer()
@r.callback_query(F.data=="nav:withdraw")
async def nwithdraw(c:CallbackQuery):
    async with Session() as s:ms=(await s.execute(select(PaymentMethod).where(PaymentMethod.active==True))).scalars().all()
    await c.message.edit_text("💸 To‘lov turini tanlang:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x.name,callback_data=f"wm:{x.id}")] for x in ms]+[[InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")]]));await c.answer()
@r.callback_query(F.data=="nav:earn")
async def nearn(c:CallbackQuery):
    u=await get_user(c.from_user.id);me=await c.bot.me();reward=await setting("referral_reward","10")
    await c.message.answer(f"💰 1 referral = {reward} GC\n\n🔗 https://t.me/{me.username}?start=ref_{u.tg_id}",reply_markup=nav());await c.answer()

def setup(dp:Dispatcher):dp.include_router(r)
