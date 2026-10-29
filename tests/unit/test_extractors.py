"""Unit tests for price extractors (JSON-LD, Meta, CSS, and extraction chain)."""

from pathlib import Path

from tracker.extractors import (
    CssExtractor,
    JsonLdExtractor,
    MetaExtractor,
    extract_price,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "html"


def read_fixture(name: str) -> str:
    """Read an HTML fixture file."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestJsonLdExtractor:
    """Tests for the JSON-LD schema.org/Product price extractor."""

    def test_extract_basic_product(self):
        html = read_fixture("product_jsonld.html")
        result = JsonLdExtractor().extract(html, "https://example.com/sony-xm5")

        assert result is not None
        assert result.price == 199.00
        assert result.currency == "EUR"
        assert result.name == "Sony WH-1000XM5"
        assert result.in_stock is True
        assert result.method == "json-ld"

    def test_extract_multiple_offers_picks_lowest(self):
        html = read_fixture("product_jsonld_multiple_offers.html")
        result = JsonLdExtractor().extract(html, "https://example.com/macbook-air")

        assert result is not None
        assert result.price == 1199.00
        assert result.currency == "EUR"
        assert result.name == "Apple MacBook Air 13-inch M3"
        assert result.method == "json-ld"

    def test_extract_graph_structure(self):
        html = read_fixture("product_jsonld_graph.html")
        result = JsonLdExtractor().extract(html, "https://example.com/mx-master")

        assert result is not None
        assert result.price == 89.90
        assert result.currency == "EUR"
        assert result.name == "Logitech MX Master 3S Performance Wireless Mouse"
        assert result.method == "json-ld"

    def test_extract_out_of_stock(self):
        html = read_fixture("product_out_of_stock.html")
        result = JsonLdExtractor().extract(html, "https://example.com/rtx-4090")

        assert result is not None
        assert result.price == 1899.00
        assert result.in_stock is False

    def test_returns_none_when_no_price(self):
        html = read_fixture("product_no_price.html")
        result = JsonLdExtractor().extract(html, "https://example.com/blog")

        assert result is None


class TestMetaExtractor:
    """Tests for HTML meta and Open Graph tags extractor."""

    def test_extract_from_product_meta(self):
        html = read_fixture("product_meta.html")
        result = MetaExtractor().extract(html, "https://example.com/dell-monitor")

        assert result is not None
        assert result.price == 549.99
        assert result.currency == "EUR"
        assert result.name == "Dell UltraSharp 27 4K USB-C Hub Monitor (U2723QE)"
        assert result.method == "meta"

    def test_returns_none_when_no_meta_price(self):
        html = read_fixture("product_no_price.html")
        result = MetaExtractor().extract(html, "https://example.com/blog")

        assert result is None


class TestCssExtractor:
    """Tests for custom CSS selector extractor."""

    def test_extract_with_css_selector(self):
        html = read_fixture("product_css.html")
        result = CssExtractor().extract(
            html,
            "https://example.com/galaxy-s24",
            css_selector=".price",
        )

        assert result is not None
        assert result.price == 1299.00
        assert result.currency == "EUR"
        assert result.method == "css"

    def test_returns_none_when_selector_not_found(self):
        html = read_fixture("product_css.html")
        result = CssExtractor().extract(
            html,
            "https://example.com/galaxy-s24",
            css_selector=".non-existent-selector",
        )

        assert result is None

    def test_returns_none_when_no_selector_provided(self):
        html = read_fixture("product_css.html")
        result = CssExtractor().extract(html, "https://example.com/galaxy-s24")

        assert result is None


class TestExtractionChain:
    """Tests for the full extraction chain: JSON-LD -> Meta -> CSS."""

    def test_prefers_jsonld_over_meta(self):
        # Combined HTML with both JSON-LD and meta tags
        html = """
        <html>
        <head>
            <meta property="product:price:amount" content="250.00">
            <meta property="product:price:currency" content="EUR">
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Combined Product",
                "offers": {"@type": "Offer", "price": "199.00", "priceCurrency": "EUR"}
            }
            </script>
        </head>
        </html>
        """
        result = extract_price(html, "https://example.com/product")
        assert result is not None
        assert result.method == "json-ld"
        assert result.price == 199.00

    def test_falls_back_to_meta_when_jsonld_missing(self):
        html = read_fixture("product_meta.html")
        result = extract_price(html, "https://example.com/product")
        assert result is not None
        assert result.method == "meta"
        assert result.price == 549.99

    def test_falls_back_to_css_when_jsonld_and_meta_missing(self):
        html = read_fixture("product_css.html")
        result = extract_price(
            html, "https://example.com/product", css_selector=".price"
        )
        assert result is not None
        assert result.method == "css"
        assert result.price == 1299.00

    def test_returns_none_when_all_fail(self):
        html = read_fixture("product_no_price.html")
        result = extract_price(
            html, "https://example.com/product", css_selector=".price"
        )
        assert result is None
