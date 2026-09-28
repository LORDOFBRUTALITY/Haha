import json
import os
import uuid
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ============== AYARLAR ==============
BOT_TOKEN = "8990954740:AAHBTlF6hKOSVub59dh3KjjywGvpN5c-J6s"
API_KEY = "ak_WL9qgJQrxJZe9YT_FUYzNJeOkfS0KnknOlAnLXfKOfs"
AI_API_URL = "https://api.anthropic.com/v1/messages"
AI_MODEL = "claude-sonnet-4-5"
DATA_FILE = "sohbetler.json"
# =====================================


# ============== VERİ YÖNETİMİ ==============
def verileri_yukle():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def verileri_kaydet(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def kullanici_verisi(user_id):
    data = verileri_yukle()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {}
    return data, data[uid]
# ============================================


# ============== AI FONKSİYONU (Anthropic) ==============
async def ai_cevap(messages):
    ai_messages = [m for m in messages if m["role"] in ("user", "assistant")]

    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": AI_MODEL,
        "max_tokens": 4000,
        "system": "Sen yardımcı bir asistansın. Türkçe cevap ver.",
        "messages": ai_messages
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(AI_API_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            result = resp.json()
            return result["content"][0]["text"]
        else:
            return f"❌ AI hatası (Kod {resp.status_code}): {resp.text}"


# ============== KOMUTLAR ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Sohbet Botuna Hoş Geldin!**\n\n"
        "📌 **Komutlar:**\n"
        "• `/yenisohbet` - Yeni sohbet oluştur\n"
        "• `/sohbetler` - Sohbetleri listele\n"
        "• `/sohbet` - Bir sohbet seç\n"
        "• `/sohbet sil` - Sohbet sil\n\n"
        "💡 Bir sohbet seçtikten sonra direkt mesaj yazarak devam edebilirsin!",
        parse_mode="Markdown"
    )


async def yenisohbet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bekleme_modu"] = "yeni_sohbet"
    await update.message.reply_text(
        "📝 Yeni sohbetin için bir **isim** yaz:",
        parse_mode="Markdown"
    )


async def sohbetler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data, user_data = kullanici_verisi(update.effective_user.id)

    if not user_data:
        await update.message.reply_text("📭 Henüz hiç sohbetin yok! `/yenisohbet` ile oluştur.")
        return

    keyboard = []
    for chat_id, chat in user_data.items():
        keyboard.append([InlineKeyboardButton(
            f"💬 {chat['isim']}",
            callback_data=f"sec:{chat_id}:normal"
        )])
    keyboard.append([InlineKeyboardButton("❌ Kapat", callback_data="kapat")])

    await update.message.reply_text(
        "📋 **Sohbetlerin:**\n\nSeçmek için tıkla:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def sohbet_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if args and args[0].lower() == "sil":
        data, user_data = kullanici_verisi(update.effective_user.id)

        if not user_data:
            await update.message.reply_text("📭 Silinecek sohbet yok!")
            return

        keyboard = []
        for chat_id, chat in user_data.items():
            keyboard.append([InlineKeyboardButton(
                f"🗑 {chat['isim']}",
                callback_data=f"sec:{chat_id}:sil"
            )])
        keyboard.append([InlineKeyboardButton("❌ Vazgeç", callback_data="kapat")])

        await update.message.reply_text(
            "🗑 **Silmek istediğin sohbeti seç:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await sohbetler(update, context)


# ============== INLINE KEYBOARD HANDLER ==============
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "kapat":
        await query.message.delete()
        return

    _, chat_id, action = query.data.split(":")

    if action == "sil":
        data, user_data = kullanici_verisi(query.from_user.id)
        if chat_id in user_data:
            sohbet_adi = user_data[chat_id]["isim"]
            del user_data[chat_id]

            # Aktif sohbet silindiyse temizle
            if context.user_data.get("aktif_sohbet") == chat_id:
                context.user_data["aktif_sohbet"] = None
                context.user_data["aktif_sohbet_adi"] = None

            verileri_kaydet(data)
            await query.edit_message_text(f"✅ **'{sohbet_adi}'** sohbeti silindi!", parse_mode="Markdown")

    elif action == "normal":
        data, user_data = kullanici_verisi(query.from_user.id)
        if chat_id in user_data:
            sohbet_adi = user_data[chat_id]["isim"]
            context.user_data["aktif_sohbet"] = chat_id
            context.user_data["aktif_sohbet_adi"] = sohbet_adi

            mesaj_sayisi = len(user_data[chat_id]["mesajlar"])
            await query.edit_message_text(
                f"✅ **'{sohbet_adi}'** sohbeti seçildi!\n\n"
                f"📊 {mesaj_sayisi // 2} mesaj geçmişi var.\n"
                f"💬 Şimdi mesaj yazarak devam edebilirsin!",
                parse_mode="Markdown"
            )


# ============== MESAJ HANDLER ==============
async def mesaj_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    data, user_data = kullanici_verisi(update.effective_user.id)

    # Yeni sohbet ismi bekleniyorsa
    if context.user_data.get("bekleme_modu") == "yeni_sohbet":
        context.user_data["bekleme_modu"] = None
        chat_id = str(uuid.uuid4())[:8]
        user_data[chat_id] = {
            "isim": user_text,
            "mesajlar": []
        }

        # Yeni sohbeti aktif yap
        context.user_data["aktif_sohbet"] = chat_id
        context.user_data["aktif_sohbet_adi"] = user_text

        verileri_kaydet(data)
        await update.message.reply_text(
            f"✅ **'{user_text}'** sohbeti oluşturuldu ve aktif edildi!\n"
            f"💬 Şimdi mesaj yazarak sohbete başlayabilirsin!",
            parse_mode="Markdown"
        )
        return

    # Aktif sohbet yoksa uyar
    aktif = context.user_data.get("aktif_sohbet")
    if not aktif or aktif not in user_data:
        await update.message.reply_text(
            "⚠️ Önce bir sohbet seç!\n\n"
            "• `/yenisohbet` - Yeni oluştur\n"
            "• `/sohbet` - Var olanı seç",
            parse_mode="Markdown"
        )
        return

    # Mesajı sohbete ekle
    user_data[aktif]["mesajlar"].append({"role": "user", "content": user_text})
    verileri_kaydet(data)

    # AI'dan cevap al
    bekleme = await update.message.reply_text("🤔 Düşünüyorum...")

    sohbet_mesajlari = user_data[aktif]["mesajlar"].copy()
    cevap = await ai_cevap(sohbet_mesajlari)

    # AI cevabını sohbete ekle
    data, user_data = kullanici_verisi(update.effective_user.id)
    user_data[aktif]["mesajlar"].append({"role": "assistant", "content": cevap})
    verileri_kaydet(data)

    await bekleme.edit_text(cevap)


# ============== MAIN ==============
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yenisohbet", yenisohbet))
    app.add_handler(CommandHandler("sohbetler", sohbetler))
    app.add_handler(CommandHandler("sohbet", sohbet_sec))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_al))

    print("✅ Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
