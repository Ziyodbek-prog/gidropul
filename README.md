# HydroCoin Bot

GitHub → Render Free → Neon PostgreSQL → UptimeRobot uchun tayyor loyiha.

## Deploy
1. ZIP'ni GitHub repositoryga yuklang.
2. Neon PostgreSQL yarating va `DATABASE_URL` oling.
3. Render'da repositorydan Web Service yarating.
4. Environment Variables:
   - `BOT_TOKEN`
   - `DATABASE_URL`
   - `ADMIN_IDS`
   - `WEBHOOK_URL`
   - `PAYMENT_CHANNEL_ID` (ixtiyoriy)
   - `WEBAPP_SECRET`
5. Deploy qiling.
6. Webhook:
   `https://api.telegram.org/botTOKEN/setWebhook?url=https://SERVICE.onrender.com/webhook`
7. UptimeRobot:
   `https://SERVICE.onrender.com/health`

## Admin
`/admin`

Asosiy buyruqlar:
- `/setreward 10`
- `/methodadd NOM|IZOH|VALYUTA|KURS|MIN|MAX`
- `/methodedit ID NOM|IZOH|VALYUTA|KURS|MIN|MAX|1`
- `/methodtoggle ID`
- `/user ID`
- `/useradd ID AMOUNT`
- `/userban ID`
- `/userrefblock ID`
- `/usermsg ID MATN`
- `/broadcast` — xabarga reply qilib
- `/broadcast_forward` — xabarga reply qilib
- `/channeladd required CHAT_ID | NOM | LINK`
- `/channeladd payment CHAT_ID | NOM | LINK`
- `/channelremove required ID`
- `/channelremove payment ID`

## WebApp va anti-fraud
Foydalanuvchi telefonini tasdiqlagandan keyin bir martalik WebApp session o'tadi.
Server:
- tokenni hash qilib saqlaydi;
- tokenni bir marta ishlatishga ruxsat beradi;
- Telegram WebApp `initData` HMAC imzosini Bot Token orqali tekshiradi;
- token egasi bilan Telegram ID mosligini tekshiradi;
- duplicate telefon signalini qayd qiladi;
- boshqa account bilan bir xil withdrawal destination hash bo'lsa signal beradi.

Bu qurilmaning barcha Telegram accountlarini aniqlash kafolati emas. Telegram bot API bunday ma'lumotni bermaydi.

## Muhim Telegram sozlamalari
Majburiy kanal/guruhda botga membership tekshirish uchun kerakli administrator huquqlarini bering.
To'lov proof kanalida bot xabar yubora olishi kerak.

## Render Free
Bot webhook rejimida ishlaydi. `/health` endpoint UptimeRobot monitoringi uchun bor. UptimeRobot'ni botni sun'iy ravishda cheksiz uptime qilish kafolati deb qabul qilmang; Render Free resurslari va platforma qoidalari o'zgarishi mumkin.
