import httpx
from parsel import Selector
import re
import json

# ۱. نقشه اولویت‌بندی شده به صورت رشته‌های مستقیم CSS
FIELD_HINTS = {
    "title": [
        "h1::text",
        "meta[property='og:title']::attr(content)",
        "meta[name='title']::attr(content)",
        "title::text"
    ],
    "lead_text": [
        "h2.uptitle::text",
        "div.excerpt",
        "span.rotitr",
        "div.lead",
        "p.lead",
        "meta[property='og:description']::attr(content)",
        "meta[name='description']::attr(content)",
    ],  
    "body_text": [
        "div.article-body",
        "div[class*='single-post-content']",
        "div.entry-content",
        "article",
        "main"
    ],
    "author_or_reporter": [
        "span.news-code",
        "span.author",
        "span.reporter",
        "meta[name='author']::attr(content)",
        "div.author",
    ],
    "category": [
        "div.service-bar a span::text",
        "meta[property='article:section']::attr(content)",
        "div.breadcrumb a:last-child::text",
        "a[class*='category']::text",
        "div[class*='category']::text"
    ],
    "tags": [
        "div.spmm-tag-list",
        "ul.tag-list",
        "ul.tags",
        "ul.tag",
        "meta[name='keywords']::attr(content)"
    ],
    "publish_date": [
        "meta[property='article:published_time']::attr(content)",
        "time::attr(datetime)",
        "span.date::text",
        "div.date::text"
    ],
}

def clean_text(text: str) -> str:
    """پاکسازی فاصله‌های اضافی و یکپارچه‌سازی متن"""
    if not text: 
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def get_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    with httpx.Client(headers=headers, timeout=10.0, follow_redirects=True) as client:
        try:
            r = client.get(url)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"Error fetching: {e}")
            return ""

def smart_extract(html: str) -> dict:
  
    if not html: 
        return {}
    
    sel = Selector(text=html)
    results = {}

    for field, hints in FIELD_HINTS.items():
        results[field] = None
        
        for css in hints:
            # جدا کردن بخش اصلی سلکتور از بخش استخراج (مثلا ::text)
            base_css = css.split("::")[0]
            
            if sel.css(base_css):
                if field == "body_text":
                    # استخراج عمیق برای متن اصلی خبر
                    parts = sel.css(f"{base_css} *::text").getall()
                    value = " ".join([clean_text(p) for p in parts if p.strip()])
                else:
                    # استخراج مقدار (متن یا اتریبیوت)
                    value = clean_text(sel.css(css).get())
                
                if value:
                    results[field] = value
                    break # پیدا شد، برو سراغ فیلد بعدی
                    
    return results

if __name__ == "__main__":
    test_url = "https://donya-e-eqtesad.com/%D8%A8%D8%AE%D8%B4-%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%DA%A9%D9%84%D8%A7%D9%86-184/4255131-%D8%B1%DA%A9%D9%88%D8%B1%D8%AF%D9%87%D8%A7%DB%8C-%D8%AC%D8%AF%DB%8C%D8%AF-%D8%A2%D9%85%D8%A7%D8%B1-%D9%BE%D9%88%D9%84%DB%8C"
    
    html_content = get_html(test_url)
    final_result = smart_extract(html_content)
    
    # ذخیره در فایل JSONL
    if any(final_result.values()):
        with open("extracted_data.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(final_result, ensure_ascii=False) + "\n")
        print("Data extracted successfully.✅")
    else:
        print("Could not extract any data.❌")