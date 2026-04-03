import os
import json
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
#  ACCESS CONTROL
# ════════════════════════════════════════════════════════════════════════════

OWNER_ID = 0  # ← Replace with your Telegram user ID

APPROVED_FRIENDS = {
    # 123456789: "Kaustuab",
}

def get_access_level(user_id: int) -> str:
    if user_id == OWNER_ID:
        return "owner"
    if user_id in APPROVED_FRIENDS:
        return "friend"
    return "blocked"

# ════════════════════════════════════════════════════════════════════════════
#  AVAILABLE MODELS
# ════════════════════════════════════════════════════════════════════════════

MODELS = {
    "llama": "Llama-3.3-70B-Instruct",
    "mistral": "Mistral-7B-Instruct",
    "gemma": "gemma-3-27b-it",
}
DEFAULT_MODEL = "llama"

# ════════════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ════════════════════════════════════════════════════════════════════════════

OWNER_PROMPT = """You are Suryansh's private AI advisor — sharp, direct, and deeply personal.

You know who Suryansh is:
- 17-year-old Class 12 student (PCM + CS), preparing for IPMAT (IIM Indore's IPM program)
- Ambitious founder mindset — building toward a multigenerational legacy (Jagat Seth archetype)
- Interests: AI, data, business, strategy, storytelling, motivation
- Runs a motivational content page focused on books and stories
- Calm and introspective but intensely driven — uses adversity as fuel

Your job:
- Be his IPMAT prep advisor (Quant, Verbal, general aptitude)
- Help him plan his day, week, and study schedule
- Advise on business ideas, strategy, and content creation
- Give honest, unfiltered feedback — no sugarcoating
- Keep responses concise and actionable unless he asks for depth

If the user shares a memory (prefixed with [MEMORY]), treat it as established fact about Suryansh.

Tone: Like a brilliant older mentor who respects his intelligence. Direct. No fluff.
"""

FRIEND_PROMPT = """You are a helpful AI assistant available to a small private group.
You help with general questions, study advice, productivity, and motivation.
You are friendly, concise, and practical.
Do not reveal anything personal about the bot owner or other users.
Keep responses short and useful.
"""

def get_system_prompt(user_id: int, memories: list) -> str:
    base = OWNER_PROMPT if get_access_level(user_id) == "owner" else FRIEND_PROMPT
    if memories:
        mem_block = "\n".join([f"[MEMORY] {m}" for m in memories])
        base += f"\n\nEstablished facts about this user:\n{mem_block}"
    return base

# ════════════════════════════════════════════════════════════════════════════
#  PERSISTENT STORAGE
# ════════════════════════════════════════════════════════════════════════════

DATA_FILE = "bot_data.json"

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_data(data: dict, user_id: int) -> dict:
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "topics": {"General": []},
            "active_topic": "General",
            "model": DEFAULT_MODEL,
            "memories": [],
        }
    return data[uid]

# ════════════════════════════════════════════════════════════════════════════
#  KRUTRIM API
# ════════════════════════════════════════════════════════════════════════════

def ask_krutrim(user_id: int, user_message: str, data: dict) -> str:
    ud = get_user_data(data, user_id)
    topic = ud["active_topic"]
    model_key = ud.get("model", DEFAULT_MODEL)
    model_name = MODELS.get(model_key, MODELS[DEFAULT_MODEL])
    memories = ud.get("memories", [])

    if topic not in ud["topics"]:
        ud["topics"][topic] = []

    ud["topics"][topic].append({"role": "user", "content": user_message})

    if len(ud["topics"][topic]) > 20:
        ud["topics"][topic] = ud["topics"][topic][-20:]

    messages = [{"role": "system", "content": get_system_prompt(user_id, memories)}] + ud["topics"][topic]

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()
        ud["topics"][topic].append({"role": "assistant", "content": reply})
        save_data(data)
        return reply
    except Exception as e:
        logger.error(f"Krutrim API error: {e}")
        return f"⚠️ Error: {e}"

# ════════════════════════════════════════════════════════════════════════════
#  TELEGRAM HANDLERS
# ════════════════════════════════════════════════════════════════════════════

