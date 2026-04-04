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
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Clients ───────────────────────────────────────────────────────────────────
krutrim_client = OpenAI(
    api_key=KRUTRIM_API_KEY,
    base_url="https://cloud.olakrutrim.com/v1",
)

openrouter_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# ════════════════════════════════════════════════════════════════════════════
#  ACCESS CONTROL
# ════════════════════════════════════════════════════════════════════════════

OWNER_ID = 1898491690  # ← Replace with your Telegram user ID

APPROVED_FRIENDS = {7560587006: "PriyanshuPSK",1141168607: "@slippedsloppy0o0",
    # 123456789: "Kaustuab",
}

def get_access_level(user_id: int) -> str:
    if user_id == OWNER_ID:
        return "owner"
    if user_id in APPROVED_FRIENDS:
        return "friend"
    return "blocked"

# ════════════════════════════════════════════════════════════════════════════
#  MODEL REGISTRY — Krutrim + OpenRouter free pool
# ════════════════════════════════════════════════════════════════════════════

MODELS = {

    # ── Krutrim models ──────────────────────────────────────────────────────
    "llama70b":      {"provider": "krutrim", "model": "Llama-3.3-70B-Instruct",          "label": "Llama 3.3 70B (Krutrim) ⭐"},
    "llama8b":       {"provider": "krutrim", "model": "Meta-Llama-3-8B-Instruct",         "label": "Llama 3 8B (Krutrim)"},
    "mistral7b":     {"provider": "krutrim", "model": "Mistral-7B-Instruct",              "label": "Mistral 7B (Krutrim)"},
    "krutrim":       {"provider": "krutrim", "model": "Krutrim-spectre-v2",               "label": "Krutrim Spectre v2 (India's own)"},

    # ── OpenRouter — Top free models (April 2026) ───────────────────────────
    "deepseek":      {"provider": "openrouter", "model": "deepseek/deepseek-chat-v3-0324:free",     "label": "DeepSeek V3 (free) 🔥"},
    "deepseek-r1":   {"provider": "openrouter", "model": "deepseek/deepseek-r1:free",               "label": "DeepSeek R1 Reasoning (free)"},
    "llama4":        {"provider": "openrouter", "model": "meta-llama/llama-4-maverick:free",        "label": "Llama 4 Maverick (free)"},
    "llama-or":      {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free",  "label": "Llama 3.3 70B (OpenRouter free)"},
    "qwen3-235b":    {"provider": "openrouter", "model": "qwen/qwen3-235b-a22b:free",               "label": "Qwen3 235B (free)"},
    "qwen3-30b":     {"provider": "openrouter", "model": "qwen/qwen3-30b-a3b:free",                 "label": "Qwen3 30B (free)"},
    "qwen3-coder":   {"provider": "openrouter", "model": "qwen/qwen3-coder-480b-a35b:free",         "label": "Qwen3 Coder 480B (free) 💻"},
    "gemma3-27b":    {"provider": "openrouter", "model": "google/gemma-3-27b-it:free",              "label": "Gemma 3 27B (free)"},
    "gemma3-12b":    {"provider": "openrouter", "model": "google/gemma-3-12b-it:free",              "label": "Gemma 3 12B (free)"},
    "gemma3-4b":     {"provider": "openrouter", "model": "google/gemma-3-4b-it:free",               "label": "Gemma 3 4B (fast, free)"},
    "nemotron":      {"provider": "openrouter", "model": "nvidia/llama-3.1-nemotron-ultra-253b-v1:free", "label": "NVIDIA Nemotron 253B (free)"},
    "nemotron-s":    {"provider": "openrouter", "model": "nvidia/nemotron-3-super-49b:free",        "label": "NVIDIA Nemotron Super 49B (free)"},
    "mistral-s":     {"provider": "openrouter", "model": "mistralai/mistral-small-3.1-24b-instruct:free", "label": "Mistral Small 3.1 24B (free)"},
    "mistral-dev":   {"provider": "openrouter", "model": "mistralai/devstral-small:free",           "label": "Devstral Small - Coding (free)"},
    "phi4":          {"provider": "openrouter", "model": "microsoft/phi-4:free",                    "label": "Microsoft Phi-4 (free)"},
    "phi4-mini":     {"provider": "openrouter", "model": "microsoft/phi-4-mini-instruct:free",      "label": "Microsoft Phi-4 Mini (fast, free)"},
    "grok":          {"provider": "openrouter", "model": "x-ai/grok-4-fast:free",                   "label": "Grok 4 Fast (free) ⚡"},
    "glm":           {"provider": "openrouter", "model": "zhipu-ai/glm-4.5-air:free",               "label": "GLM 4.5 Air (free)"},
    "step":          {"provider": "openrouter", "model": "stepfun-ai/step-3-5-flash:free",          "label": "Step 3.5 Flash (free)"},
    "minimax":       {"provider": "openrouter", "model": "minimax/minimax-m2.5:free",               "label": "MiniMax M2.5 (free)"},
    "arcee":         {"provider": "openrouter", "model": "arcee-ai/trinity-large:free",             "label": "Arcee Trinity Large 400B (free)"},
    "internlm":      {"provider": "openrouter", "model": "internlm/internlm3-8b-instruct:free",     "label": "InternLM3 8B (free)"},
    "moonlight":     {"provider": "openrouter", "model": "moonshotai/moonlight-16a-instruct:free",  "label": "Moonlight 16A (free)"},
    "auto":          {"provider": "openrouter", "model": "openrouter/auto",                         "label": "OpenRouter Auto (picks best free model)"},
}

DEFAULT_MODEL = "llama70b"

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

If memories are provided (prefixed with [MEMORY]), treat them as established facts.

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
#  AI API CALL — routes to Krutrim or OpenRouter
# ════════════════════════════════════════════════════════════════════════════

def ask_ai(user_id: int, user_message: str, data: dict) -> str:
    ud = get_user_data(data, user_id)
    topic = ud["active_topic"]
    model_key = ud.get("model", DEFAULT_MODEL)
    model_info = MODELS.get(model_key, MODELS[DEFAULT_MODEL])
    memories = ud.get("memories", [])

    if topic not in ud["topics"]:
        ud["topics"][topic] = []

    ud["topics"][topic].append({"role": "user", "content": user_message})

    if len(ud["topics"][topic]) > 20:
        ud["topics"][topic] = ud["topics"][topic][-20:]

    messages = [{"role": "system", "content": get_system_prompt(user_id, memories)}] + ud["topics"][topic]

    provider = model_info["provider"]
    model_name = model_info["model"]

    try:
        if provider == "krutrim":
            if not KRUTRIM_API_KEY:
                return "⚠️ Krutrim API key not set."
            response = krutrim_client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=1024,
                temperature=0.7,
            )
        else:  # openrouter
            if not OPENROUTER_API_KEY:
                return "⚠️ OpenRouter API key not set. Add OPENROUTER_API_KEY in Railway variables."
            response = openrouter_client.chat.completions.create(
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
        logger.error(f"AI API error ({provider}): {e}")
        return f"⚠️ Error from {provider}: {e}"

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
            "🧠 *Your private AI advisor — v4*\n\n"
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
            "/models — list all models\n"
            "/setmodel `key` — switch model\n\n"
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
            "/models — list all models\n"
            "/setmodel `key` — switch model",
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
        await update.message.reply_text(f"▶ Switched to existing: *{topic_name}*", parse_mode="Markdown")
        return
    ud["topics"][topic_name] = []
    ud["active_topic"] = topic_name
    save_data(data)
    await update.message.reply_text(f"✅ Created: *{topic_name}*", parse_mode="Markdown")

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
        await update.message.reply_text(f"Not found. Your topics: {', '.join(ud['topics'].keys())}")
        return
    ud["active_topic"] = topic_name
    save_data(data)
    count = len(ud["topics"][topic_name]) // 2
    await update.message.reply_text(f"🔀 *{topic_name}* — {count} exchanges", parse_mode="Markdown")

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
        lines.append(f"{indicator} *{name}* — {len(history)//2} exchanges")
    await update.message.reply_text("📂 *Your topics:*\n\n" + "\n".join(lines), parse_mode="Markdown")

async def clear_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return
    ud = get_user_data(data, user_id)
    topic = ud["active_topic"]
    ud["topics"][topic] = []
    save_data(data)
    await update.message.reply_text(f"🗑️ *{topic}* cleared.", parse_mode="Markdown")

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
        await update.message.reply_text("Cannot delete General.")
        return
    if topic_name not in ud["topics"]:
        await update.message.reply_text(f"Not found: *{topic_name}*", parse_mode="Markdown")
        return
    del ud["topics"][topic_name]
    if ud["active_topic"] == topic_name:
        ud["active_topic"] = "General"
        await update.message.reply_text(f"🗑️ *{topic_name}* deleted. Back to General.", parse_mode="Markdown")
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
    await update.message.reply_text("🧠 *Saved memories:*\n\n" + "\n".join(lines), parse_mode="Markdown")

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
        await update.message.reply_text("Couldn't find that. Use /memories to see the list.")

# ── Model commands ────────────────────────────────────────────────────────────

async def show_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return
    ud = get_user_data(data, user_id)
    current = ud.get("model", DEFAULT_MODEL)
    info = MODELS.get(current, MODELS[DEFAULT_MODEL])
    await update.message.reply_text(
        f"🤖 *Current model:* `{current}`\n"
        f"_{info['label']}_\n"
        f"Provider: {info['provider']}\n\n"
        f"Use /models to see all options.",
        parse_mode="Markdown"
    )

async def list_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return

    krutrim_lines = ["*── Krutrim models ──*"]
    or_lines = ["*── OpenRouter free models ──*"]

    for key, info in MODELS.items():
        line = f"`{key}` — {info['label']}"
        if info["provider"] == "krutrim":
            krutrim_lines.append(line)
        else:
            or_lines.append(line)

    msg = "\n".join(krutrim_lines) + "\n\n" + "\n".join(or_lines)
    msg += "\n\nSwitch with: /setmodel `key`"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def set_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_access_level(user_id) == "blocked":
        await update.message.reply_text("🔒 Access denied.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /setmodel `key`\nSee /models for all options.", parse_mode="Markdown")
        return
    model_key = context.args[0].lower()
    if model_key not in MODELS:
        await update.message.reply_text(f"Unknown model key. Use /models to see all options.")
        return
    ud = get_user_data(data, user_id)
    ud["model"] = model_key
    save_data(data)
    info = MODELS[model_key]
    await update.message.reply_text(
        f"✅ Switched to *{model_key}*\n_{info['label']}_\nProvider: {info['provider']}",
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
        name = "You (Owner)" if uid_int == OWNER_ID else APPROVED_FRIENDS.get(uid_int, f"Unknown ({uid})")
        topics = list(ud.get("topics", {}).keys())
        active = ud.get("active_topic", "General")
        model = ud.get("model", DEFAULT_MODEL)
        mem_count = len(ud.get("memories", []))
        lines.append(f"👤 *{name}*\n  Topics: {', '.join(topics)}\n  Active: {active} | Model: {model} | Memories: {mem_count}")
    if not lines:
        await update.message.reply_text("No users yet.")
        return
    await update.message.reply_text("🔐 *Admin Panel*\n\n" + "\n\n".join(lines), parse_mode="Markdown")

async def addme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"Your Telegram user ID:\n`{user_id}`\n\nShare with bot owner to request access.",
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
    reply = ask_ai(user_id, user_text, data)
    await update.message.reply_text(f"_{active}_\n\n{reply}", parse_mode="Markdown")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN:
        logger.error("Missing TELEGRAM_BOT_TOKEN")
        return
    if not KRUTRIM_API_KEY:
        logger.warning("⚠️ KRUTRIM_API_KEY not set — Krutrim models won't work")
    if not OPENROUTER_API_KEY:
        logger.warning("⚠️ OPENROUTER_API_KEY not set — OpenRouter models won't work")
    if OWNER_ID == 0:
        logger.warning("⚠️ OWNER_ID not set!")

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
    app.add_handler(CommandHandler("models", list_models))
    app.add_handler(CommandHandler("setmodel", set_model))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addme", addme))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
