import uuid
from datetime import datetime, UTC
from urllib.parse import urlparse
import scrapy
from scrapy.loader import ItemLoader
from news_crawler.items import NewsItem


LIST_URLS = [
    "https://sena.ir/archive?tp=2",
    "https://sena.ir/archive?tp=3",
    "https://sena.ir/archive?tp=4",
    "https://sena.ir/archive?tp=5",
    "https://sena.ir/archive?tp=6",
    "https://sena.ir/archive?tp=9",
    "https://sena.ir/archive?tp=57",
    "https://sena.ir/archive?tp=58",
    "https://sena.ir/archive?tp=61",
]


class SenaSpider(scrapy.Spider):
    name = "sena"
    allowed_domains = ["sena.ir"]
    ROBOTSTXT_OBEY = True
    custom_settings = {
     #    "LOG_LEVEL": "INFO",
        # "FEEDS": {
        # "sena.json": {
        # "format": "json",
        # "encoding": "utf8",
        # "indent": 2,
        #     }
        # }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # جلوگیری از درخواست تکراری بین صفحات/دسته‌ها
        self.seen_news_urls = set()
        # جلوگیری از loop یا تکرار list-page
        self.seen_list_pages = set()

    def start_requests(self):
        for url in LIST_URLS:
            yield scrapy.Request(
                url=url,
                callback=self.parse_list_page,
                meta={"category_start_url": url},
            )

    def parse_list_page(self, response):
        # ایمنی: اگر همین صفحه قبلاً پردازش شده، برگرد
        if response.url in self.seen_list_pages:
            return
        self.seen_list_pages.add(response.url)

        # 1) لینک خبرها را فقط از لیست اصلی دسته بگیر
        hrefs = response.css("li.report div.desc h4 a::attr(href)").getall()
        #    if not hrefs:
        #        hrefs = response.css("div.category-list-right a::attr(href)").getall()

        for href in hrefs:
            if not href or not href.strip():
                continue

            full_url = response.urljoin(href.strip())

            # فیلترها
            if "sena.ir" not in full_url:
                continue
            if (
                "/tag/" in full_url
                or "/category/" in full_url
                or "/podcast/" in full_url
            ):
                continue
            if full_url.rstrip("/") == "https://sena.ir":
                continue

            parsed = urlparse(full_url)
            if parsed.query:
                continue

            path = (parsed.path or "").strip("/")
            if not path:
                continue

            if full_url in self.seen_news_urls:
                continue
            self.seen_news_urls.add(full_url)

            yield scrapy.Request(full_url, callback=self.parse_news)

        # 2) صفحه بعد: <a class="next page-numbers" ...>
        next_page = response.xpath(
            '//ul[contains(@class,"pagination")]//a[normalize-space()="بعدی"]/@href').get()
        if next_page:
            next_page_url = response.urljoin(next_page)
            if (
                next_page_url != response.url
                and next_page_url not in self.seen_list_pages
            ):
                yield response.follow(
                    next_page_url, callback=self.parse_list_page, meta=response.meta
                )

    def parse_news(self, response):
        loader = ItemLoader(item=NewsItem(), response=response)

        loader.add_value("source_domain", self.allowed_domains[0])
        loader.add_value("url", response.url)
        loader.add_value("article_id", str(uuid.uuid4()))

        loader.add_css("title", "h1.title a::text")

        lead_sel = response.css("p.summary.introtext::text")
        if not lead_sel:
            lead_sel = response.css("p[itemprop='description']::text")
        lead_text = (lead_sel.get() or "").strip()
        loader.add_value("lead_text", lead_text)

        loader.add_css("body_text", "div[itemprop='articleBody']")

        loader.add_xpath("author_or_reporter", '//div[contains(@class,"item-nav")]//div[contains(text(),"کد خبر")]/span/text()')
        loader.add_css("category", 'ol.breadcrumb a[itemprop="articleSection"]::text')

        loader.add_xpath("tags", '//section[contains(@class,"tags")]//li/a/text()').getall()

        loader.add_css("publish_date_raw", '.item-date span::text')
        loader.add_css("publish_date_utc", '.item-date span::text')
        loader.add_value("crawl_timestamp", datetime.now(UTC).isoformat())

        has_media = bool(response.css("div.item-summary img, div.item-summary video"))
        loader.add_value("has_media", has_media)

        yield loader.load_item()
