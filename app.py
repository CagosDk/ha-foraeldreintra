from flask import Flask, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import time
import os

SCHOOL_URL = "https://holbaekrealskolen.m.skoleintra.dk"

USERNAME = os.getenv("SKOLE_USERNAME", "")
PASSWORD = os.getenv("SKOLE_PASSWORD", "")

CACHE_TTL = 300  # 5 minutter

app = Flask(__name__)

cache_data = None
cache_timestamp = 0


def parse_lektier(html):
    soup = BeautifulSoup(html, "html.parser")
    lektier = []

    for li in soup.select("ul.sk-list > li"):
        dato_tag = li.find("b")
        dato = dato_tag.get_text(strip=True).replace(":", "") if dato_tag else ""

        user_input = li.select_one(".sk-user-input")
        if not user_input:
            continue

        tekst = user_input.get_text("\n", strip=True)

        strong = user_input.find("strong")
        fag = strong.get_text(strip=True).replace(":", "") if strong else ""

        lektier.append({
            "dato": dato,
            "fag": fag,
            "tekst": tekst
        })

    return lektier


def scrape_lektier():
    resultat = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(SCHOOL_URL)
        page.wait_for_selector("input[name='UserName']")
        page.fill("input[name='UserName']", USERNAME)
        page.fill("input[name='Password']", PASSWORD)
        page.click("input[type='submit']")
        page.wait_for_url("**/parent/**", timeout=15000)

        homepage_html = page.content()

        children = re.findall(
            r'href="/parent/(\d+)/([^/]+)/Index"',
            homepage_html
        )

        children = list(set(children))

        for parent_id, barn_navn in children:

            resultat[barn_navn] = []

            diary_url = (
                f"{SCHOOL_URL}/parent/{parent_id}/"
                f"{barn_navn}item/weeklyplansandhomework/diary"
            )

            page.goto(diary_url)
            page.wait_for_load_state("networkidle")

            diary_html = page.content()

            match = re.search(
                r'/weeklyplansandhomework/diary/(\d+)',
                diary_html
            )

            if not match:
                continue

            diary_id = match.group(1)

            notes_url = (
                f"{SCHOOL_URL}/parent/{parent_id}/"
                f"{barn_navn}item/weeklyplansandhomework/"
                f"diary/notes/{diary_id}"
            )

            page.goto(notes_url)
            page.wait_for_load_state("networkidle")

            html = page.content()

            lektier = parse_lektier(html)
            resultat[barn_navn] = lektier

        browser.close()

    return resultat


@app.route("/lektier")
def get_lektier():
    global cache_data, cache_timestamp

    if cache_data and (time.time() - cache_timestamp < CACHE_TTL):
        return jsonify(cache_data)

    cache_data = scrape_lektier()
    cache_timestamp = time.time()

    return jsonify(cache_data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
