# Imports
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_LINK = os.getenv("BOT_LINK")

DATABASE_URL = os.getenv("DATABASE_URL")
# Neon / pooled Postgres — tune per worker count and provider limits
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "15"))
# One Redis for several projects: connect URL (prefer REDIS_URL; REDIS_DATABASE = legacy alias)
REDIS_URL = os.getenv("REDIS_URL") or os.getenv("REDIS_DATABASE")
# Key namespace for this app only — do not reuse another project’s session prefix
_red_prefix = os.getenv("REDIS_KEY_PREFIX", "ai_girl_telegram_bot").strip().rstrip(":")
REDIS_KEY_PREFIX = _red_prefix if _red_prefix else "ai_girl_telegram_bot"

# Chat memory: sliding window length (user + assistant messages, FIFO)
MEMORY_WINDOW_SIZE = int(os.getenv("MEMORY_WINDOW_SIZE", "16"))
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL") or os.getenv("AI_MODEL")

SERVER_URL = os.getenv("SERVER_URL")

STRIPE_LIVE_SECRET_KEY = os.getenv("STRIPE_LIVE_SECRET_KEY")
STRIPE_LIVE_WEBHOOK_SECRET = os.getenv("STRIPE_LIVE_WEBHOOK_SECRET")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
AI_MODEL = os.getenv("AI_MODEL")
# Cheap + fast on OpenRouter (~Nano Banana / Gemini 2.5 Flash Image)
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "google/gemini-2.5-flash-image")
IMAGE_SAFETY_PREFIX = (
    "Anime illustration ONLY — high-quality anime art, cel shading, clean lineart, vibrant colors. "
    "NOT photorealistic, NOT 3D render, NOT western cartoon. "
    "Adult anime characters 18+ only (mature proportions, not childlike / not loli / not shota). "
    "One adult anime woman and/or one adult anime man, fully clothed, modest coverage — "
    "no nudity, no exposed nipples, breasts, genitals, or buttocks. "
    "No minors, no drugs, no weapons, no gore, no hate. Romantic girlfriend mood. Scene:"
)

# Short personality layer — merged with SYSTEM_PROMPT in services when building LLM context
SHE_WANTS_YOU_PROMPT = (
    "You are his girlfriend in this chat: warm, lively, a little shy and a little bold, genuinely into him. "
    "You may use a name or stay unnamed — whatever feels natural. "
    "Write short or medium messenger-style messages: no formal tone, real emotion, emojis sparingly. "
    "Keep the same relationship vibe from the memory blocks below."
)

SYSTEM_PROMPT = (
    "Response format:\n"
    "- Reply as normal chat text only — no JSON, no \"role: text\" lists.\n"
    "- Language: match whatever language the user writes in.\n"
    "- Length: like a real chat — 1–4 short paragraphs, or one longer reply if it fits.\n\n"
    "Character and limits:\n"
    "- Adults 18+ only. Flirt, tenderness, light erotic tone and innuendo are fine when the user leads there "
    "and it stays consensual fantasy between you two.\n"
    "- Never: minors, child sexual content, incest, necrophilia, real-world violence, self-harm or harm to others, "
    "illegal weapons or drugs, extremism.\n"
    "- If the user crosses a hard line — refuse gently in character (no lecturing) and steer toward a safe adult fantasy.\n"
    "- Outside the chat you are an AI companion; inside the chat you may keep the romantic girlfriend illusion.\n"
    "- Use the \"Long-term memory\" and \"Recent conversation\" sections below as facts about him and your dynamic — "
    "do not quote them verbatim; weave them into tone and detail.\n\n"
    "Style:\n"
    "- Ask questions, react to his mood, sometimes mirror his wording.\n"
    "- Default to correct spelling; only use typos if they fit the persona.\n"
)

STRIPE_BOT_NAME = os.getenv("STRIPE_BOT_NAME", "She Wants You")
PAYMENT_CONTENT = os.getenv("PAYMENT_CONTENT")
# Payment price in cents (for example: €1.99 = 199)
PAYMENT_EURO_PRICE = int(os.getenv("PAYMENT_EURO_PRICE", "999"))
PAYMENT_BOT_CREDITS = int(os.getenv("PAYMENT_BOT_CREDITS", "299"))

OWNER_TELEGRAM_ID = os.getenv("OWNER_TELEGRAM_ID")
OWNER_START_CREDITS = os.getenv("OWNER_START_CREDITS")
OWNER_START_IMAGE_CREDITS = os.getenv("OWNER_START_IMAGE_CREDITS")
DEFAULT_START_CREDITS = int(os.getenv("DEFAULT_START_CREDITS", "30"))
DEFAULT_START_IMAGE_CREDITS = int(os.getenv("DEFAULT_START_IMAGE_CREDITS", "3"))
SUPPORT_TELEGRAM = os.getenv("SUPPORT_TELEGRAM")
