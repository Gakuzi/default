"""Initialization of Yandex Bus Arkhangelsk component."""
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import YandexBusCoordinator

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Инициализация интеграции из конфига."""
    hass.data.setdefault(DOMAIN, {})

    stop_id = entry.data[CONF_STOP_ID]
    stop_name = entry.data.get(CONF_STOP_NAME, f"Остановка {stop_id}")

    interval_sec = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinator = YandexBusCoordinator(hass, stop_id, stop_name, interval_sec)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Срабатывает при изменении параметров через 'Настроить'."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        new_interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        coordinator.update_interval = timedelta(seconds=new_interval)

    await hass.config_entries.async_reload(entry.entry_id)
