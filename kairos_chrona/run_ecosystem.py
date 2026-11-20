import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import asyncio
import os
import traceback
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

async def start_kairos():
    while True:
        try:
            print("⚡️ Starting Kairos bot...")
            import kairos_bot
            await kairos_bot.main()
        except Exception as e:
            print(f"❌ Kairos crashed: {e}")
            traceback.print_exc()
            await asyncio.sleep(3)

async def start_chrona():
    while True:
        try:
            print("🌸 Starting Chrona bot...")
            import chrona_bot
            await chrona_bot.main()
        except Exception as e:
            print(f"❌ Chrona crashed: {e}")
            traceback.print_exc()
            await asyncio.sleep(3)

async def handle_ping(request):
    return web.Response(text="Kairos & Chrona are alive! ⚡️🌸")

async def start_web_server():
    port = int(os.getenv("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Health-check веб-сервер слушает порт {port}")

async def main():
    print("🚀 Запуск экосистемы Telegram-ботов: Кайрос ⚡️ + Хрона 🌸")
    await asyncio.gather(
        start_web_server(),
        start_kairos(),
        start_chrona()
    )

if __name__ == "__main__":
    asyncio.run(main())
