from datetime import datetime, timezone
from sqlalchemy import BigInteger,Boolean,DateTime,ForeignKey,Integer,String,Text,Numeric,UniqueConstraint
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker,AsyncSession
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column
from .config import settings

url=settings.DATABASE_URL
if url.startswith("postgres://"): url=url.replace("postgres://","postgresql+asyncpg://",1)
elif url.startswith("postgresql://"): url=url.replace("postgresql://","postgresql+asyncpg://",1)

# asyncpg does not accept libpq's sslmode/channel_binding keyword arguments.
# Render/Neon URLs often contain them, so normalize the URL before SQLAlchemy uses it.
_parts=urlsplit(url)
_q=parse_qsl(_parts.query,keep_blank_values=True)
_q=[(k,v) for k,v in _q if k not in {"sslmode","channel_binding"}]
url=urlunsplit((_parts.scheme,_parts.netloc,_parts.path,urlencode(_q),_parts.fragment))
connect_args={"ssl": True} if "sslmode=require" in settings.DATABASE_URL else {}
engine=create_async_engine(url,pool_pre_ping=True,pool_recycle=300,pool_size=3,max_overflow=2,connect_args=connect_args)
Session=async_sessionmaker(engine,expire_on_commit=False,class_=AsyncSession)
def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass

class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    tg_id:Mapped[int]=mapped_column(BigInteger,unique=True,index=True)
    username:Mapped[str|None]=mapped_column(String(255))
    first_name:Mapped[str|None]=mapped_column(String(255))
    phone:Mapped[str|None]=mapped_column(String(32),index=True)
    balance:Mapped[int]=mapped_column(BigInteger,default=0)
    referrals_count:Mapped[int]=mapped_column(Integer,default=0)
    accepted_referrals:Mapped[int]=mapped_column(Integer,default=0)
    referral_earned:Mapped[int]=mapped_column(BigInteger,default=0)
    withdrawn:Mapped[int]=mapped_column(BigInteger,default=0)
    referral_blocked:Mapped[bool]=mapped_column(Boolean,default=False)
    banned:Mapped[bool]=mapped_column(Boolean,default=False)
    verified:Mapped[bool]=mapped_column(Boolean,default=False)
    web_verified:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Referral(Base):
    __tablename__="referrals"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    inviter_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    invited_id:Mapped[int]=mapped_column(ForeignKey("users.id"),unique=True)
    accepted:Mapped[bool]=mapped_column(Boolean,default=False)
    rewarded:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Setting(Base):
    __tablename__="settings"
    key:Mapped[str]=mapped_column(String(100),primary_key=True)
    value:Mapped[str]=mapped_column(Text)

class PaymentMethod(Base):
    __tablename__="payment_methods"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    name:Mapped[str]=mapped_column(String(100))
    description:Mapped[str|None]=mapped_column(Text)
    currency:Mapped[str]=mapped_column(String(20),default="UZS")
    rate:Mapped[float]=mapped_column(Numeric(18,4),default=1)
    min_amount:Mapped[int]=mapped_column(BigInteger,default=1)
    max_amount:Mapped[int]=mapped_column(BigInteger,default=10**9)
    active:Mapped[bool]=mapped_column(Boolean,default=True)

class Channel(Base):
    __tablename__="channels"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    chat_id:Mapped[int]=mapped_column(BigInteger,unique=True)
    title:Mapped[str]=mapped_column(String(255))
    username:Mapped[str|None]=mapped_column(String(255))
    invite_link:Mapped[str|None]=mapped_column(Text)
    kind:Mapped[str]=mapped_column(String(20),default="required") # required/payment
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Withdrawal(Base):
    __tablename__="withdrawals"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    method_id:Mapped[int]=mapped_column(ForeignKey("payment_methods.id"))
    coins:Mapped[int]=mapped_column(BigInteger)
    currency:Mapped[str]=mapped_column(String(20))
    rate:Mapped[float]=mapped_column(Numeric(18,4))
    payout:Mapped[float]=mapped_column(Numeric(18,4))
    destination:Mapped[str]=mapped_column(Text)
    destination_hash:Mapped[str]=mapped_column(String(64),index=True)
    status:Mapped[str]=mapped_column(String(20),default="pending",index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    processed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class WebSession(Base):
    __tablename__="web_sessions"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    used:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    used_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class FraudSignal(Base):
    __tablename__="fraud_signals"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    kind:Mapped[str]=mapped_column(String(80))
    value:Mapped[str]=mapped_column(Text)
    score:Mapped[int]=mapped_column(Integer,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Event(Base):
    __tablename__="events"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    kind:Mapped[str]=mapped_column(String(80),index=True)
    value:Mapped[int]=mapped_column(BigInteger,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

async def init_db():
    async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
    async with Session() as s:
        defaults={"referral_reward":"10","payment_channel_link":""}
        for k,v in defaults.items():
            if await s.get(Setting,k) is None:s.add(Setting(key=k,value=v))
        await s.commit()
