import os
import threading
import http.server
import socketserver
import logging

# ── Start bot in background thread ────────────────────────────────────────
def run_bot():
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        import bot
        bot.main()
    except Exception as e:
        logging.error(f"Bot error: {e}")

bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# ── Serve miniapp on PORT ─────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 8080))
DIRECTORY = os.path.join(os.path.dirname(__file__), "miniapp")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        pass

print(f"Serving miniapp on port {PORT}")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()
