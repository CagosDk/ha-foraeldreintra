from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from html import unescape
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
    """
    Async klient til ForældreIntra/SkoleIntra mobilsite.

    Flow:
    - GET /Account/IdpLogin (hent __RequestVerificationToken)
    - POST credentials
    - Find og POST SAML-form (action + hidden inputs)
    - Land på /parent/{childId}/{childName}/...
    - Find børn i menu + fra URL
    - For hvert barn: hent diary, find diary_id, hent notes, parse lektier
    - For hvert barn: prøv ugeplan for nyeste relevante uge
    """

    def __init__(self, session: ClientSession, username: str, password: str, school_url: str) -> None:
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
        """
        Find børn ud fra URL og menu.
        Hvis vi ikke er logget ind, kan listen være tom.
        """
        html, url = await self._get_home_html_and_url()
        soup = BeautifulSoup(html, "html.parser")

        children: list[Child] = []
        seen: set[tuple[str, str]] = set()

        active_match = re.search(r"/parent/(\d+)/([^/]+)/", url or "")
        if active_match:
            child_id = active_match.group(1)
            child_name = active_match.group(2)
            child_name = self._clean_child_name(child_name)
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

    async def get_homework_for_children(self, children: list[Child]) -> list[dict[str, Any]]:
        """Henter lektier for en given liste af børn."""
        all_items: list[dict[str, Any]] = []

        for child in children:
            child_id = child.id
            child_name = child.name

            diary_url = f"{self._base_url}/parent/{child_id}/{child_name}item/weeklyplansandhomework/diary"
            diary_text = await self._get_text(diary_url)

            diary_id = self._extract_diary_id(diary_text)
            if not diary_id:
                continue

            notes_url = (
                f"{self._base_url}/parent/{child_id}/{child_name}item/weeklyplansandhomework/diary/notes/{diary_id}"
            )
            notes_text = await self._get_text(notes_url)

            parsed = self._parse_homework_notes(notes_text)
            for item in parsed:
                item["barn"] = child_name
                item["dato"] = self._dk_date_to_iso(item.get("dato"))
                all_items.append(item)

        all_items.sort(key=lambda x: (x.get("dato") or "", x.get("barn") or "", x.get("fag") or ""))
        return all_items

    async def get_weekplans_for_children(self, children: list[Child]) -> dict[str, dict[str, Any]]:
        """Henter nyeste ugeplan for hver elev."""
        result: dict[str, dict[str, Any]] = {}

        for child in children:
            plan = await self.get_latest_weekplan_for_child(child)
            if plan:
                result[child.name] = plan

        return result

    async def get_latest_weekplan_for_child(self, child: Child) -> dict[str, Any] | None:
        """
        Prøver de mest relevante uge-nøgler og returnerer den nyeste tilgængelige ugeplan.
        Prøver næste uge først og derefter denne uge.
        """
        child_id = child.id
        child_name = child.name

        for week_key in self._candidate_week_keys():
            url = (
                f"{self._base_url}/parent/"
                f"{child_id}/{child_name}item/weeklyplansandhomework/item/class/{week_key}"
            )

            try:
                html = await self._get_text(url)
            except ForaldreIntraError:
                continue

            parsed = self._parse_weekplan(
                html=html,
                child_name=child_name,
                week_key=week_key,
                url=url,
            )
            if parsed:
                return parsed

        return None

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

    def _clean_child_name(self, name: str) -> str:
        n = (name or "").strip()
        if n.lower().endswith("item"):
            n = n[:-4]
        return n

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
                    ensure_block(current_fag)["links"].append({"tekst": t, "url": u})
                    a.extract()

                txt = clean_text(node.get_text(" ", strip=True))
                if txt:
                    ensure_block(current_fag)["lines"].append(txt)

            for fag, data in blocks.items():
                lines = data.get("lines") or []
                links = data.get("links") or []
                tekst = "\n".join([clean_text(x) for x in lines if clean_text(x)]).strip()

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

    def _week_key_for_date(self, d: date) -> str:
        iso_year, iso_week, _ = d.isocalendar()
        return f"{iso_week:02d}-{iso_year}"

    def _candidate_week_keys(self) -> list[str]:
        today = date.today()
        current_week = self._week_key_for_date(today)
        next_week = self._week_key_for_date(today + timedelta(days=7))

        keys: list[str] = []
        for key in [next_week, current_week]:
            if key not in keys:
                keys.append(key)
        return keys

    def _parse_weekplan(
        self,
        html: str,
        child_name: str,
        week_key: str,
        url: str,
    ) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one("#root")

        if not root:
            return None

        raw = root.get("data-clientlogic-settings-WeeklyPlansApp")
        if not raw:
            return None

        try:
            data = json.loads(raw)
        except Exception:
            return None

        selected = data.get("SelectedPlan") or {}
        if not selected:
            return None

        def clean_text(txt: str) -> str:
            return (txt or "").replace("\xa0", " ").strip()

        def html_to_text(fragment: str) -> str:
            if not fragment:
                return ""

            fragment = unescape(fragment)
            frag_soup = BeautifulSoup(fragment, "html.parser")

            for br in frag_soup.find_all("br"):
                br.replace_with("\n")

            lines: list[str] = []

            def parse_list(list_tag: Any, level: int = 0) -> None:
                for li in list_tag.find_all("li", recursive=False):
                    text_parts: list[str] = []
                    nested_lists: list[Any] = []

                    for child in li.children:
                        child_tag_name = getattr(child, "name", None)
                        if child_tag_name in ("ul", "ol"):
                            nested_lists.append(child)
                        else:
                            if hasattr(child, "get_text"):
                                piece = clean_text(child.get_text(" ", strip=True))
                            else:
                                piece = clean_text(str(child))
                            if piece:
                                text_parts.append(piece)

                    line = clean_text(" ".join(text_parts))
                    if line:
                        indent = "  " * level
                        lines.append(f"{indent}• {line}")

                    for nested in nested_lists:
                        parse_list(nested, level + 1)

            top_nodes = list(frag_soup.children)
            for node in top_nodes:
                tag_name = getattr(node, "name", None)

                if tag_name in ("ul", "ol"):
                    parse_list(node, 0)
                    continue

                if hasattr(node, "get_text"):
                    txt = clean_text(node.get_text(" ", strip=True))
                else:
                    txt = clean_text(str(node))

                if txt:
                    lines.append(txt)

            if not lines:
                txt = clean_text(frag_soup.get_text("\n", strip=True))
                if txt:
                    lines = [clean_text(line) for line in txt.splitlines() if clean_text(line)]

            return "\n".join(line for line in lines if line).strip()

        formatted_week = selected.get("FormattedWeek") or week_key
        class_or_group = selected.get("ClassOrGroup")
        general_plan = selected.get("GeneralPlan") or {}
        daily_plans = selected.get("DailyPlans") or []

        general_items: list[dict[str, Any]] = []
        for lesson in general_plan.get("LessonPlans") or []:
            subject_obj = lesson.get("Subject") or {}
            subject = subject_obj.get("FormattedTitle") or subject_obj.get("Title") or ""
            content_html = lesson.get("Content") or ""

            general_items.append(
                {
                    "subject": clean_text(subject),
                    "lesson_number": subject_obj.get("LessonNumber"),
                    "content_html": content_html,
                    "content_text": html_to_text(content_html),
                }
            )

        days: list[dict[str, Any]] = []
        for day in daily_plans:
            lesson_plans: list[dict[str, Any]] = []
            for lesson in day.get("LessonPlans") or []:
                subject_obj = lesson.get("Subject") or {}
                subject = subject_obj.get("FormattedTitle") or subject_obj.get("Title") or ""
                content_html = lesson.get("Content") or ""

                lesson_plans.append(
                    {
                        "subject": clean_text(subject),
                        "lesson_number": subject_obj.get("LessonNumber"),
                        "content_html": content_html,
                        "content_text": html_to_text(content_html),
                        "link": lesson.get("Link"),
                        "attachments": lesson.get("Attachments") or [],
                    }
                )

            schedule_items: list[dict[str, Any]] = []
            for sched in day.get("Schedule") or []:
                schedule_items.append(
                    {
                        "time": sched.get("TimeString"),
                        "title": sched.get("Title"),
                        "class_name": sched.get("ClassName"),
                        "subject_short": sched.get("ShortSubjectTitle"),
                        "subject_full": sched.get("FullSubjectTitle"),
                        "lesson_number": sched.get("LessonNumber"),
                    }
                )

            days.append(
                {
                    "date": day.get("Date"),
                    "day": day.get("Day"),
                    "formatted_date": day.get("FormattedDate"),
                    "long_formatted_date": day.get("LongFormattedDate"),
                    "lesson_plans": lesson_plans,
                    "schedule": schedule_items,
                }
            )

        if not general_items and not days:
            return None

        markdown_parts: list[str] = []
        title = f"Ugeplan for {class_or_group} - uge {formatted_week}" if class_or_group else f"Ugeplan {formatted_week}"
        markdown_parts.append(f"# {title}")

        if general_items:
            markdown_parts.append("## Generelt")
            for item in general_items:
                if item["subject"]:
                    markdown_parts.append(f"### {item['subject']}")
                if item["content_text"]:
                    markdown_parts.append(item["content_text"])

        for day in days:
            header = day.get("day") or ""
            if day.get("formatted_date"):
                header = f"{header} {day['formatted_date']}".strip()

            if header:
                markdown_parts.append(f"## {header}")

            for lesson in day.get("lesson_plans", []):
                subject = lesson.get("subject") or "Ukendt fag"
                markdown_parts.append(f"### {subject}")
                if lesson.get("content_text"):
                    markdown_parts.append(lesson["content_text"])

            schedule = day.get("schedule") or []
            if schedule:
                schedule_lines = ["### Skema"]
                for row in schedule:
                    time_str = row.get("time") or ""
                    title_str = row.get("title") or ""
                    if time_str or title_str:
                        schedule_lines.append(f"- {time_str} — {title_str}".strip())
                markdown_parts.append("\n".join(schedule_lines))

        markdown = "\n\n".join(part for part in markdown_parts if part).strip()

        return {
            "barn": child_name,
            "week": formatted_week,
            "title": title,
            "class_or_group": class_or_group,
            "general": general_items,
            "days": days,
            "markdown": markdown,
            "url": url,
        }

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
