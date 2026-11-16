from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode, urljoin, urlparse

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from .api_parser import (
    _clean_child_name,
    _dk_date_to_iso,
    _extract_diary_id,
    _extract_latest_weekplan_from_list,
    _parse_homework_notes,
    _parse_weekplan_page,
)


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
        import re
        html_text, url = await self._get_home_html_and_url()
        soup = BeautifulSoup(html_text, "html.parser")

        children: list[Child] = []
        seen: set[tuple[str, str]] = set()

        active_match = re.search(r"/parent/(\d+)/([^/]+)/", url or "")
        if active_match:
            child_id = active_match.group(1)
            child_name = _clean_child_name(active_match.group(2))
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
                child_name = _clean_child_name(m.group(2))
                key = (child_id, child_name)
                if key not in seen:
                    seen.add(key)
                    children.append(Child(id=child_id, name=child_name))

        return children

    async def get_messages_for_children(
        self,
        children: list[Child],
    ) -> list[dict[str, Any]]:
        """Fetch the latest message for every conversation belonging to selected children."""
        messages: list[dict[str, Any]] = []

        for child in children:
            child_path = (
                f"/parent/{quote(child.id, safe='')}/{quote(child.name, safe='')}"
            )
            child_url = f"{self._base_url}{child_path}"
            conversations_url = f"{child_url}/messages/conversations"
            page_html = await self._get_text(conversations_url)
            page = BeautifulSoup(page_html, "html.parser")
            settings = page.select_one(
                "[data-clientlogic-settings-messageconversationswitharchivefunctionality]"
            )
            if settings is None:
                raise ForaldreIntraError(
                    "Samtalesiden indeholder ikke genkendelige beskeddata"
                )

            raw_settings = settings.get(
                "data-clientlogic-settings-messageconversationswitharchivefunctionality"
            )
            try:
                config = json.loads(str(raw_settings))
            except (TypeError, json.JSONDecodeError) as err:
                raise ForaldreIntraError(
                    "Beskedindstillingerne kunne ikke læses"
                ) from err

            conversations = config.get("Conversations")
            if not isinstance(conversations, list):
                raise ForaldreIntraError(
                    "Samtalelisten har et ukendt format"
                )

            provider = config.get("DataProviderSettings") or {}
            detail_endpoint = provider.get(
                "LoadMessagesForSelectedConversationUrl"
            ) or f"{child_path}/messages/conversations/loadmessagesforselectedconversation"
            detail_url = urljoin(f"{self._base_url}/", str(detail_endpoint).lstrip("/"))
            base_origin = urlparse(self._base_url)
            target_origin = urlparse(detail_url)
            if (
                target_origin.scheme != base_origin.scheme
                or target_origin.netloc != base_origin.netloc
                or not target_origin.path.startswith(child_path + "/")
            ):
                raise ForaldreIntraError(
                    "Beskedendpointet peger uden for den valgte skole eller elev"
                )

            for conversation in conversations:
                if not isinstance(conversation, dict):
                    continue
                latest_id = conversation.get("LatestMessageId")
                if latest_id is None:
                    continue
                thread_id = str(conversation.get("ThreadId") or "")
                if thread_id:
                    params = {
                        "threadId": thread_id,
                        "takeFromRootMessageId": str(latest_id),
                        "takeToMessageId": "0",
                        "searchRequest": "",
                    }
                    request_url = f"{detail_url}?{urlencode(params)}"
                else:
                    request_url = (
                        f"{child_url}/messages/conversations/getmessageforthreadlessconversation?"
                        f"{urlencode({'messageId': str(latest_id)})}"
                    )

                response_text = await self._get_text(request_url)
                try:
                    response_data = json.loads(response_text)
                except json.JSONDecodeError as err:
                    raise ForaldreIntraError(
                        "Beskedindholdet returnerede ikke gyldig JSON"
                    ) from err

                if isinstance(response_data, list):
                    candidates = response_data
                elif isinstance(response_data, dict):
                    candidates = [response_data]
                else:
                    raise ForaldreIntraError(
                        "Beskedindholdet har et ukendt format"
                    )

                latest_message = next(
                    (
                        item
                        for item in candidates
                        if isinstance(item, dict)
                        and str(item.get("Id")) == str(latest_id)
                    ),
                    None,
                )
                if latest_message is None:
                    valid_candidates = [
                        item for item in candidates
                        if isinstance(item, dict) and item.get("Id") is not None
                    ]
                    if valid_candidates:
                        latest_message = max(
                            valid_candidates,
                            key=lambda item: int(item.get("Id", 0))
                            if str(item.get("Id", "")).isdigit()
                            else 0,
                        )
                if latest_message is None:
                    continue
                if not isinstance(latest_message.get("BaseText"), str):
                    raise ForaldreIntraError(
                        "Beskedindholdet mangler meddelelsestekst"
                    )

                body = BeautifulSoup(
                    str(latest_message.get("BaseText") or ""),
                    "html.parser",
                )
                for tag in body(["script", "style"]):
                    tag.decompose()
                messages.append(
                    {
                        "id": str(latest_message.get("Id")),
                        "thread_id": thread_id or str(latest_id),
                        "child_id": child.id,
                        "child": child.name,
                        "subject": str(
                            latest_message.get("Subject")
                            or conversation.get("Subject")
                            or "Ny besked"
                        ),
                        "sender": str(latest_message.get("SenderName") or ""),
                        "sent_at": str(
                            latest_message.get("SentReceivedDateText") or ""
                        ),
                        "message": body.get_text(" ", strip=True),
                        "unread": bool(
                            latest_message.get("ShowUnreadIndication", False)
                        ),
                        "url": conversations_url,
                    }
                )

        return messages

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
            diary_id = _extract_diary_id(diary_text)
            if not diary_id:
                continue

            notes_url = (
                f"{self._base_url}/parent/{child_id}/{child_name}"
                f"item/weeklyplansandhomework/diary/notes/{diary_id}"
            )
            notes_text = await self._get_text(notes_url)
            parsed = _parse_homework_notes(notes_text)

            for item in parsed:
                item["barn"] = child_name
                item["dato"] = _dk_date_to_iso(item.get("dato"))
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
        """Henter fuld ugeplan for hver valgt elev."""
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
        """Bagudkompatibel hjælpefunktion."""
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

        html_text = await self._get_text(latest["url"])
        parsed = _parse_weekplan_page(
            html_text=html_text,
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

        latest = _extract_latest_weekplan_from_list(list_html)
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
