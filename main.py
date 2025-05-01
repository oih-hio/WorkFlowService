from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os

# --- Google Sheets Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1Ae53u5fVhUgFYDi5FrJQJZeWjnh4piLpXybOG26Lv2c/edit").sheet1

# --- Стани ---
SELECT_ENGINEER, GET_IMEI, GET_COMMENT = range(3)
GET_IMEI_TO_UPDATE, GET_REPAIR_RESULT = range(3, 5)
GET_HISTORY_IMEI = 10

# --- Список інженерів ---
ENGINEERS = {
    "dyphny": "Dyphny",
    "bosayt1": "Bosayt1",
    "Kepasa_Paradox": "Kepasa",
    "Okeksii_Hrynashchuk": "Олексій (коорд.)",
    "@an8tframe": "@an8tframe",
    "graid1988": "Грайд (коорд.)"
}

# --- Команди бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот активний. Напишіть /repair, щоб створити новий запис.")

# --- Додавання нового запису ---
async def new_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(name, callback_data=username)] for username, name in ENGINEERS.items()]
    await update.message.reply_text("Оберіть інженера:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_ENGINEER

async def select_engineer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['engineer'] = query.data
    await query.edit_message_text("Надішліть IMEI (можна сканером):")
    return GET_IMEI

async def get_imei(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['imei'] = update.message.text.strip()
    await update.message.reply_text("Введіть коментар (або '-' якщо не потрібно):")
    return GET_COMMENT

async def get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text.strip()
    engineer = context.user_data['engineer']
    imei = context.user_data['imei']
    timestamp = (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

    sheet.append_row([engineer, imei, comment, timestamp])
    await update.message.reply_text(f"✅ Запис додано:\n👨‍🔧 Інженер: {engineer}\n📱 IMEI: {imei}\n📝 Коментар: {comment}")
    return ConversationHandler.END

# --- Оновлення запису після ремонту з вибором варіанту ---
async def repair_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Введіть IMEI пристрою, який ви щойно відремонтували:")
    return GET_IMEI_TO_UPDATE

async def receive_imei(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['imei_to_update'] = update.message.text.strip()

    options = [
        "МС_Переклейка скла дисплея рівень 0, шт",
        "МС_Переклейка скла дисплея рівень 1, шт",
        "МС_Переклейка скла дисплея рівень 2, шт",
        "МС_Переклейка скла дисплея рівень 3, шт",
        "МС_Переклейка скла дисплея рівень 4, шт",
        "МС_Послуга з діагностики обладнання рівень 0, шт",
        "МС_Послуга з діагностики обладнання рівень 1, шт",
        "МС_Послуга з ремонту обладнання рівень 0A, шт",
        "МС_Послуга з ремонту обладнання рівень 0, шт",
        "МС_Послуга з ремонту обладнання рівень 1, шт",
        "МС_Послуга з ремонту обладнання рівень 2, шт",
        "НБ_Послуга з ремонту обладнання рівень 0, шт",
        "НБ_Послуга з ремонту обладнання рівень 1, шт"
    ]

    keyboard = [
        [InlineKeyboardButton(text=option, callback_data=f"repair:{i}")]
        for i, option in enumerate(options)
    ]
    context.user_data['repair_options'] = options

    await update.message.reply_text(
        "🛠️ Оберіть тип виконаного ремонту:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GET_REPAIR_RESULT

async def receive_repair_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    index = int(query.data.split(":")[1])
    repair_text = context.user_data['repair_options'][index]
    imei = context.user_data['imei_to_update']

    records = sheet.get_all_records()
    for i, row in enumerate(records):
        if str(row["IMEI"]).strip() == imei:
            sheet.update_cell(i + 2, 5, repair_text)
            await query.edit_message_text(
                f"✅ Оновлено для IMEI {imei}:\n🔧 Ремонт: {repair_text}"
            )
            return ConversationHandler.END

    await query.edit_message_text(f"⚠️ IMEI {imei} не знайдено в таблиці.")
    return ConversationHandler.END

# --- Перегляд історії за IMEI ---
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Введіть IMEI, для якого потрібна історія:")
    return GET_HISTORY_IMEI

async def send_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    imei = update.message.text.strip()
    records = sheet.get_all_values()
    header = records[0]
    rows = records[1:]
    matching = [row for row in rows if row[1].strip() == imei]

    if not matching:
        await update.message.reply_text("⚠️ Записів з таким IMEI не знайдено.")
        return ConversationHandler.END

    text = f"🔎 Історія для IMEI: {imei}\n\n"
    for row in matching:
        engineer = row[0]
        comment = row[2]
        time = row[3]
        result = row[4] if len(row) > 4 else "–"
        text += f"📅 {time}\n👨‍🔧 {engineer}\n📝 {comment}\n🔧 {result}\n\n"

    await update.message.reply_text(text)
    return ConversationHandler.END

# --- Скасування ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Операцію скасовано.")
    return ConversationHandler.END

# --- Запуск ---
def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("repair", new_task)],
        states={
            SELECT_ENGINEER: [CallbackQueryHandler(select_engineer)],
            GET_IMEI: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_imei)],
            GET_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_comment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True
    )

    done_conv = ConversationHandler(
        entry_points=[CommandHandler("repair_done", repair_done)],
        states={
            GET_IMEI_TO_UPDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_imei)],
            GET_REPAIR_RESULT: [CallbackQueryHandler(receive_repair_result)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True
    )

    history_conv = ConversationHandler(
        entry_points=[CommandHandler("history", history)],
        states={
            GET_HISTORY_IMEI: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_history)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(done_conv)
    app.add_handler(history_conv)

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
