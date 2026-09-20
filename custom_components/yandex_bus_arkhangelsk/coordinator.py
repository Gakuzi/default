"""DataUpdateCoordinator for Yandex Bus Arkhangelsk."""
import json
import logging
import re
from datetime import timedelta

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


def extract_stop_id(raw_input: str) -> str:
    """Извлекает числовой ID остановки из строки или ссылки."""
    if not raw_input:
        return ""
    match = re.search(r"(\d{6,12})", raw_input)
    if match:
        return match.group(1)
    return raw_input.strip()


def parse_yandex_stop_html(html: str, default_name: str) -> dict:
    """Парсинг данных по остановке из HTML-кода Яндекс.Карт."""
    parsed_name = default_name
    title_m = re.search(r"Остановка [«\"]([^»\"]+)[»\"]", html)
    if title_m:
        parsed_name = title_m.group(1)

    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    transports = None

    for s in scripts:
        if "BriefSchedule" in s and "transports" in s:
            try:
                data = json.loads(s)

                def extract(d):
                    if isinstance(d, dict):
                        if "transports" in d and isinstance(d["transports"], list):
                            return d["transports"]
                        for v in d.values():
                            res = extract(v)
                            if res:
                                return res
                    elif isinstance(d, list):
                        for item in d:
                            res = extract(item)
                            if res:
                                return res
                    return None

                transports = extract(data)
                if transports:
                    break
            except Exception:
                continue

    routes_dict = {}
    routes_list = []
    nearest_bus = "Нет рейсов"
    nearest_time = "99:99"

    if transports:
        for t in transports:
            name = str(t.get("name", "")).strip()
            if not name:
                continue
            line_id = str(t.get("lineId", ""))
            times = []

            for thread in t.get("threads", []):
                for ev in thread.get("BriefSchedule", {}).get("Events", []):
                    time_val = ev.get("Estimated", {}).get("text") or ev.get("Scheduled", {}).get("text")
                    if time_val and time_val not in times:
                        times.append(time_val)

            if times:
                next_time = times[0]
                route_data = {
                    "route": name,
                    "next": next_time,
                    "times": times[:5],
                    "line_id": line_id,
                    "map_url": f"https://yandex.ru/maps/20/arkhangelsk/?masstransit%5BlineId%5D={line_id}&l=masstransit",
                }
                routes_dict[name] = route_data
                routes_list.append(route_data)

                if next_time < nearest_time:
                    nearest_time = next_time
                    nearest_bus = f"№{name} в {next_time}"

    routes_list.sort(key=lambda x: x["next"])

    return {
        "stop_name": parsed_name,
        "nearest": nearest_bus,
        "routes": routes_list,
        "routes_dict": routes_dict,
    }


class YandexBusCoordinator(DataUpdateCoordinator):
    """Координатор опроса Яндекс.Карт без блокировки потоков."""

    def __init__(self, hass: HomeAssistant, stop_id: str, stop_name: str, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{stop_id}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.stop_id = extract_stop_id(stop_id)
        self.stop_name = stop_name
        self.session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict:
        url = f"https://yandex.ru/maps/20/arkhangelsk/stops/{self.stop_id}/?l=masstransit"
        try:
            async with async_timeout.timeout(12):
                response = await self.session.get(url, headers=HEADERS)
                if response.status != 200:
                    raise UpdateFailed(f"Ошибка Яндекс.Карт: HTTP {response.status}")
                html = await response.text()
        except Exception as err:
            raise UpdateFailed(f"Сетевая ошибка при запросе данных: {err}") from err

        data = parse_yandex_stop_html(html, self.stop_name)
        if data.get("stop_name"):
            self.stop_name = data["stop_name"]

        return data
