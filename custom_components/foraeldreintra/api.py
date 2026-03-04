from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession
from bs4 import BeautifulSoup


class ForaldreIntraAuthError(Exception):
    """Login/auth fejl."""


class ForaldreIntraError(Exception):
    """Generel fejl."""


@dataclass
class Child:
    id: str
    name: str


class ForaldreIntraClient:
    def __init__(self, session: ClientSession, username: str, password: str, school_url: str) -> None:
        if not username or not password or not school_url:
            raise ValueError("Mangler username/password/school_url")

        self._session = session
        self._username = username
        self._password = password
        self._base_url = school_url.rstrip("/")
        self._login_url = f"{self._base_url}/Account/IdpLogin"

        self._headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        self._home_html: str | None = None
        self._home_url: str | None = None

    async def login(self) -> None:
        # 1) GET login side (hent __RequestVerificationToken)
        async with self._session.get(self._login_url, headers=self._headers, allow_redirects=True) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise ForaldreIntraAuthError(f"Login-side fejlede: HTTP {resp.status}")

        soup = BeautifulSoup(text, "html.parser")
        token_input = soup.find("input", {"name": "__RequestVerificationToken"})
        token = token_input.get("value") if token_input else None
        if not token:
            raise ForaldreIntraAuthError("Kunne ikke finde __RequestVerificationToken på login-siden")

        payload = {
            "__RequestVerificationToken": token,
            "RoleType": "Parent",
            "UserName": self._username,
            "Password": self._password,
        }

        # 2) POST credentials
        async with self._session.post(
            self._login_url,
            data=payload,
            headers=self._headers,
            allow_redirects=True,
        ) as resp:
            text2 = await resp.text()
            if resp.status >= 400:
                raise ForaldreIntraAuthError(f"Login POST fejlede: HTTP {resp.status}")

        # 3) SAML form (typisk)
        soup2 = BeautifulSoup(text2, "html.parser")
        saml_form = soup2.find("form")
        if not saml_form:
            raise ForaldreIntraAuthError("Ingen SAML form fundet efter login POST")

        action_url = saml_form.get("action")
        if not action_url:
            raise ForaldreIntraAuthError("SAML form mangler action")

        form_data: dict[str, str] = {}
        for input_tag in saml_form.find_all("input"):
            name = input_tag.get("name")
            value = input_tag.get("value", "")
            if name:
                form_data[name] = value

        async with self._session.post(
            action_url,
            data=form_data,
            headers=self._headers,
            allow_redirects=True,
        ) as resp:
            final_text = await resp.text()
            final_url = str(resp.url)
            if resp.status >= 400:
                raise ForaldreIntraAuthError(f"SAML POST fejlede: HTTP {resp.status}")

        if "/parent/" not in final_url:
            raise ForaldreIntraAuthError(f"Landede ikke på parent-side efter SAML. URL: {final_url}")

        self._home_html = final_text
        self._home_url = final_url

    async def get_children(self) -> list[Child]:
        html, url = await self._get_home_html_and_url()
        soup = BeautifulSoup(html, "html.parser")

        children: list[Child] = []
        seen: set[tuple[str, str]] = set()

        # aktivt barn fra URL
        active_match = re.search(r"/parent/(\d+)/([^/]+)/", url or "")
        if active_match:
            child_id = active_match.group(1)
            child_name = active_match.group(2)
            key = (child_id, child_name)
            if key not in seen:
                seen.add(key)
                children.append(Child(id=child_id, name=child_name))

        # menu med børn
        menu = soup.find("div", id="sk-personal-menu-container")
        if menu:
            for link in menu.find_all("a", href=True):
                href = link["href"]
                m = re.search(r"/parent/(\d+)/([^/]+)/", href)
                if not m:
                    continue
                if "settings" in href.lower():
                    continue
                child_id = m.group(1)
                child_name = m.group(2)
                key = (child_id, child_name)
                if key not in seen:
                    seen.add(key)
                    children.append(Child(id=child_id, name=child_name))

        return children

    async def get_homework(self) -> list[dict[str, Any]]:
        children = await self.get_children()
        all_items: list[dict[str, Any]] = []

        for child in children:
            child_id = child.id
            child_name = child.name

            # NB: i dit fungerende projekt havde du ".../{child_name}item/..."
            # Vi bevarer præcis samme mønster her.
            diary_url = f"{self._base_url}/parent/{child_id}/{child_name}item/weeklyplansandhomework/diary"
            diary_text = await self._get_text(diary_url)

            diary_id = self._extract_diary_id(diary_text)
            if not diary_id:
                continue

            notes_url = (
                f"{self._base_url}/parent/{child_id}/{child_name}item/weeklyplansandhomework/diary/notes/{diary_id}"
            )
            notes_text = await self._get_text(notes_url)

            parsed = self._parse_lektier(notes_text)
            for item in parsed:
                item["barn"] = child_name
                item["dato"] = self._dk_date_to_iso(item.get("dato"))
                all_items.append(item)

        all_items.sort(key=lambda x: (x.get("dato") or "", x.get("barn") or "", x.get("fag") or ""))
        return all_items

    async def _get_home_html_and_url(self) -> tuple[str, str]:
        if self._home_html and self._home_url:
            return self._home_html, self._home_url

        async with self._session.get(self._base_url, headers=self._headers, allow_redirects=True) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise ForaldreIntraError(f"Kunne ikke hente base url: HTTP {resp.status}")
            return text, str(resp.url)

    async def _get_text(self, url: str) -> str:
        async with self._session.get(url, headers=self._headers, allow_redirects=True) as resp:
            text = await resp.text()
            if resp.status == 401 or resp.status == 403:
                raise ForaldreIntraAuthError(f"Adgang nægtet: {url}")
            if resp.status >= 400:
                raise ForaldreIntraError(f"HTTP {resp.status} ved hentning: {url}")
            return text

    def _extract_diary_id(self, html: str) -> str | None:
        m = re.search(r"weeklyplansandhomework/diary/(\d+)", html)
        if m:
            return m.group(1)

        m = re.search(r"diary/(\d+)(?:/|\"|'|\?)", html)
        if m:
            return m.group(1)

        return None

    def _parse_lektier(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        result: list[dict[str, Any]] = []

        def clean_text(txt: str) -> str:
            return (txt or "").replace("\xa0", " ").strip()

        for li in soup.select("ul.sk-list > li"):
            dato_tag = li.select_one("div.sk-white-box > b")
            content_div = li.select_one("div.sk-user-input")
            if not dato_tag or not content_div:
                continue

            dato = dato_tag.get_text(strip=True).replace(":", "").strip()

            current_fag: str | None = None
            blocks: dict[str | None, dict[str, Any]] = {}

            def ensure_block(fag: str | None) -> dict[str, Any]:
                if fag not in blocks:
                    blocks[fag] = {"lines": [], "links": []}
                return blocks[fag]

            for child in content_div.children:
                if getattr(child, "name", None) is None:
                    continue

                strong = child.find("strong") if hasattr(child, "find") else None
                if strong:
                    fag_txt = clean_text(strong.get_text(strip=True)).replace(":", "")
                    if fag_txt:
                        current_fag = fag_txt
                        ensure_block(current_fag)
                    strong.extract()

                for a in child.find_all("a"):
                    t = clean_text(a.get_text(strip=True)) or "link"
                    u = a.get("href")
                    ensure_block(current_fag)["links"].append({"tekst": t, "url": u})
                    a.extract()

                if child.name == "ul