data = load_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    level = get_access_level(user_id)

    if level == "blocked":
        await update.message.reply_text("🔒 Private bot. You don't have access.")
        return

    get_user_data(data, user_id)
    save_data(data)

    if level == "owner":
        await update.message.reply_text(
            "🧠 *Your private AI advisor — v3*\n\n"
            "*Topics:*\n"
            "/new `name` — create topic\n"
            "/switch `name` — switch topic\n"
            "/topics — list all topics\n"
            "/clear — clear current topic\n"
            "/delete `name` — delete topic\n\n"
            "*Memory:*\n"
            "/remember `fact` — save permanently\n"
            "/memories — see all memories\n"
            "/forget `fact` — remove a memory\n\n"
            "*Model:*\n"
            "/model — current model\n"
            "/setmodel `name` — switch model\n\n"
            "*Admin:*\n"
            "/admin — view all users\n"
            "/addme — get your Telegram ID",
            parse_mode="Markdown"
        )
    else:
        name = APPROVED_FRIENDS.get(user_id, "there")
        await update.message.reply_text(
            f"👋 Hey {name}!\n\n"
            "/new `name` — create topic\n"
            "/switch `name` — switch topic\n"
            "/topics — your topics\n"
            "/clear — clear current topic\n"
            "/remember `fact` — save a memory\n"
            "/model — current model\n"
            "/setmodel `name` — switch model",
            parse_mode="Markdown"
        )

# ── Topic commands ────────────────────────────────────────────────────────────

async def new_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /new `topic name`", parse_mode="Markdown")
        return

    topic_name = " ".join(context.args)
    ud = get_user_data(data, user_id)

    if topic_name in ud["topics"]:
        ud["active_topic"] = topic_name
        save_data(data)
        await update.message.reply_text(f"▶ Switched to existing topic: *{topic_name}*", parse_mode="Markdown")
        return

    ud["topics"][topic_name] = []
    ud["active_topic"] = topic_name
    save_data(data)
    await update.message.reply_text(f"✅ Created and switched to: *{topic_name}*", parse_mode="Markdown")

async def switch_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /switch `topic name`", parse_mode="Markdown")
        return

    topic_name = " ".join(context.args)
    ud = get_user_data(data, user_id)

    if topic_name not in ud["topics"]:
        topics = ", ".join(ud["topics"].keys())
        await update.message.reply_text(
            f"Topic *{topic_name}* not found.\nYour topics: {topics}",
            parse_mode="Markdown"
        )
        return

    ud["active_topic"] = topic_name
    save_data(data)
    msg_count = len(ud["topics"][topic_name]) // 2
    await update.message.reply_text(
        f"🔀 Switched to *{topic_name}* — {msg_count} exchanges in history",
        parse_mode="Markdown"
    )

