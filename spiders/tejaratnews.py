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

    def start_requests(self):
        for url in LIST_URLS:
            yield scrapy.Request(url, callback=self.parse_list_page)

    def parse_list_page(self, response):
        # آدرس لینک‌ها را با ::attr(href) بگیر (مقدار href)، نه متن لینک. تجارت‌نیوز slug دارد نه عدد.
        hrefs = response.css("section article h2 a::attr(href)").getall()
        if not hrefs:
            hrefs = response.xpath("//section//article//h2/a/@href").getall()
        if not hrefs:
            hrefs = response.css("a[href*='tejaratnews.com']::attr(href)").getall()
        seen = set()
        for href in hrefs:
            if not href or not href.strip():
                continue
            full_url = response.urljoin(href.strip())
            if full_url in seen:
                continue
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
            seen.add(full_url)
            yield scrapy.Request(full_url, callback=self.parse_news)

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
        loader.add_css("category", "div.news-media a::text")
        loader.add_css("tags", "div.single-post-meta-middle a::text, div.sp--tags-middle a::text, a[href*='/tag/']::text")
        
        loader.add_css("publish_date_raw", "time.published-time::attr(datetime)")
        loader.add_css("publish_date_utc", "time.published-time::attr(datetime)")
        loader.add_value("crawl_timestamp", datetime.now(UTC).isoformat())

        has_media = bool(response.css(".content img, .article-body img, .content video, .article-body video"))
        loader.add_value("has_media", has_media)

        yield loader.load_item()