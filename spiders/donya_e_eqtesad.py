# -*- coding: utf-8 -*-
import uuid
from datetime import datetime, UTC

import scrapy
from scrapy.loader import ItemLoader
from news_crawler.items import NewsItem

LIST_BASE = "https://donya-e-eqtesad.com/%D8%A8%D8%AE%D8%B4-%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-183"


class DonyaEEqtesadSpider(scrapy.Spider):
    name = "donya-e-eqtesad"
    allowed_domains = ["donya-e-eqtesad.com"]

    def start_requests(self):
        for page in range(1, 100):
            url = f"{LIST_BASE}/" if page == 1 else f"{LIST_BASE}/?page={page}"
            yield scrapy.Request(url, callback=self.parse_list_page)

    def parse_list_page(self, response):
        links = response.css("div.news-grouped-by-date a[href]::attr(href)").getall()
        seen = set()
        for href in links:
            if not href:
                continue
            full_url = response.urljoin(href)
            if full_url in seen:
                continue
            seen.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_news)

    def parse_news(self, response):
        loader = ItemLoader(item=NewsItem(), response=response)
        loader.add_value("source_domain", self.allowed_domains[0])
        loader.add_value("url", response.url)
        loader.add_value("article_id", str(uuid.uuid4()))

        loader.add_css("title", "h1.title::text")
        lead = response.css("h2.uptitle::text").get()
        loader.add_value("lead_text", lead.strip() if lead else "")

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
