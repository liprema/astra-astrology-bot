import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import asyncio
import traceback
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

async def run_bot_safe(bot_module_name: str, bot_icon: str):
    while True:
        try:
            print(f"{bot_icon} Starting {bot_module_name}...")
            mod = __import__(bot_module_name)
            if hasattr(mod, 'main'):
                await mod.main()
            else:
                print(f"No main in {bot_module_name}")
                await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ {bot_module_name} crashed: {e}")
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
        run_bot_safe("kairos_bot", "⚡️"),
        run_bot_safe("chrona_bot", "🌸")
    )

if __name__ == "__main__":
    asyncio.run(main())
