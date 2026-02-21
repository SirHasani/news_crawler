# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from w3lib.html import remove_tags
from itemloaders.processors import TakeFirst, MapCompose, Join, Compose

from news_crawler.utils import fa_to_en_digits
from news_crawler.utils import shamsi_to_utc, extract_khabar_code

# فیلدهای اختیاری (Optional): در اعتبارسنجی چک نمی‌شوند.
OPTIONAL_NEWS_ITEM_FIELDS = ("lead_text", "author_or_reporter")


class NewsItem(scrapy.Item):
    # --- اجباری ---
    article_id = scrapy.Field()       # UUID تولید شده توسط سیستم
    source_domain = scrapy.Field()    # مثلا farsnews.ir
    url = scrapy.Field()              # لینک یکتای خبر
    title = scrapy.Field()            # تیتر اصلی، بدون کاراکترهای اضافه
    body_text = scrapy.Field(         # متن کامل خبر، بدون تگ HTML و تبلیغات
        input_processor=MapCompose(lambda x: x.strip() if isinstance(x, str) else x),
        output_processor=Join("\n"),
    )
    # --- Optional ---
    lead_text = scrapy.Field()        # روتیتر یا خلاصه خبر (Optional)
    author_or_reporter = scrapy.Field(  # نام خبرنگار یا کد خبر (Optional)
        input_processor=MapCompose(
            remove_tags,
            str.strip,
            lambda x: fa_to_en_digits(x) if isinstance(x, str) else x,
            extract_khabar_code,
        ),
    )
    # --- اجباری ---
    category = scrapy.Field()         # دسته‌بندی سایت مثلا اقتصاد کلان
    tags = scrapy.Field()             # لیست کلمات کلیدی پایین خبر
    publish_date_raw = scrapy.Field(   # تاریخ دقیقاً همان‌طور که در سایت نوشته شده
        input_processor=MapCompose(
            remove_tags,
            str.strip,
            lambda x: fa_to_en_digits(x) if isinstance(x, str) else x,
        ),
    )
    publish_date_utc = scrapy.Field(   # تبدیل‌شده به فرمت استاندارد UTC
        input_processor=MapCompose(
            lambda x: x.strip() if isinstance(x, str) else x,
            shamsi_to_utc,
        ),
        output_processor=TakeFirst(),
    )
    crawl_timestamp = scrapy.Field()   # زمان دقیق اجرای کرالر
    has_media = scrapy.Field()         # boolean: آیا خبر عکس/ویدیو دارد

