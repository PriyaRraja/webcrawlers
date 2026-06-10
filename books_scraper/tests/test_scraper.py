import pytest
from bs4 import BeautifulSoup

from scraper import parse_book, RATING_MAP


def make_card(
    title: str = "A Great Book",
    price: str = "£12.99",
    rating_class: str = "Three",
    availability: str = "In stock",
) -> BeautifulSoup:
    html = f"""
    <article class="product_pod">
        <h3><a href="catalogue/book.html" title="{title}">A Great Bo...</a></h3>
        <p class="price_color">{price}</p>
        <p class="star-rating {rating_class}"></p>
        <p class="availability">{availability}</p>
    </article>
    """
    soup = BeautifulSoup(html, "lxml")
    return soup.select_one("article.product_pod")


# ── Normal parsing ─────────────────────────────────────────────────────────────

def test_parse_book_title():
    assert parse_book(make_card(title="Sharp Objects"))["Title"] == "Sharp Objects"


def test_parse_book_price():
    assert parse_book(make_card(price="£47.82"))["Price"] == pytest.approx(47.82)


def test_parse_book_availability():
    assert parse_book(make_card(availability="In stock"))["Availability"] == "In stock"


# ── All five rating values ─────────────────────────────────────────────────────

@pytest.mark.parametrize("word,expected", list(RATING_MAP.items()))
def test_parse_book_all_ratings(word, expected):
    assert parse_book(make_card(rating_class=word))["Rating"] == expected


# ── Price edge cases ───────────────────────────────────────────────────────────

def test_price_strips_pound_symbol():
    assert parse_book(make_card(price="£9.99"))["Price"] == pytest.approx(9.99)


def test_price_with_encoding_artifact():
    assert parse_book(make_card(price="Â£51.77"))["Price"] == pytest.approx(51.77)


def test_price_invalid_text_defaults_to_zero():
    card = make_card()
    price_el = card.select_one("p.price_color")
    price_el.string = "N/A"
    assert parse_book(card)["Price"] == 0.0


def test_price_empty_text_defaults_to_zero():
    card = make_card()
    price_el = card.select_one("p.price_color")
    price_el.string = ""
    assert parse_book(card)["Price"] == 0.0


# ── Missing element fallbacks ──────────────────────────────────────────────────

def test_missing_anchor_gives_empty_title():
    html = """
    <article class="product_pod">
        <h3></h3>
        <p class="price_color">£10.00</p>
        <p class="star-rating Two"></p>
        <p class="availability">In stock</p>
    </article>
    """
    card = BeautifulSoup(html, "lxml").select_one("article.product_pod")
    assert parse_book(card)["Title"] == ""


def test_missing_price_element_defaults_to_zero():
    html = """
    <article class="product_pod">
        <h3><a title="No Price Book">No Price Book</a></h3>
        <p class="star-rating Four"></p>
        <p class="availability">In stock</p>
    </article>
    """
    card = BeautifulSoup(html, "lxml").select_one("article.product_pod")
    assert parse_book(card)["Price"] == 0.0


def test_missing_rating_element_defaults_to_one():
    html = """
    <article class="product_pod">
        <h3><a title="No Rating Book">No Rating Book</a></h3>
        <p class="price_color">£20.00</p>
        <p class="availability">In stock</p>
    </article>
    """
    card = BeautifulSoup(html, "lxml").select_one("article.product_pod")
    assert parse_book(card)["Rating"] == 1


def test_missing_availability_element_defaults_to_unknown():
    html = """
    <article class="product_pod">
        <h3><a title="No Avail Book">No Avail Book</a></h3>
        <p class="price_color">£15.00</p>
        <p class="star-rating Three"></p>
    </article>
    """
    card = BeautifulSoup(html, "lxml").select_one("article.product_pod")
    assert parse_book(card)["Availability"] == "Unknown"


def test_unknown_rating_word_defaults_to_one():
    card = make_card(rating_class="Six")
    assert parse_book(card)["Rating"] == 1


def test_rating_element_with_only_one_class_defaults_to_one():
    html = """
    <article class="product_pod">
        <h3><a title="Odd Book">Odd Book</a></h3>
        <p class="price_color">£5.00</p>
        <p class="star-rating"></p>
        <p class="availability">In stock</p>
    </article>
    """
    card = BeautifulSoup(html, "lxml").select_one("article.product_pod")
    assert parse_book(card)["Rating"] == 1


# ── Return shape ───────────────────────────────────────────────────────────────

def test_parse_book_returns_all_keys():
    result = parse_book(make_card())
    assert set(result.keys()) == {"Title", "Price", "Rating", "Availability"}
