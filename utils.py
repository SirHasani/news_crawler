import re
import pytz
import jdatetime

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ENGLISH_DIGITS = "0123456789"
DIGIT_TABLE = str.maketrans(PERSIAN_DIGITS, ENGLISH_DIGITS)

# الگوهای خطوطی که باید از body_text حذف شوند (اسکریپت، دکمه شبکه اجتماعی، مطالب مرتبط)
BODY_TEXT_NOISE_PATTERNS = re.compile(
    r"|".join(
        [
            r"مطالب\s*مرتبط",
            r"اخبار\s*مرتبط",
            r"بیشتر\s*بخوانید",
            r"اشتراک\s*در",
            r"ارسال\s*به",
            r"تلگرام",
            r"واتس[اآ]پ",
            r"توییتر",
            r"تِلِگرام",
            r"اینستاگرام",
            r"لینکدین",
            r"share\s*on",
            r"tweet",
            r"telegram",
            r"whatsapp",
            r"<script",
            r"function\s*\(",
            r"var\s+\w+\s*=",
            r"^\s*\{\s*\}\s*$",
            r"^\s*\[.*\]\s*$",  # خطوط فقط براکت (ممکن است بقایای JSON/کد باشند)
        ]
    ),
    re.IGNORECASE,
)


def sanitize_body_text(text: str) -> str:
    """
    پاک‌سازی body_text طبق PRD: حذف اسکریپت، دکمه‌های شبکه اجتماعی و لینک‌های «مطالب مرتبط».
    فقط محتوای اصلی خبر باقی می‌ماند.
    """
    if not text or not isinstance(text, str):
        return text or ""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # خطوطی که فقط شامل الگوی نویز هستند حذف می‌شوند
        if BODY_TEXT_NOISE_PATTERNS.search(line):
            continue
        # خطوط خیلی کوتاهِ فقط نماد/انگلیسیِ شبیه کد (مثلاً یک کلمه تکی) را نگاه دار؛ فقط خطوط واضحاً اسکریپتی را حذف کن
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def fa_to_en_digits(text: str) -> str:
    return text.translate(DIGIT_TABLE)


def extract_news_id(text: str):
    text = text.strip()
    text = fa_to_en_digits(text)
    match = re.search(r'\d+', text)
    return match.group() if match else None

def shamsi_to_utc(value):
    year, month, day, hour, minute = map(int, value.split('-'))
    
    # تبدیل به میلادی
    jalali_dt = jdatetime.JalaliDateTime(year, month, day, hour, minute)
    gregorian_dt = jalali_dt.to_gregorian()
    
    iran_tz = pytz.timezone("Asia/Tehran")
    localized_dt = iran_tz.localize(gregorian_dt)
    
    # تبدیل به UTC
    utc_dt = localized_dt.astimezone(pytz.UTC)
    
    return utc_dt.isoformat()

def extract_khabar_code(text: str):

    if not text or not isinstance(text, str):
        return None
    match = re.search(r"کد\s*خبر\s*[:：]?\s*(\d+)", text)
    if match:
        return match.group(1)
    return text.strip()