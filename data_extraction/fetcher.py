import requests
from typing import Any

from bs4 import BeautifulSoup


def fetch_html(url: str, timeout: int = 10) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


class ArticleSchema:
    fields = [
        "title",
        "lead_text",
        "body_text",
        "author_or_reporter",
        "publish_date_raw",
        "category",
        "tags",
    ]


# هر آیتم: (تگ, کلاس یا None) یا (تگ, دیکشنری attrs برای meta)
# ترتیب = اولویت؛ سلکتورهای خاص‌تر اول
FIELD_HINTS: dict[str, list[tuple[str, str | None | dict[str, str]]]] = {
    "title": [
        ("h1", None),
        ("meta", {"property": "og:title"}),
        ("meta", {"name": "title"}),
        ("title", None),
        ("h2", None),
        ("div", "news-media__title-h"),
        ("div", "title"),
        ("div", "headline"),
    ],
    "body_text": [
        ("div", "single-post-content"),
        ("div", "article-body"),
        ("div", "entry-content"),
        ("div", "content-body"),
        ("div", "news-content"),
        ("div", "news-body"),
        ("div", "content"),
        ("div", "post"),
        ("div", "story"),
        ("div", "body"),
        ("article", None),
        ("main", None),
    ],
    "lead_text": [
        ("div", "excerpt"),
        ("span", "rotitr"),
        ("div", "lead"),
        ("p", "lead"),
        ("meta", {"property": "og:description"}),
        ("meta", {"name": "description"}),
        ("div", "summary"),
        ("p", "summary"),
    ],
    "author_or_reporter": [
        ("span", "news-code"),
        ("span", "author"),
        ("span", "reporter"),
        ("meta", {"name": "author"}),
        ("div", "author"),
        ("span", "byline"),
    ],
    "publish_date_raw": [
        ("time", "published-time"),
        ("time", None),
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "date"}),
        ("span", "date"),
        ("div", "date"),
    ],
    "category": [
        ("div", "news-media__label"),
        ("a", "category"),
        ("div", "category"),
        ("a", "section"),
        ("div", "section"),
    ],
    "tags": [
        ("div", "spmm-tag-list"),
        ("ul", "tag-list"),
        ("ul", "tags"),
        ("ul", "tag"),
        ("meta", {"name": "keywords"}),
    ],
}


def _css_from_el(el: Any) -> str:
    """از المان BeautifulSoup یک سلکتور CSS ساده می‌سازد (بدون ::text / ::attr)."""
    parts = [el.name]
    if el.has_attr("class") and el["class"]:
        parts.append("." + ".".join(c for c in el["class"] if c))
    if el.has_attr("id") and el["id"]:
        parts.append("#" + el["id"])
    return "".join(parts)


def guess_selectors(html: str) -> dict[str, str]:
    """
    از روی HTML صفحه، برای هر فیلد یک سلکتور شبه-Scrapy حدس می‌زند.
    خروجی همیشه یا سلکتور معتبر است یا رشته خالی.
    """
    soup = BeautifulSoup(html, "lxml")
    result: dict[str, str] = {}

    for field, hints in FIELD_HINTS.items():
        found = ""
        for item in hints:
            tag, cls_or_attrs = item
            el = None

            if isinstance(cls_or_attrs, dict):
                el = soup.find(tag, attrs=cls_or_attrs)
            elif cls_or_attrs is None:
                el = soup.find(tag)
            else:
                # کلاس: هر کلاسی که این رشته را داشته باشد
                el = soup.find(tag, class_=lambda c: c and cls_or_attrs in c)

            if not el:
                continue

            sel = _css_from_el(el)
            if not sel:
                continue

            # متا → مقدار از attr می‌آید؛ بقیه از متن
            if tag == "meta" and isinstance(cls_or_attrs, dict):
                parts = ["meta"]
                for k, v in cls_or_attrs.items():
                    parts.append(f'[{k}="{v}"]')
                found = "".join(parts) + "::attr(content)"
            elif field == "tags":
                # لیست تگ‌ها: سلکتور ظرف؛ در Scrapy با ::text یا a::text بچه‌ها را می‌گیری
                found = sel + " a::text" if el.find("a") else sel + "::text"
            else:
                found = sel + "::text"

            break

        result[field] = found

    return result
