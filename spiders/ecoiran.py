# -*- coding: utf-8 -*-
import re
import uuid
from datetime import datetime, UTC
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import scrapy
from scrapy.loader import ItemLoader
from news_crawler.items import NewsItem


LIST_URLS = [
    "https://ecoiran.com/%D8%A8%D8%AE%D8%B4-%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%DA%A9%D9%84%D8%A7%D9%86-186",
    "https://ecoiran.com/%D8%A8%D8%AE%D8%B4-%D8%A8%D8%A7%D9%86%DA%A9-%D8%A8%DB%8C%D9%85%D9%87-151",
    "https://ecoiran.com/%D8%A8%D8%AE%D8%B4-%D9%85%D8%A7%D9%84%DB%8C%D8%A7%D8%AA-94",
    "https://ecoiran.com/%D8%A8%D8%AE%D8%B4-%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A8%DB%8C%D9%86-%D8%A7%D9%84%D9%85%D9%84%D9%84-82",
]


class EcoiranSpider(scrapy.Spider):
    name = "ecoiran"
    allowed_domains = ["ecoiran.com"]

    custom_settings = {
        "LOG_LEVEL": "DEBUG",
    }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # جلوگیری از تکراری بین صفحات و حتی بین دسته‌ها
        self.seen_article_urls = set()
        # جلوگیری از loop روی صفحات لیست
        self.seen_list_pages = set()

    def start_requests(self):
        for base_url in LIST_URLS:
            page1 = self._build_page_url(base_url, 1)
            yield scrapy.Request(
                url=page1,
                callback=self.parse_list_page,
                meta={"base_url": base_url, "page": 1},
            )

    def parse_list_page(self, response):
        base_url = response.meta["base_url"]
        page = response.meta["page"]

        # ایمنی: اگر همین list-page را قبلاً دیده‌ایم، ادامه نده
        if response.url in self.seen_list_pages:
            return
        self.seen_list_pages.add(response.url)

        # لینک‌های مقاله
        links = response.css("a.contentArticle::attr(href)").getall()
        if not links:
            self.logger.info("No links found. Stop. base=%s page=%s url=%s", base_url, page, response.url)
            return

        new_count = 0

        for href in links:
            if not href:
                continue

            full_url = response.urljoin(href)

            if "ecoiran.com" not in full_url:
                continue

            # لینک مقاله: شامل /عدد- یا /عدد/ (مثلاً /123264- یا /123264/)
            if not re.search(r"/\d{5,}[-/]", full_url):
                continue

            if full_url in self.seen_article_urls:
                continue

            self.seen_article_urls.add(full_url)
            new_count += 1
            yield scrapy.Request(full_url, callback=self.parse_news)

        # اگر هیچ لینک جدیدی پیدا نشد، یعنی یا به آخر رسیدیم یا سایت صفحه تکراری می‌دهد => stop
        if new_count == 0:
            self.logger.info("No NEW articles. Stop. base=%s page=%s url=%s", base_url, page, response.url)
            return

        # صفحه بعد
        next_page = page + 1
        next_url = self._build_page_url(base_url, next_page)
        yield scrapy.Request(
            url=next_url,
            callback=self.parse_list_page,
            meta={"base_url": base_url, "page": next_page},
        )

    def _build_page_url(self, base_url: str, page: int) -> str:
        """
        ecoiran pagination:
        ecoiran.com/<section>/?page=N
        """
        p = urlparse(base_url)
        qs = parse_qs(p.query)

        # اگر صفحه 1 بودی، باز هم page=1 می‌گذاریم که رفتار یکدست باشد
        qs["page"] = [str(page)]

        new_query = urlencode(qs, doseq=True)
        return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))

    def parse_news(self, response):
        loader = ItemLoader(item=NewsItem(), response=response)
        loader.add_value("source_domain", self.allowed_domains[0])
        loader.add_value("url", response.url)
        loader.add_value("article_id", str(uuid.uuid4()))

        loader.add_css("title", "h1[itemprop='headline']::text")
        loader.add_css("lead_text", "div.lead::text")

        body_html = response.css("div.content").get() or response.css("div.article-body").get()
        if body_html:
            loader.add_value("body_text", body_html)
        else:
            loader.add_css(
                "body_text",
                "div.content p::text, div.article-body p::text, "
                "div.post-content p::text, [itemprop='articleBody'] p::text",
            )

        loader.add_css("author_or_reporter", "span.postCode::text")
        loader.add_xpath("category", "/html/body/main/div[1]/section[2]/div[2]/div[1]/div/div[2]/a/text()")
        loader.add_css("tags", "a.taglink::text")

        loader.add_css("publish_date_raw", "span[data-date]::attr(data-date)")
        loader.add_css("publish_date_utc", "span[data-date]::attr(data-date)")
        loader.add_value("crawl_timestamp", datetime.now(UTC).isoformat())

        has_media = bool(response.css(".content img, .article-body img, .content video, .article-body video"))
        loader.add_value("has_media", has_media)

        yield loader.load_item()