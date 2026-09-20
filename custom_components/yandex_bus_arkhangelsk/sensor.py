"""Sensors for Yandex Bus Arkhangelsk."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STOP_NAME, CONF_TRACKED_ROUTES, DOMAIN
from .coordinator import YandexBusCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Создание сенсоров."""
    coordinator: YandexBusCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [YandexBusMainSensor(coordinator, entry)]

    current_data = entry.options if entry.options else entry.data
    tracked_routes = current_data.get(CONF_TRACKED_ROUTES)

    if tracked_routes is None:
        if coordinator.data:
            tracked_routes = list(coordinator.data.get("routes_dict", {}).keys())
        else:
            tracked_routes = []

    for route_num in tracked_routes:
        entities.append(YandexBusRouteSensor(coordinator, entry, str(route_num)))

    async_add_entities(entities)


class YandexBusMainSensor(CoordinatorEntity, SensorEntity):
    """Главный сенсор остановки (совместим с карточками транспорта)."""

    def __init__(self, coordinator: YandexBusCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"yandex_bus_stop_{coordinator.stop_id}"
        name = (coordinator.data or {}).get("stop_name") or entry.data.get(CONF_STOP_NAME)
        self._attr_name = name
        self._attr_icon = "mdi:bus-stop"

    @property
    def native_value(self) -> str:
        if not self.coordinator.data:
            return "Нет данных"
        return self.coordinator.data.get("nearest", "Нет данных")

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        return {
            "stop_id": self.coordinator.stop_id,
            "stop_name": self.coordinator.data.get("stop_name"),
            "routes": self.coordinator.data.get("routes", []),
        }


class YandexBusRouteSensor(CoordinatorEntity, SensorEntity):
    """Индивидуальный сенсор выбранного автобуса."""

    def __init__(self, coordinator: YandexBusCoordinator, entry: ConfigEntry, route: str) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.route = str(route)
        name = (coordinator.data or {}).get("stop_name") or entry.data.get(CONF_STOP_NAME)
        self._attr_unique_id = f"yandex_bus_{coordinator.stop_id}_route_{self.route}"
        self._attr_name = f"{name} — Автобус {self.route}"
        self._attr_icon = "mdi:bus"

    @property
    def native_value(self) -> str:
        if not self.coordinator.data:
            return "Нет рейсов"
        route_info = self.coordinator.data.get("routes_dict", {}).get(self.route)
        if route_info:
            return route_info.get("next", "Нет рейсов")
        return "Нет рейсов"

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {"route": self.route, "next_times": []}
        route_info = self.coordinator.data.get("routes_dict", {}).get(self.route, {})
        return {
            "route": self.route,
            "next_times": route_info.get("times", []),
            "map_url": route_info.get("map_url"),
            "stop_name": self.coordinator.data.get("stop_name"),
        }
