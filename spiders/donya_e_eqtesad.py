# -*- coding: utf-8 -*-
import uuid
from datetime import datetime, UTC
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import scrapy
from scrapy.loader import ItemLoader
from news_crawler.items import NewsItem

LIST_BASE = "https://donya-e-eqtesad.com/%D8%A8%D8%AE%D8%B4-%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-183"


class DonyaEEqtesadSpider(scrapy.Spider):
    name = "donya-e-eqtesad"
    allowed_domains = ["donya-e-eqtesad.com"]

    custom_settings = {
        "LOG_LEVEL": "INFO",
        # اختیاری:
        # "CLOSESPIDER_ITEMCOUNT": 5000,
    }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_article_urls = set()
        self.seen_list_pages = set()

    def start_requests(self):
        # صفحه اول: دقیقاً مثل کد خودت / بدون page
        yield scrapy.Request(self._build_list_url(1), callback=self.parse_list_page, meta={"page": 1})

    def parse_list_page(self, response):
        page = response.meta.get("page", 1)

        # ایمنی: تکراری نبودن list-page
        if response.url in self.seen_list_pages:
            return
        self.seen_list_pages.add(response.url)

        # === هیچ تغییری در selector لیست نمی‌دهیم ===
        links = response.css("div.news-grouped-by-date a[href]::attr(href)").getall()

        # Stop 1: صفحه خالی
        if not links:
            self.logger.info("No links found. Stop. page=%s url=%s", page, response.url)
            return

        new_count = 0

        for href in links:
            if not href:
                continue

            full_url = response.urljoin(href)

            # جلوگیری از تکراری‌ها بین صفحات
            if full_url in self.seen_article_urls:
                continue

            self.seen_article_urls.add(full_url)
            new_count += 1

            yield scrapy.Request(full_url, callback=self.parse_news)

        # Stop 2: صفحه چیزی جدید نداشت => پایان pagination
        if new_count == 0:
            self.logger.info("No NEW articles. Stop. page=%s url=%s", page, response.url)
            return
        
        # صفحه بعد
        next_page = page + 1
        yield scrapy.Request(
            self._build_list_url(next_page),
            callback=self.parse_list_page,
            meta={"page": next_page},
        )

    def _build_list_url(self, page: int) -> str:
        """
        مثل کد خودت:
        page=1 -> LIST_BASE + "/"
        page>1 -> LIST_BASE + "/?page=N"
        """
        if page <= 1:
            return f"{LIST_BASE}/"

        # اگر LIST_BASE روزی query داشت، امن می‌سازیم
        base = f"{LIST_BASE}/"
        p = urlparse(base)
        qs = parse_qs(p.query)
        qs["page"] = [str(page)]
        new_query = urlencode(qs, doseq=True)
        return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))

    def parse_news(self, response):
        # === هیچ تغییری در selectorها و منطق parse_news نمی‌دهیم ===
        loader = ItemLoader(item=NewsItem(), response=response)
        loader.add_value("source_domain", self.allowed_domains[0])
        loader.add_value("url", response.url)
        loader.add_value("article_id", str(uuid.uuid4()))

        loader.add_css("title", "h1.title::text")
        lead = response.css("h2.uptitle::text").get()
        loader.add_value("lead_text", lead.strip() if lead else "")

        body_html = response.css("div.article-body").get() or response.css("div#echo-detail").get()
        if body_html:
            loader.add_value("body_text", body_html)
        else:
            loader.add_css("body_text", "div.article-body p::text, div#echo-detail p::text, div#echo-detail h2::text")

        author = response.xpath('//*[@id="news-page-article"]/header/div/div[1]/div[3]/span/span[2]/text()').get()
        if not author:
            author = response.xpath('//*[@id="news-page-article"]/header/div/div[1]/div[2]/span/text()').get()
        if author:
            loader.add_value("author_or_reporter", author.strip())

        raw_category = response.css("div.service-bar a span::text").getall()
        category = " ".join(p.strip().replace("گروه:", "").strip() for p in raw_category if p and p.strip())
        loader.add_value("category", category)

        loader.add_css("tags", "a.tags-detail::text")
        loader.add_css("publish_date_raw", "time.news-time::text")
        loader.add_css("publish_date_utc", "time.news-time::attr(datetime), time.news-time::text")
        loader.add_value("crawl_timestamp", datetime.now(UTC).isoformat())

        has_media = bool(response.css("div.article-body img, div#echo-detail img, div.article-body video, div#echo-detail video"))
        loader.add_value("has_media", has_media)

        yield loader.load_item()