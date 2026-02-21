# -*- coding: utf-8 -*-
import re
import uuid
from datetime import datetime, UTC

import scrapy
from scrapy.loader import ItemLoader
from news_crawler.items import NewsItem

# بخش‌های اقتصاد (طبق PRD فقط اقتصاد، سیاست، بین‌الملل)
LIST_URLS = [
    'https://ecoiran.com/%D8%A8%D8%AE%D8%B4-%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%DA%A9%D9%84%D8%A7%D9%86-186',
    'https://ecoiran.com/%D8%A8%D8%AE%D8%B4-%D8%A8%D8%A7%D9%86%DA%A9-%D8%A8%DB%8C%D9%85%D9%87-151',
    'https://ecoiran.com/%D8%A8%D8%AE%D8%B4-%D9%85%D8%A7%D9%84%DB%8C%D8%A7%D8%AA-94',
    'https://ecoiran.com/%D8%A8%D8%AE%D8%B4-%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A8%DB%8C%D9%86-%D8%A7%D9%84%D9%85%D9%84%D9%84-82'
]


class EcoiranSpider(scrapy.Spider):
    name = "ecoiran"
    allowed_domains = ["ecoiran.com"]

    def start_requests(self):
        for url in LIST_URLS:
            yield scrapy.Request(url, callback=self.parse_list_page)

    def parse_list_page(self, response):
        links = response.css("a.contentArticle::attr(href)").getall()
        seen = set()
        for href in links:
            if not href:
                continue
            full_url = response.urljoin(href)
            if full_url in seen:
                continue
            if "ecoiran.com" not in full_url:
                continue
            # لینک مقاله: شامل /عدد- یا /عدد/ (مثلاً /123264- یا /123264/)
            if not re.search(r"/\d{5,}[-/]", full_url):
                continue
            seen.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_news)

    def parse_news(self, response):
        loader = ItemLoader(item=NewsItem(), response=response)
        loader.add_value("source_domain", self.allowed_domains[0])
        loader.add_value("url", response.url)
        loader.add_value("article_id", str(uuid.uuid4()))
        loader.add_css("title", "h1[itemprop='headline']::text")
        loader.add_css("lead_text", "div.lead::text")

        body_selectors = (
            "div.content p::text, div.article-body p::text, "
            "div.post-content p::text, div.entry-content p::text, "
            "[itemprop='articleBody'] p::text, div.body p::text, article p::text"
        )
        loader.add_css("body_text", body_selectors)

        loader.add_css("author_or_reporter", "span.postCode::text")
        loader.add_xpath("category", "/html/body/main/div[1]/section[2]/div[2]/div[1]/div/div[2]/a/text()")
        loader.add_css("tags", "a.taglink::text")
        
        loader.add_css("publish_date_raw", "span[data-date]::attr(data-date)")
        loader.add_css("publish_date_utc", "span[data-date]::attr(data-date)")
        loader.add_value("crawl_timestamp", datetime.now(UTC).isoformat())

        has_media = bool(response.css(".content img, .article-body img, .content video, .article-body video"))
        loader.add_value("has_media", has_media)

        yield loader.load_item()
