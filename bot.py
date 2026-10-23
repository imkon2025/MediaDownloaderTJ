
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

MAX_SIZE = 45 * 1024 * 1024  # 45 MB


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Салом! Ба MediaDownloaderTJ хуш омадӣ!\n\n"
        "🔗 Линки видеоро фирист.\n"
        "📥 Ман кӯшиш мекунам онро зеркашӣ кунам.\n\n"
        "⚠️ На ҳамаи сайтҳо дастгирӣ мешаванд."
    )


def download_media(url: str, folder: str) -> Path:
    options = {
        "format": "best[filesize<45M]/best[height<=720]/best",
        "outtmpl": str(Path(folder) / "%(title).80s.%(ext)s"),
        "noplaylist": True,
        "max_filesize": MAX_SIZE,
        "socket_timeout": 30,
        "retries": 2,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    files = [
        p for p in Path(folder).iterdir()
        if p.is_file() and not p.name.endswith((".part", ".ytdl"))
    ]

    if not files:
        raise RuntimeError("Файли зеркашишуда ёфт нашуд.")

    result = max(files, key=lambda p: p.stat().st_size)

    if result.stat().st_size > MAX_SIZE:
        raise RuntimeError("Файл аз 45 MB калон аст.")

    return result


async def handle_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.message
    url = message.text.strip()

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        await message.reply_text("❌ Линки дурусти https:// ё http:// фирист.")
        return

    # Аз URL-ҳои дохилӣ ва маҳаллӣ эҳтиёт мекунем.
    host = parsed.hostname.lower()
    if (
        host == "localhost"
        or host.endswith(".localhost")
        or host.endswith(".local")
        or host.startswith(("127.", "10.", "192.168."))
    ):
        await message.reply_text("❌ Ин навъи линк қабул намешавад.")
        return

    status = await message.reply_text("⏳ Линк қабул шуд. Зеркашӣ оғоз мешавад...")

    try:
        with tempfile.TemporaryDirectory(prefix="media_") as folder:
            file_path = await asyncio.to_thread(download_media, url, folder)

            await status.edit_text("📤 Файл тайёр шуд. Ба Telegram мефиристам...")

            with file_path.open("rb") as media:
                if file_path.suffix.lower() in (".mp4", ".m4v", ".mov"):
                    await message.reply_video(
                        video=media,
                        caption="✅ Зеркашӣ анҷом ёфт!",
                        read_timeout=120,
                        write_timeout=120,
                        connect_timeout=30,
                    )
                else:
                    await message.reply_document(
                        document=media,
                        caption="✅ Файл омода аст!",
                        read_timeout=120,
                        write_timeout=120,
                        connect_timeout=30,
                    )

        await status.delete()

    except Exception:
        logging.exception("Download failed")
        await status.edit_text(
            "❌ Зеркашӣ нашуд.\n\n"
            "Сабаб метавонад линк, маҳдудияти сайт, "
            "пайвасти интернет ё андозаи файл бошад.\n"
            "Линки дигарро санҷ."
        )


async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN ёфт нашуд. Файли .env-ро санҷ.")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)
    )

    print("🤖 MediaDownloaderTJ фаъол аст!")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
