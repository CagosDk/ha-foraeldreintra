import requests
from bs4 import BeautifulSoup


def hent_lektier(username, password, school_url):
    """
    Logger ind på ForældreIntra og returnerer
    en dict med antal lektier pr barn.
    """

    session = requests.Session()

    # 1️⃣ Login
    login_data = {
        "UserName": username,
        "Password": password,
    }

    login_url = school_url

    response = session.post(login_url, data=login_data)

    if response.status_code != 200:
        return {"Fejl": "Login fejlede"}

    # 2️⃣ Gå til forside efter login
    response = session.get(school_url)

    soup = BeautifulSoup(response.text, "html.parser")

    # DEBUG: find links til børn
    children = {}

    for link in soup.find_all("a", href=True):
        if "/parent/" in link["href"] and "Index" in link["href"]:
            navn = link.text.strip()
            children[navn] = link["href"]

    result = {}

    for navn, path in children.items():
        # Her skal vi senere hente diary
        result[navn] = "Fundet barn (ikke implementeret endnu)"

    return result
