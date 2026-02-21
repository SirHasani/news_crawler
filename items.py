# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from w3lib.html import remove_tags
from itemloaders.processors import TakeFirst, MapCompose, Join, Compose

from news_crawler.utils import fa_to_en_digits, sanitize_body_text
from news_crawler.utils import shamsi_to_utc, extract_khabar_code


class NewsItem(scrapy.Item):
    article_id = scrapy.Field()
    source_domain = scrapy.Field()
    url = scrapy.Field()
    title = scrapy.Field()
    lead_text = scrapy.Field()
    body_text = scrapy.Field(
        input_processor=MapCompose(remove_tags, str.strip),
        output_processor=Compose(Join("\n"), sanitize_body_text),
    )
    author_or_reporter = scrapy.Field(
        input_processor=MapCompose(
            remove_tags,
            str.strip,
            lambda x: fa_to_en_digits(x) if isinstance(x, str) else x,
            extract_khabar_code,
        ),
    )
    category = scrapy.Field()
    tags = scrapy.Field()
    publish_date_raw = scrapy.Field(
        input_processor=MapCompose(
            remove_tags,
            str.strip,
            lambda x: fa_to_en_digits(x) if isinstance(x, str) else x,
        ),
    )
    publish_date_utc = scrapy.Field(
        input_processor=MapCompose(
            lambda x: x.strip() if isinstance(x, str) else x,
            to_utc_iso,
        ),
        output_processor=TakeFirst(),
    )
    crawl_timestamp = scrapy.Field()
    has_media = scrapy.Field()

