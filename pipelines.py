# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
# from itemadapter import ItemAdapter


import logging
import os
import sqlite3
import json
import uuid
from scrapy.exceptions import DropItem
from news_crawler.items import NewsItem
from news_crawler.utils import body_to_markdown, sanitize_body_text

logger = logging.getLogger(__name__)

# فیلدهای اجباری برای اعتبارسنجی. Optional طبق PRD: lead_text, author_or_reporter
REQUIRED_NEWS_ITEM_FIELDS = (
    "url",
    "title",
    "body_text",
    "category",
    "tags",
    "publish_date_raw",
    "publish_date_utc",
)


def _is_empty(value, field_name=None):
    """بررسی خالی بودن مقدار (None، رشته خالی). برای tags لیست خالی مجاز است."""
    if value is None:
        return True
    if field_name == "tags" and isinstance(value, list):
        return False  # لیست خالی برای تگ‌ها مجاز است
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _first_value(value):
    """اولین مقدار غیرخالی از فیلد (برای چک کردن مقدار واقعی)."""
    if value is None:
        return None
    if isinstance(value, list):
        for v in value:
            if v is not None and (not isinstance(v, str) or v.strip()):
                return v.strip() if isinstance(v, str) else v
        return None
    return value.strip() if isinstance(value, str) else value


class NewsItemValidationPipeline:
    """
    آیتم‌های ناقص را Drop می‌کند و یک Alert برای به‌روزرسانی سلکتورها لاگ می‌کند.
    طبق PRD: اگر ساختار DOM عوض شده باشد، خزنده Crash نکند؛ خبر ناقص Drop شود و هشدار ثبت شود.
    """

    def process_item(self, item, spider):
        if not isinstance(item, NewsItem):
            return item

        missing = []
        for field in REQUIRED_NEWS_ITEM_FIELDS:
            raw = item.get(field)
            if _is_empty(raw, field_name=field):
                missing.append(field)
                continue
            # برای فیلدهای لیستی (غیر از tags) بررسی کن حداقل یک مقدار معنی‌دار داشته باشیم
            if field != "tags":
                first = _first_value(raw)
                if first is None or (isinstance(first, str) and not first.strip()):
                    missing.append(field)

        if not missing:
            return item

        url = _first_value(item.get("url")) or "(unknown)"
        alert_msg = (
            f"ALERT [SELECTOR_UPDATE] Incomplete item dropped | spider={spider.name} | url={url} | missing_fields={missing}"
        )
        logger.error(alert_msg)
        raise DropItem(alert_msg)


class BodyToMarkdownPipeline:
    """
    body_text را به مارک‌داون تمیز تبدیل می‌کند و بعد پاک‌سازی (حذف نویز) اعمال می‌کند.
    اگر اسپایدر HTML بدنه بفرستد، هدرها و لیست‌ها در مارک‌داون حفظ می‌شوند.
    """

    def process_item(self, item, spider):
        if not isinstance(item, NewsItem):
            return item
        raw = item.get("body_text")
        if raw is None:
            return item
        if isinstance(raw, list):
            raw = "\n".join(str(x).strip() for x in raw if x)
        raw = str(raw).strip()
        if not raw:
            return item
        markdown = body_to_markdown(raw)
        item["body_text"] = sanitize_body_text(markdown)
        return item


def _to_scalar(value):
    """تبدیل مقدار به اسکالر برای SQLite؛ ItemLoader گاهی لیست برمی‌گرداند."""
    if value is None:
        return None
    if isinstance(value, list):
        for v in value:
            if v is None:
                continue
            s = v.strip() if isinstance(v, str) else v
            if s != "":
                return s
        return value[0].strip() if value and isinstance(value[0], str) else (value[0] if value else None)
    return value.strip() if isinstance(value, str) else value


class NewsItemSqlitePipeline:
    """
    یک پایپلاین ساده که آیتم‌های NewsItem را در یک دیتابیس SQLite ذخیره می‌کند.
    """

    def open_spider(self, spider):
        # مسیر ثابت: همیشه داخل پوشهٔ پروژه (کنار scrapy.cfg) تا با هر cwd ذخیره در یک فایل باشد
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(project_dir, "news_items.db")
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        # جدول اگر وجود نداشته باشد ساخته می‌شود
        self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS news_items (
                id TEXT PRIMARY KEY,
                article_id TEXT,
                source_domain TEXT,
                url TEXT UNIQUE,
                title TEXT,
                lead_text TEXT,
                body_text TEXT,
                author_or_reporter TEXT,
                category TEXT,
                tags TEXT,
                publish_date_raw TEXT,
                publish_date_utc TEXT,
                crawl_timestamp TEXT,
                has_media INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_news_items_publish_date_utc ON news_items(publish_date_utc);
        """)
        self.conn.commit()

    def process_item(self, item, spider):
        # فقط آیتم‌هایی که از نوع NewsItem هستند ذخیره می‌شوند
        if not isinstance(item, NewsItem):
            return item
        # ItemLoader ممکن است فیلدها را به صورت لیست برگرداند؛ برای SQLite اسکالر می‌خواهیم
        item_id = str(uuid.uuid4())
        tags_val = item.get("tags")
        if isinstance(tags_val, list):
            tags_db = json.dumps([x.strip() if isinstance(x, str) else x for x in tags_val], ensure_ascii=False)
        else:
            tags_db = json.dumps(tags_val) if tags_val is not None else None
        has_media_val = item.get("has_media")
        if isinstance(has_media_val, list) and has_media_val:
            has_media_val = has_media_val[0]
        has_media_int = 1 if has_media_val else 0
        self.cursor.execute("""
            INSERT OR IGNORE INTO news_items (
                id, article_id, source_domain, url, title, lead_text,
                body_text, author_or_reporter, category, tags,
                publish_date_raw, publish_date_utc, crawl_timestamp, has_media
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id,
            _to_scalar(item.get("article_id")),
            _to_scalar(item.get("source_domain")),
            _to_scalar(item.get("url")),
            _to_scalar(item.get("title")),
            _to_scalar(item.get("lead_text")),
            _to_scalar(item.get("body_text")),
            _to_scalar(item.get("author_or_reporter")),
            _to_scalar(item.get("category")),
            tags_db,
            _to_scalar(item.get("publish_date_raw")),
            _to_scalar(item.get("publish_date_utc")),
            _to_scalar(item.get("crawl_timestamp")),
            has_media_int,
        ))
        self.conn.commit()
        url = _to_scalar(item.get("url")) or ""
        if self.cursor.rowcount > 0:
            logger.info("DB saved: %s", url[:80])
        else:
            logger.debug("DB duplicate (skipped): %s", url[:80])
        return item

    def close_spider(self, spider):
        if hasattr(self, "conn") and self.conn:
            self.conn.close()
            