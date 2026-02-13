import requests
from bs4 import BeautifulSoup


def hent_lektier(username, password, school_url):
    session = requests.Session()

    # 1️⃣ Hent login-side først (vigtigt!)
    login_page = session.get(school_url)
    soup = BeautifulSoup(login_page.text, "html.parser")

    # Find hidden inputs
    hidden_fields = {}
    for hidden in soup.find_all("input", type="hidden"):
        hidden_fields[hidden.get("name")] = hidden.get("value")

    # 2️⃣ Byg login payload korrekt
    payload = {
        "UserName": username,
        "Password": password,
    }

    payload.update(hidden_fields)

    # 3️⃣ Post login
    response = session.post(school_url, data=payload)

    # DEBUG
    if "Log ud" not in response.text and "Logout" not in response.text:
        return {"Fejl": "Login fejlede - mulig CSRF eller forkert form action"}

    return {"Login": "Virker"}