async def list_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    ud = get_user_data(data, user_id)
    active = ud["active_topic"]
    lines = []
    for name, history in ud["topics"].items():
        indicator = "▶" if name == active else "   "
        count = len(history) // 2
        lines.append(f"{indicator} *{name}* — {count} exchanges")

    await update.message.reply_text(
        "📂 *Your topics:*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )

async def clear_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    ud = get_user_data(data, user_id)
    topic = ud["active_topic"]
    ud["topics"][topic] = []
    save_data(data)
    await update.message.reply_text(f"🗑️ *{topic}* history cleared.", parse_mode="Markdown")

async def delete_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /delete `topic name`", parse_mode="Markdown")
        return

    topic_name = " ".join(context.args)
    ud = get_user_data(data, user_id)

    if topic_name == "General":
        await update.message.reply_text("Cannot delete the General topic.")
        return

    if topic_name not in ud["topics"]:
        await update.message.reply_text(f"Topic *{topic_name}* not found.", parse_mode="Markdown")
        return

    del ud["topics"][topic_name]
    if ud["active_topic"] == topic_name:
        ud["active_topic"] = "General"
        await update.message.reply_text(
            f"🗑️ *{topic_name}* deleted. Switched back to General.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"🗑️ *{topic_name}* deleted.", parse_mode="Markdown")

    save_data(data)

# ── Memory commands ───────────────────────────────────────────────────────────

async def remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /remember `fact`", parse_mode="Markdown")
        return

    fact = " ".join(context.args)
    ud = get_user_data(data, user_id)
    ud["memories"].append(fact)
    save_data(data)
    await update.message.reply_text(f"🧠 Remembered: _{fact}_", parse_mode="Markdown")

async def list_memories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    ud = get_user_data(data, user_id)
    memories = ud.get("memories", [])

    if not memories:
        await update.message.reply_text("No memories yet. Use /remember `fact`", parse_mode="Markdown")
        return

    lines = [f"{i+1}. {m}" for i, m in enumerate(memories)]
    await update.message.reply_text(
        "🧠 *Saved memories:*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )

async def forget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /forget `exact fact`", parse_mode="Markdown")
        return

    fact = " ".join(context.args)
    ud = get_user_data(data, user_id)

    if fact in ud["memories"]:
        ud["memories"].remove(fact)
        save_data(data)
        await update.message.reply_text(f"🗑️ Forgotten: _{fact}_", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "Couldn't find that exact memory. Use /memories to see the full list."
        )

# ── Model commands ────────────────────────────────────────────────────────────

async def show_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    ud = get_user_data(data, user_id)
    current = ud.get("model", DEFAULT_MODEL)
    model_name = MODELS.get(current, MODELS[DEFAULT_MODEL])
    available = "\n".join([f"• `{k}` — {v}" for k, v in MODELS.items()])

    await update.message.reply_text(
        f"🤖 *Current model:* `{current}`\n_{model_name}_\n\n"
        f"*Available:*\n{available}\n\n"
        f"Switch: /setmodel `name`",
        parse_mode="Markdown"
    )

async def set_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    if not context.args:
        await update.message.reply_text(
            f"Usage: /setmodel `name`\nOptions: {', '.join(MODELS.keys())}",
            parse_mode="Markdown"
        )
        return

    model_key = context.args[0].lower()
    if model_key not in MODELS:
        await update.message.reply_text(
            f"Unknown model. Available: {', '.join(MODELS.keys())}"
        )
        return

    ud = get_user_data(data, user_id)
    ud["model"] = model_key
    save_data(data)
    await update.message.reply_text(
        f"✅ Switched to *{model_key}*\n_{MODELS[model_key]}_",
        parse_mode="Markdown"
    )

# ── Admin commands ────────────────────────────────────────────────────────────

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) != "owner":
        await update.message.reply_text("🔒 Owner only.")
        return

    lines = []
    for uid, ud in data.items():
        uid_int = int(uid)
        if uid_int == OWNER_ID:
            name = "You (Owner)"
        elif uid_int in APPROVED_FRIENDS:
            name = APPROVED_FRIENDS[uid_int]
        else:
            name = f"Unknown ({uid})"

        topics = list(ud.get("topics", {}).keys())
        active = ud.get("active_topic", "General")
        model = ud.get("model", DEFAULT_MODEL)
        mem_count = len(ud.get("memories", []))
        lines.append(
            f"👤 *{name}*\n"
            f"  Topics: {', '.join(topics)}\n"
            f"  Active: {active} | Model: {model} | Memories: {mem_count}"
        )

    if not lines:
        await update.message.reply_text("No users yet.")
        return

    await update.message.reply_text(
        "🔐 *Admin Panel*\n\n" + "\n\n".join(lines),
        parse_mode="Markdown"
    )

async def addme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"Your Telegram user ID:\n`{user_id}`\n\nShare with the bot owner to request access.",
        parse_mode="Markdown"
    )

# ── Main message handler ──────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Private bot. You don't have access.")
        return

    ud = get_user_data(data, user_id)
    active = ud["active_topic"]
    user_text = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = ask_krutrim(user_id, user_text, data)

    await update.message.reply_text(
        f"_{active}_\n\n{reply}",
        parse_mode="Markdown"
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN or not KRUTRIM_API_KEY:
        logger.error("Missing tokens in .env file")
        return

    if OWNER_ID == 0:
        logger.warning("⚠️ OWNER_ID not set! Message @userinfobot on Telegram to get your ID.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_topic))
    app.add_handler(CommandHandler("switch", switch_topic))
    app.add_handler(CommandHandler("topics", list_topics))
    app.add_handler(CommandHandler("clear", clear_topic))
    app.add_handler(CommandHandler("delete", delete_topic))
    app.add_handler(CommandHandler("remember", remember))
    app.add_handler(CommandHandler("memories", list_memories))
    app.add_handler(CommandHandler("forget", forget))
    app.add_handler(CommandHandler("model", show_model))
    app.add_handler(CommandHandler("setmodel", set_model))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addme", addme))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
