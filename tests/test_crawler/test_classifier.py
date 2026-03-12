"""Tests for the pattern classifier."""

from humanization.crawler.classifier import classify_target


def test_classify_table_keywords():
    assert classify_target("extract table data") == "table_data"


def test_classify_table_multiple_keywords():
    assert classify_target("get all table rows and columns") == "table_data"


def test_classify_product_keywords():
    assert classify_target("all product prices") == "product_listing"


def test_classify_product_shop():
    assert classify_target("shop items catalog") == "product_listing"


def test_classify_article_keywords():
    assert classify_target("article text and author") == "article_content"


def test_classify_article_blog():
    assert classify_target("blog post content") == "article_content"


def test_classify_link_keywords():
    assert classify_target("all links on page") == "link_list"


def test_classify_link_navigation():
    assert classify_target("navigation menu urls") == "link_list"


def test_classify_generic_fallback():
    assert classify_target("xyz123 foobar") == "generic"


def test_classify_empty_string():
    assert classify_target("") == "generic"


def test_classify_case_insensitive():
    assert classify_target("TABLE DATA") == "table_data"


def test_classify_mixed_keywords_picks_highest():
    # "product" and "price" = 2 hits for product_listing
    # "table" = 1 hit for table_data
    assert classify_target("product price table") == "product_listing"
