import re
import pytz
import jdatetime
from datetime import datetime

try:
    import html2text
except ImportError:
    html2text = None

DIGIT_TABLE = str.maketrans(
    {
        "\u06f0": "0",
        "\u06f1": "1",
        "\u06f2": "2",
        "\u06f3": "3",
        "\u06f4": "4",
        "\u06f5": "5",
        "\u06f6": "6",
        "\u06f7": "7",
        "\u06f8": "8",
        "\u06f9": "9",
        "\u0660": "0",
        "\u0661": "1",
        "\u0662": "2",
        "\u0663": "3",
        "\u0664": "4",
        "\u0665": "5",
        "\u0666": "6",
        "\u0667": "7",
        "\u0668": "8",
        "\u0669": "9",
    }
)

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


def body_to_markdown(value: str) -> str:
    """
    متن یا HTML بدنهٔ خبر را به مارک‌داون تمیز تبدیل می‌کند.
    - اگر مقدار شبیه HTML باشد (حاوی < و >)، با html2text به مارک‌داون تبدیل می‌شود.
    - وگرنه متن ساده در نظر گرفته می‌شود و فقط پاراگراف‌بندی نرمال می‌شود (\\n\\n بین پاراگراف‌ها).
    """
    if not value or not isinstance(value, str):
        return value or ""
    s = value.strip()
    if not s:
        return ""
    # تشخیص HTML
    if "<" in s and ">" in s and html2text is not None:
        try:
            h = html2text.HTML2Text()
            h.ignore_links = True   # فقط متن لینک بیاید، آدرس لینک ذخیره نشود (خروجی تمیز)
            h.ignore_images = True  # بدون لینک/مسیر تصویر
            h.body_width = 0
            h.ignore_emphasis = False
            out = h.handle(s)
            return out.strip()
        except Exception:
            pass
    # متن ساده: نرمال‌سازی پاراگراف‌ها
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", s)).strip()


# الگوی مارک‌داون لینک [متن](آدرس) برای حذف آدرس و نگه‌داشتن فقط متن
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\([^)]+\)")


def _strip_markdown_links(text: str) -> str:
    """تبدیل [متن](آدرس) به فقط «متن» تا body_text بدون لینک و تمیز باشد."""
    return MARKDOWN_LINK_PATTERN.sub(r"\1", text)


def sanitize_body_text(text: str) -> str:
    """
    پاک‌سازی body_text طبق PRD: حذف اسکریپت، دکمه‌های شبکه اجتماعی و لینک‌های «مطالب مرتبط».
    لینک‌های مارک‌داون [متن](url) به فقط متن تبدیل می‌شوند. فقط محتوای اصلی خبر باقی می‌ماند.
    """
    if not text or not isinstance(text, str):
        return text or ""
    text = _strip_markdown_links(text)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if BODY_TEXT_NOISE_PATTERNS.search(line):
            continue
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def fa_to_en_digits(text: str) -> str:
    if not isinstance(text, str):
        return text
    return text.translate(DIGIT_TABLE)


def extract_news_id(text: str):
    text = text.strip()
    text = fa_to_en_digits(text)
    match = re.search(r'\d+', text)
    return match.group() if match else None



def shamsi_to_utc(value):
    if not value:
        return value

    try:
        # Normalize digits and separators.
        normalized_value = fa_to_en_digits(value).strip()

        # If value already looks Gregorian, parse as Gregorian.
        year_match = re.match(r"^(\d{4})[-/]", normalized_value)
        year = int(year_match.group(1)) if year_match else None
        if year is not None and year >= 1900:
            iso_candidate = normalized_value
            if iso_candidate.endswith("Z"):
                iso_candidate = iso_candidate[:-1] + "+00:00"
            try:
                gregorian_iso = datetime.fromisoformat(iso_candidate)
                if gregorian_iso.tzinfo is None:
                    gregorian_iso = pytz.timezone("Asia/Tehran").localize(gregorian_iso)
                return gregorian_iso.astimezone(pytz.UTC).isoformat()
            except ValueError:
                pass

        # Normalize Shamsi formats (handle T separator and slash-separated date).
        normalized_value = normalized_value.replace("/", "-").replace("T", " ")
        if re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}$", normalized_value):
            normalized_value = f"{normalized_value[:10]} {normalized_value[11:13]}:{normalized_value[14:16]}"

        # Try parsing supported formats
        parse_formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        )
        jalali_dt = None
        for date_format in parse_formats:
            try:
                jalali_dt = jdatetime.datetime.strptime(normalized_value, date_format)
                break
            except ValueError:
                continue
        if jalali_dt is None:
            raise ValueError(f"Unsupported date format: {value}")

        # Convert to Gregorian
        gregorian_dt = jalali_dt.togregorian()

        # Localize to Iran timezone
        iran_tz = pytz.timezone("Asia/Tehran")
        localized_dt = iran_tz.localize(gregorian_dt)

        # Convert to UTC
        utc_dt = localized_dt.astimezone(pytz.UTC)

        return utc_dt.isoformat()

    except Exception as e:
        print(f"Date conversion error: {value} -> {e}")
        return value

def extract_khabar_code(text: str):

    if not text or not isinstance(text, str):
        return None
    match = re.search(r"کد\s*خبر\s*[:：]?\s*(\d+)", text)
    if match:
        return match.group(1)
    return text.strip()
