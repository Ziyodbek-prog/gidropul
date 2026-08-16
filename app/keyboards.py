from aiogram.types import ReplyKeyboardMarkup,KeyboardButton,InlineKeyboardMarkup,InlineKeyboardButton

def menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💰 Pul ishlash"),KeyboardButton(text="💸 Pul chiqarish")],
        [KeyboardButton(text="👤 Mening profilim")],
        [KeyboardButton(text="🏆 Top reyting"),KeyboardButton(text="💳 To‘lovlar kanali")],
    ],resize_keyboard=True)

def nav(back="menu"):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Orqaga",callback_data=f"nav:{back}"),
        InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")]])

def admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanallar",callback_data="adm:channels")],
        [InlineKeyboardButton(text="📊 Statistika",callback_data="adm:stats")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar",callback_data="adm:users")],
        [InlineKeyboardButton(text="📣 Xabar tarqatish",callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="💸 Barcha to‘lovlar",callback_data="adm:payments")],
        [InlineKeyboardButton(text="💰 Referral sozlamalari",callback_data="adm:ref")],
        [InlineKeyboardButton(text="💳 To‘lov turlari",callback_data="adm:methods")],
        [InlineKeyboardButton(text="🏆 Reytinglar",callback_data="adm:ratings")],
        [InlineKeyboardButton(text="🛡 Anti-Fraud",callback_data="adm:fraud")],
        [InlineKeyboardButton(text="🏠 Bosh menyu",callback_data="nav:menu")]])
