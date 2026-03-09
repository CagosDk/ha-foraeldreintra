from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession
from bs4 import BeautifulSoup, Tag


class ForaldreIntraAuthError(Exception):
    """Login/auth fejl."""


class ForaldreIntraError(Exception):
    """Generel fejl."""


@dataclass
class Child:
    id: str
    name: str


class ForaldreIntraClient:
    """Async klient til ForældreIntra/SkoleIntra mobilsite."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        school_url: str,
    ) -> None:
        if not username or not password or not school_url:
            raise ValueError("Mangler username/password/school_url")

        self._session = session
        self._username = username
        self._password = password
        self._base_url = school_url.rstrip("/")
        self._login_url = f"{self._base_url}/Account/IdpLogin"
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Home Assistant ForaldreIntra)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        self._home_html: str | None = None
        self._home_url: str | None = None

    async def login(self) -> None:
        """Login og cache den første parent-side vi lander på."""
        async with self._session.get(
            self._login_url,
            headers=self._headers,
            allow_redirects=True,
        ) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise ForaldreIntraAuthError(f"Login-side fejlede: HTTP {resp.status}")

        soup = BeautifulSoup(text, "html.parser")
        token_input = soup.find("input", {"name": "__RequestVerificationToken"})
        token = token_input.get("value") if token_input else None
        if not token:
            raise ForaldreIntraAuthError(
                "Kunne ikke finde __RequestVerificationToken på login-siden"
            )

        payload = {
            "__RequestVerificationToken": token,
            "RoleType": "Parent",
            "UserName": self._username,
            "Password": self._password,
        }

        async with self._session.post(
            self._login_url,
            data=payload,
            headers=self._headers,
            allow_redirects=True,
        ) as resp:
            text2 = await resp.text()
            if resp.status >= 400:
                raise ForaldreIntraAuthError(f"Login POST fejlede: HTTP {resp.status}")

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
                raise ForaldreIntraAuthError(
                    f"Landede ikke på parent-side efter SAML. URL: {final_url}"
                )

            self._home_html = final_text
            self._home_url = final_url

    async def get_children(self) -> list[Child]:
        """Find børn ud fra URL og menu."""
        html, url = await self._get_home_html_and_url()
        soup = BeautifulSoup(html, "html.parser")

        children: list[Child] = []
        seen: set[tuple[str, str]] = set()

        active_match = re.search(r"/parent/(\d+)/([^/]+)/", url or "")
        if active_match:
            child_id = active_match.group(1)
            child_name = self._clean_child_name(active_match.group(2))
            key = (child_id, child_name)
            if key not in seen:
                seen.add(key)
                children.append(Child(id=child_id, name=child_name))

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
                child_name = self._clean_child_name(m.group(2))
                key = (child_id, child_name)
                if key not in seen:
                    seen.add(key)
                    children.append(Child(id=child_id, name=child_name))

        return children

    async def get_homework(self) -> list[dict[str, Any]]:
        """Henter lektier for alle børn."""
        children = await self.get_children()
        return await self.get_homework_for_children(children)

    async def get_homework_for_children(
        self,
        children: list[Child],
    ) -> list[dict[str, Any]]:
        """Henter lektier for en given liste af børn."""
        all_items: list[dict[str, Any]] = []

        for child in children:
            child_id = child.id
            child_name = child.name

            diary_url = (
                f"{self._base_url}/parent/{child_id}/{child_name}"
                "item/weeklyplansandhomework/diary"
            )
            diary_text = await self._get_text(diary_url)
            diary_id = self._extract_diary_id(diary_text)
            if not diary_id:
                continue

            notes_url = (
                f"{self._base_url}/parent/{child_id}/{child_name}"
                f"item/weeklyplansandhomework/diary/notes/{diary_id}"
            )
            notes_text = await self._get_text(notes_url)
            parsed = self._parse_homework_notes(notes_text)

            for item in parsed:
                item["barn"] = child_name
                item["dato"] = self._dk_date_to_iso(item.get("dato"))
                all_items.append(item)

        all_items.sort(
            key=lambda x: (
                x.get("dato") or "",
                x.get("barn") or "",
                x.get("fag") or "",
            )
        )
        return all_items

    async def get_weekplans_for_children(
        self,
        children: list[Child],
    ) -> dict[str, dict[str, Any]]:
        """Henter fuld ugeplan for hver valgt elev, baseret på nyeste publicerede ugeplan."""
        result: dict[str, dict[str, Any]] = {}

        for child in children:
            plan = await self.get_weekplan_for_child(child)
            if plan:
                result[child.name] = plan

        return result

    async def get_latest_weekplans_for_children(
        self,
        children: list[Child],
    ) -> list[dict[str, Any]]:
        """Beholdes for bagudkompatibilitet."""
        result: list[dict[str, Any]] = []
        plans = await self.get_weekplans_for_children(children)

        for child_name, plan in plans.items():
            result.append(
                {
                    "barn": child_name,
                    "weekplan_id": plan.get("week"),
                    "title": plan.get("title"),
                    "url": plan.get("url"),
                }
            )

        return result

    async def get_weekplan_for_child(self, child: Child) -> dict[str, Any] | None:
        """Henter og parser den nyeste publicerede ugeplan for ét barn."""
        latest = await self.get_latest_weekplan_info_for_child(child)
        if not latest:
            return None

        html = await self._get_text(latest["url"])
        parsed = self._parse_weekplan_page(
            html=html,
            weekplan_id=latest["weekplan_id"],
            fallback_title=latest["title"],
            url=latest["url"],
        )
        parsed["barn"] = child.name
        return parsed

    async def get_latest_weekplan_info_for_child(
        self,
        child: Child,
    ) -> dict[str, Any] | None:
        """Finder nyeste publicerede ugeplan for ét barn via /list-siden."""
        list_url = (
            f"{self._base_url}/parent/{child.id}/{child.name}"
            "item/weeklyplansandhomework/list"
        )
        list_html = await self._get_text(list_url)

        latest = self._extract_latest_weekplan_from_list(list_html)
        if not latest:
            return None

        href = latest["href"]
        if href.startswith("/"):
            full_url = f"{self._base_url}{href}"
        else:
            full_url = href

        return {
            "barn": child.name,
            "weekplan_id": latest["weekplan_id"],
            "title": latest["title"],
            "url": full_url,
        }

    async def _get_home_html_and_url(self) -> tuple[str, str]:
        if self._home_html and self._home_url:
            return self._home_html, self._home_url

        async with self._session.get(
            self._base_url,
            headers=self._headers,
            allow_redirects=True,
        ) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise ForaldreIntraError(f"Kunne ikke hente base url: HTTP {resp.status}")
            return text, str(resp.url)

    async def _get_text(self, url: str) -> str:
        async with self._session.get(
            url,
            headers=self._headers,
            allow_redirects=True,
        ) as resp:
            text = await resp.text()

            if resp.status in (401, 403):
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

    def _extract_latest_weekplan_from_list(self, html: str) -> dict[str, str] | None:
        """Finder første publicerede ugeplan på /weeklyplansandhomework/list."""
        soup = BeautifulSoup(html, "html.parser")

        container = soup.select_one("ul.sk-weekly-plans-list-container")
        if not container:
            return None

        first_link = container.select_one(
            "li a[href*='/weeklyplansandhomework/item/class/']"
        )
        if not first_link:
            return None

        href = (first_link.get("href") or "").strip()
        title = first_link.get_text(" ", strip=True)

        match = re.search(r"/item/class/(\d{2}-\d{4})", href)
        if not match:
            return None

        return {
            "weekplan_id": match.group(1),
            "href": href,
            "title": title,
        }

    def _parse_weekplan_page(
        self,
        html: str,
        weekplan_id: str,
        fallback_title: str,
        url: str,
    ) -> dict[str, Any]:
        """Parser ugeplansside til det format sensor.py forventer."""
        soup = BeautifulSoup(html, "html.parser")

        content_root = (
            soup.select_one("div.sk-l-content")
            or soup.select_one("div.sk-l-content-wrapper")
            or soup.body
            or soup
        )

        for tag in content_root.select("script, style, noscript"):
            tag.decompose()

        title = self._extract_weekplan_title(content_root) or fallback_title
        class_or_group = self._extract_class_or_group(content_root)
        days = self._extract_weekplan_days(content_root)
        items: list[dict[str, Any]] = []

        general_text = self._extract_general_weekplan_text(content_root)
        if general_text:
            items.append(
                {
                    "type": "general",
                    "subject": "Generelt",
                    "content_text": general_text,
                }
            )

        for day in days:
            for lesson in day.get("lesson_plans", []):
                items.append(
                    {
                        "type": "day",
                        "day": day.get("day"),
                        "formatted_date": day.get("formatted_date"),
                        "subject": lesson.get("subject"),
                        "content_text": lesson.get("content_text"),
                    }
                )

        return {
            "title": title,
            "week": weekplan_id,
            "url": url,
            "class_or_group": class_or_group,
            "items": items,
            "days": days,
        }

    def _extract_weekplan_title(self, root: Tag) -> str | None:
        for selector in ("h1", "h2", ".sk-page-header", ".sk-page-title"):
            el = root.select_one(selector)
            if el:
                text = self._clean_text(el.get_text(" ", strip=True))
                if text:
                    return text
        return None

    def _extract_class_or_group(self, root: Tag) -> str | None:
        txt = self._clean_text(root.get_text(" ", strip=True))
        m = re.search(r"\b(\d{1,2}[A-ZÆØÅa-zæøå])\b", txt)
        if m:
            return m.group(1)
        return None

    def _extract_general_weekplan_text(self, root: Tag) -> str:
        """Forsøger at finde den generelle tekst i ugeplanen."""
        candidates: list[str] = []

        selectors = [
            ".sk-user-input",
            ".sk-white-box",
            ".sk-week-plan-content",
            ".sk-weekly-plan-content",
        ]

        for selector in selectors:
            for el in root.select(selector):
                text = self._clean_multiline_text(el.get_text("\n", strip=True))
                if text and len(text) > 30:
                    candidates.append(text)

        if candidates:
            best = max(candidates, key=len)
            return best

        return ""

    def _extract_weekplan_days(self, root: Tag) -> list[dict[str, Any]]:
        days: list[dict[str, Any]] = []

        day_headers = []
        weekday_re = re.compile(
            r"^(Mandag|Tirsdag|Onsdag|Torsdag|Fredag|Lørdag|Søndag)\b",
            re.IGNORECASE,
        )

        for el in root.find_all(["h2", "h3", "h4", "strong", "b"]):
            text = self._clean_text(el.get_text(" ", strip=True))
            if weekday_re.match(text):
                day_headers.append(el)

        seen_headers: set[str] = set()

        for header in day_headers:
            header_text = self._clean_text(header.get_text(" ", strip=True))
            if not header_text or header_text in seen_headers:
                continue
            seen_headers.add(header_text)

            day_name, formatted_date = self._split_day_header(header_text)
            section_nodes = self._collect_until_next_day_header(header, weekday_re)

            lesson_plans: list[dict[str, Any]] = []
            schedule: list[dict[str, Any]] = []

            section_texts: list[str] = []
            for node in section_nodes:
                if getattr(node, "name", None) == "table":
                    schedule.extend(self._parse_schedule_table(node))
                else:
                    txt = self._clean_multiline_text(node.get_text("\n", strip=True))
                    if txt:
                        section_texts.append(txt)

            merged_text = "\n\n".join(t for t in section_texts if t).strip()
            if merged_text:
                lesson_plans.append(
                    {
                        "subject": "Generelt",
                        "content_text": merged_text,
                    }
                )

            if lesson_plans or schedule:
                days.append(
                    {
                        "day": day_name,
                        "formatted_date": formatted_date,
                        "lesson_plans": lesson_plans,
                        "schedule": schedule,
                    }
                )

        if days:
            return days

        schedule_tables = root.find_all("table")
        flat_schedule: list[dict[str, Any]] = []
        for table in schedule_tables:
            flat_schedule.extend(self._parse_schedule_table(table))

        if flat_schedule:
            days.append(
                {
                    "day": "",
                    "formatted_date": "",
                    "lesson_plans": [],
                    "schedule": flat_schedule,
                }
            )

        return days

    def _collect_until_next_day_header(self, header: Tag, weekday_re: re.Pattern[str]) -> list[Tag]:
        nodes: list[Tag] = []
        node = header.parent if header.parent and header.parent != header else header

        current = node.find_next_sibling()
        while current:
            text = self._clean_text(current.get_text(" ", strip=True))
            if current.name in ("h2", "h3", "h4", "strong", "b") and weekday_re.match(text):
                break

            inner_header = current.find(["h2", "h3", "h4", "strong", "b"])
            if inner_header:
                inner_text = self._clean_text(inner_header.get_text(" ", strip=True))
                if weekday_re.match(inner_text):
                    break

            if isinstance(current, Tag):
                nodes.append(current)

            current = current.find_next_sibling()

        return nodes

    def _parse_schedule_table(self, table: Tag) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []

        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            values = [self._clean_text(c.get_text(" ", strip=True)) for c in cells]
            values = [v for v in values if v]

            if len(values) < 2:
                continue

            time_str = ""
            subject_short = ""
            subject_full = ""
            title = ""

            if re.match(r"^\d{1,2}[:.]\d{2}", values[0]):
                time_str = values[0]
                if len(values) >= 2:
                    subject_short = values[1]
                if len(values) >= 3:
                    subject_full = values[2]
                if len(values) >= 4:
                    title = values[3]
            else:
                subject_short = values[0]
                if len(values) >= 2:
                    subject_full = values[1]
                if len(values) >= 3:
                    title = values[2]

            if time_str or subject_short or subject_full or title:
                rows.append(
                    {
                        "time": time_str,
                        "subject_short": subject_short,
                        "subject_full": subject_full,
                        "title": title,
                    }
                )

        return rows

    def _split_day_header(self, text: str) -> tuple[str, str]:
        text = self._clean_text(text)
        m = re.match(
            r"^(Mandag|Tirsdag|Onsdag|Torsdag|Fredag|Lørdag|Søndag)\s*(.*)$",
            text,
            re.IGNORECASE,
        )
        if not m:
            return text, ""

        day = m.group(1).capitalize()
        rest = (m.group(2) or "").strip(" -–—")
        return day, rest

    def _clean_child_name(self, name: str) -> str:
        """Fjern evt. 'item' suffix fra barnets navn i URL."""
        n = (name or "").strip()
        if n.lower().endswith("item"):
            n = n[:-4]
        return n

    def _clean_text(self, txt: str) -> str:
        return (txt or "").replace("\xa0", " ").strip()

    def _clean_multiline_text(self, txt: str) -> str:
        lines = [self._clean_text(line) for line in (txt or "").splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines).strip()

    def _parse_homework_notes(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        result: list[dict[str, Any]] = []

        def clean_text(txt: str) -> str:
            return (txt or "").replace("\xa0", " ").strip()

        def normalize_subject(s: str) -> str:
            s = (s or "").strip().replace(":", "")
            if not s:
                return ""
            return s.lower().capitalize()

        def ensure_subject(s: str | None) -> str:
            s2 = normalize_subject(s or "")
            return s2 if s2 else "Ukendt"

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

            for node in content_div.children:
                if getattr(node, "name", None) is None:
                    continue

                strong = node.find("strong") if hasattr(node, "find") else None
                if strong:
                    fag_txt = normalize_subject(clean_text(strong.get_text(strip=True)))
                    if fag_txt:
                        current_fag = fag_txt
                        ensure_block(current_fag)
                    strong.extract()

                for a in node.find_all("a"):
                    t = clean_text(a.get_text(strip=True)) or "link"
                    u = a.get("href")
                    ensure_block(current_fag)["links"].append(
                        {"tekst": t, "url": u}
                    )
                    a.extract()

                txt = clean_text(node.get_text(" ", strip=True))
                if txt:
                    ensure_block(current_fag)["lines"].append(txt)

            for fag, data in blocks.items():
                lines = data.get("lines") or []
                links = data.get("links") or []
                tekst = "\n".join(
                    [clean_text(x) for x in lines if clean_text(x)]
                ).strip()

                if not tekst and not links:
                    continue

                if (not fag or not str(fag).strip()) and tekst:
                    first_line = tekst.splitlines()[0].strip()
                    m = re.match(r"^([A-Za-zÆØÅæøå ]{2,30})\s*:\s*(.+)$", first_line)
                    if m:
                        guessed_fag = normalize_subject(m.group(1).strip())
                        rest = m.group(2).strip()
                        fag = guessed_fag
                        remaining_lines = tekst.splitlines()[1:]
                        tekst = "\n".join([rest] + remaining_lines).strip()

                fag_final = ensure_subject(str(fag) if fag is not None else None)

                result.append(
                    {
                        "dato": dato,
                        "fag": fag_final,
                        "tekst": tekst,
                        "links": links,
                    }
                )

        return result

    def _dk_date_to_iso(self, date_str: str | None) -> str | None:
        if not date_str:
            return None

        s = date_str.strip()
        if "," in s:
            s = s.split(",", 1)[1].strip()

        m = re.match(r"^(\d{1,2})\.\s*([A-Za-zæøåÆØÅ\.]+)\s+(\d{4})$", s)
        if not m:
            return date_str

        day = int(m.group(1))
        mon_raw = m.group(2).lower().replace(".", "").strip()
        year = int(m.group(3))

        months = {
            "jan": 1,
            "januar": 1,
            "feb": 2,
            "februar": 2,
            "mar": 3,
            "marts": 3,
            "apr": 4,
            "april": 4,
            "maj": 5,
            "jun": 6,
            "juni": 6,
            "jul": 7,
            "juli": 7,
            "aug": 8,
            "august": 8,
            "sep": 9,
            "september": 9,
            "okt": 10,
            "oktober": 10,
            "nov": 11,
            "november": 11,
            "dec": 12,
            "december": 12,
        }

        month = months.get(mon_raw)
        if not month:
            return date_str

        return f"{year:04d}-{month:02d}-{day:02d}"
