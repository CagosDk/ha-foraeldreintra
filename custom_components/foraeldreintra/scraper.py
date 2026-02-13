import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def hent_lektier(username, password, school_url):
    session = requests.Session()

    # 1️⃣ Hent login-side
    login_page = session.get(school_url)
    soup = BeautifulSoup(login_page.text, "html.parser")

    # Find login form
    form = soup.find("form")
    if not form:
        return {"Fejl": "Login form ikke fundet"}

    action = form.get("action")
    login_url = urljoin(school_url, action)

    # Hent alle hidden fields
    payload = {}
    for input_tag in form.find_all("input"):
        name = input_tag.get("name")
        value = input_tag.get("value", "")
        if name:
            payload[name] = value

    # Indsæt credentials korrekt
    payload["UserName"] = username
    payload["Password"] = password

    # 2️⃣ Send login request til korrekt endpoint
    response = session.post(login_url, data=payload)

    # 3️⃣ Tjek om login lykkedes
    if "Log ud" not in response.text and "Logout" not in response.text:
        return {"Fejl": f"Login fejlede (POST til {login_url})"}

    return {"Login": "Virker"}
