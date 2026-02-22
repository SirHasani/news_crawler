# -*- coding: utf-8 -*-
import uuid
from datetime import datetime, UTC
from urllib.parse import urlparse

import scrapy
from scrapy.loader import ItemLoader

from news_crawler.items import NewsItem


LIST_URLS = [
    "https://tejaratnews.com/category/%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%DA%A9%D9%84%D8%A7%D9%86",
    "https://tejaratnews.com/category/%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%AC%D9%87%D8%A7%D9%86",
    "https://tejaratnews.com/category/%D8%B7%D9%84%D8%A7-%D9%88-%D8%A7%D8%B1%D8%B2",
    "https://tejaratnews.com/category/%D8%A8%D8%A7%D8%B2%D8%A7%D8%B1-%D8%B3%D8%B1%D9%85%D8%A7%DB%8C%D9%87",
    "https://tejaratnews.com/category/%D8%B5%D9%86%D8%B9%D8%AA-%D9%85%D8%B9%D8%AF%D9%86-%D8%AA%D8%AC%D8%A7%D8%B1%D8%AA/%D8%B3%D9%88%D8%AE%D8%AA-%D9%88-%D8%A7%D9%86%D8%B1%DA%98%DB%8C",
]


class TejaratnewsSpider(scrapy.Spider):
    name = "tejaratnews"
    allowed_domains = ["tejaratnews.com"]
    custom_settings = {
        "LOG_LEVEL": "DEBUG",
        # "FEEDS": {
        # "tejaratnews.json": {
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
        hrefs = response.css('div.category-list-right article.news-media h2.news-media__title-h a::attr(href)').getall()
        if not hrefs:
            # fallback محدود به همان container (نه کل صفحه)
            hrefs = response.css("div.category-list-right a::attr(href)").getall()

        for href in hrefs:
            if not href or not href.strip():
                continue

            full_url = response.urljoin(href.strip())

            # فیلترها
            if "tejaratnews.com" not in full_url:
                continue
            if "/tag/" in full_url or "/category/" in full_url or "/podcast/" in full_url:
                continue
            if full_url.rstrip("/") == "https://tejaratnews.com":
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
        next_page = response.css("a.next.page-numbers::attr(href)").get()
        if next_page:
            next_page_url = response.urljoin(next_page)
            if next_page_url != response.url and next_page_url not in self.seen_list_pages:
                yield response.follow(next_page_url, callback=self.parse_list_page, meta=response.meta)

    def parse_news(self, response):
        loader = ItemLoader(item=NewsItem(), response=response)

        loader.add_value("source_domain", self.allowed_domains[0])
        loader.add_value("url", response.url)
        loader.add_value("article_id", str(uuid.uuid4()))

        loader.add_css("title", "article h1::text")

        lead = response.css("div.excerpt::text").get()
        if not lead:
            lead = response.css("span.rotitr::text").get()
        loader.add_value("lead_text", lead.strip() if lead else "")

        loader.add_css("body_text", "div.single-post-content")

        loader.add_css("author_or_reporter", "span.news-code::text")
        loader.add_css("category", "div.news-media.news-media__label a::text")
        
        loader.add_css("tags","div.spmm-tag-list ul li a::text")

        loader.add_css("publish_date_raw", "time.published-time::attr(datetime)")
        loader.add_css("publish_date_utc", "time.published-time::attr(datetime)")
        loader.add_value("crawl_timestamp", datetime.now(UTC).isoformat())

        has_media = bool(
            response.css("div.gds-container img, div.gds-container video")
        )
        loader.add_value("has_media", has_media)

        yield loader.load_item()
        