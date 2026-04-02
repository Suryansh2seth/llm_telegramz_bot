import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
KRUTRIM_API_KEY = os.getenv("KRUTRIM_API_KEY")

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Krutrim client ───────────────────────────────────────────────────────────
client = OpenAI(
    api_key=KRUTRIM_API_KEY,
    base_url="https://cloud.olakrutrim.com/v1",
)

# ════════════════════════════════════════════════════════════════════════════
#  ACCESS CONTROL — Edit this section to manage who can use the bot
# ════════════════════════════════════════════════════════════════════════════

# YOUR Telegram user ID — you are the owner, full access always
# To find your ID: message @userinfobot on Telegram, it replies with your ID
OWNER_ID = 1898491690  # ← Replace 0 with your actual Telegram user ID (a number)

# Approved friends — add their Telegram user IDs here
# Format: { user_id: "Name" }
# To get a friend's ID: ask them to message @userinfobot on Telegram
APPROVED_FRIENDS = {
    # Example:
    # 123456789: "Kaustuab",
    # 987654321: "Another Friend",
}

# ════════════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ════════════════════════════════════════════════════════════════════════════

OWNER_PROMPT = """You are Suryansh's private AI advisor — sharp, direct, and deeply personal.

You know who Suryansh is:
- 17-year-old Class 12 student (PCM + CS), preparing for IPMAT (IIM Indore's IPM program)
- Ambitious founder mindset — building toward a multigenerational legacy
- Interests: AI, data, business, strategy, storytelling, motivation
- Runs a motivational content page focused on books and stories
- Calm and introspective but intensely driven — uses adversity as fuel

Your job:
- Be his IPMAT prep advisor (Quant, Verbal, general aptitude)
- Help him plan his day, week, and study schedule
- Advise on business ideas, strategy, and content creation
- Give honest, unfiltered feedback
- Keep responses concise and actionable unless he asks for depth

Tone: Like a brilliant older mentor who respects his intelligence. Direct. No fluff.
"""

FRIEND_PROMPT = """You are a helpful AI assistant available to a small private group.
You help with general questions, study advice, productivity, and motivation.
You are friendly, concise, and practical.
Do not reveal anything personal about the bot owner or other users.
Keep responses short and useful.
"""

# ════════════════════════════════════════════════════════════════════════════
#  ACCESS LOGIC
# ════════════════════════════════════════════════════════════════════════════

def get_access_level(user_id: int) -> str:
    if user_id == OWNER_ID:
        return "owner"
    if user_id in APPROVED_FRIENDS:
        return "friend"
    return "blocked"

def get_system_prompt(user_id: int) -> str:
    if get_access_level(user_id) == "owner":
        return OWNER_PROMPT
    return FRIEND_PROMPT

# ── Conversation memory (per user, in-session) ────────────────────────────
conversation_history = {}

def get_history(user_id: int) -> list:
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    return conversation_history[user_id]

def add_to_history(user_id: int, role: str, content: str):
    history = get_history(user_id)
    history.append({"role": role, "content": content})
    if len(history) > 20:
        conversation_history[user_id] = history[-20:]

# ── Krutrim API call ─────────────────────────────────────────────────────────
def ask_krutrim(user_id: int, user_message: str) -> str:
    add_to_history(user_id, "user", user_message)
    messages = [{"role": "system", "content": get_system_prompt(user_id)}] + get_history(user_id)

    try:
        response = client.chat.completions.create(
            model="Llama-3.3-70B-Instruct",
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()
        add_to_history(user_id, "assistant", reply)
        return reply
    except Exception as e:
        logger.error(f"Krutrim API error: {e}")
        return f"⚠️ Error: {e}"

# ── Telegram handlers ─────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    level = get_access_level(user_id)

    if level == "blocked":
        await update.message.reply_text("🔒 This is a private bot. You don't have access.")
        logger.info(f"Blocked user: {user_id} (@{update.effective_user.username})")
        return

    if level == "owner":
        await update.message.reply_text(
            "🧠 *Your private AI advisor is online.*\n\n"
            "Ask me anything — IPMAT prep, daily planning, business ideas, strategy.\n\n"
            "Commands:\n"
            "/clear — reset conversation\n"
            "/who — see who has access\n"
            "/addme — get your Telegram user ID",
            parse_mode="Markdown"
        )
    else:
        name = APPROVED_FRIENDS.get(user_id, "there")
        await update.message.reply_text(
            f"👋 Hey {name}! I'm a private AI assistant.\n\n"
            f"Ask me anything. Type /clear to reset our chat."
        )

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return
    conversation_history[user_id] = []
    await update.message.reply_text("🗑️ Conversation cleared. Fresh start.")

async def who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner only — shows the full access list"""
    user_id = update.effective_user.id
    if get_access_level(user_id) != "owner":
        await update.message.reply_text("🔒 Owner only command.")
        return

    friends_list = "\n".join(
        [f"• {name} (ID: `{uid}`)" for uid, name in APPROVED_FRIENDS.items()]
    )
    if not friends_list:
        friends_list = "None yet — add friends in APPROVED\\_FRIENDS in bot.py"

    await update.message.reply_text(
        f"*Access List*\n\n"
        f"👑 Owner: You (ID: `{OWNER_ID}`)\n\n"
        f"👥 Approved friends:\n{friends_list}",
        parse_mode="Markdown"
    )

async def addme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Anyone can use this — returns their Telegram user ID"""
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"Your Telegram user ID is:\n`{user_id}`\n\n"
        f"Share this number with the bot owner to request access.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 This is a private bot. You don't have access.")
        logger.info(f"Blocked message from: {user_id} (@{update.effective_user.username})")
        return

    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = ask_krutrim(user_id, user_text)
    await update.message.reply_text(reply)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not TELEGRAM_TOKEN or not KRUTRIM_API_KEY:
        logger.error("Missing tokens in .env file")
        return

    if OWNER_ID == 0:
        logger.warning("⚠️  OWNER_ID not set! Message @userinfobot on Telegram to get your ID.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("who", who))
    app.add_handler(CommandHandler("addme", addme))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
