"""The Panasonic H&C integration."""

from __future__ import annotations

import asyncio
import logging
import sys

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_CONSUMPTION_UPDATE_INTERVAL,
    CONF_NOTIFICATION_TIMEOUT,
    CONF_RECONNECT_BASE_DELAY,
    CONF_RECONNECT_MAX_DELAY,
    CONF_STATUS_UPDATE_INTERVAL,
    DEFAULT_CONSUMPTION_UPDATE_INTERVAL,
    DEFAULT_NOTIFICATION_TIMEOUT,
    DEFAULT_RECONNECT_BASE_DELAY,
    DEFAULT_RECONNECT_MAX_DELAY,
    DEFAULT_STATUS_UPDATE_INTERVAL,
    DOMAIN,
    SIGNAL_THERMOSTAT_CONNECTED,
    SIGNAL_THERMOSTAT_DISCONNECTED,
)
from .panasonic_hc import PanasonicHC, PanasonicHCException

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]

type PanasonicHCConfigEntry = ConfigEntry[PanasonicHC]  # noqa: F821

# Default reconnection parameters - these will be overridden by config entry options
RECONNECT_MAX_ATTEMPTS = 0  # 0 means unlimited attempts

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Panasonic H&C from a config entry."""

    mac_address: str | None = entry.unique_id

    device = bluetooth.async_ble_device_from_address(
        hass, mac_address.upper(), connectable=True
    )

    if device is None:
        raise ConfigEntryNotReady(f"[{mac_address}] Device could not be found")

    # Get configuration options
    options = entry.options
    notification_timeout = options.get(
        CONF_NOTIFICATION_TIMEOUT, DEFAULT_NOTIFICATION_TIMEOUT
    )
    consumption_interval = options.get(
        CONF_CONSUMPTION_UPDATE_INTERVAL, DEFAULT_CONSUMPTION_UPDATE_INTERVAL
    )

    thermostat = PanasonicHC(
        ble_device=device,
        mac_address=mac_address,
        notification_timeout=notification_timeout,
        consumption_interval=consumption_interval,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = thermostat

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_create_background_task(
        hass, _async_run_thermostat(hass, entry), entry.entry_id
    )

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry update."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        thermostat: PanasonicHC = hass.data[DOMAIN].pop(entry.entry_id)
        await thermostat.async_disconnect()

    return unload_ok


async def _async_run_thermostat(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Run the thermostat."""

    thermostat = hass.data[DOMAIN][entry.entry_id]
    # Get configuration option for status update interval
    options = entry.options
    status_update_interval = options.get(
        CONF_STATUS_UPDATE_INTERVAL, DEFAULT_STATUS_UPDATE_INTERVAL
    )

    await _async_reconnect_thermostat(hass, entry)

    while True:
        try:
            # Proactively check connection status before attempting operations
            if not thermostat.is_connected or not thermostat.is_receiving_notifications:
                if not thermostat.is_connected:
                    _LOGGER.warning(
                        "[%s] PanasonicHC device detected as disconnected, reconnecting",
                        thermostat.mac_address
                    )
                else:
                    _LOGGER.warning(
                        "[%s] PanasonicHC device not receiving notifications, reconnecting",
                        thermostat.mac_address
                    )
                
                async_dispatcher_send(
                    hass, f"{SIGNAL_THERMOSTAT_DISCONNECTED}_{thermostat.mac_address}"
                )
                await _async_reconnect_thermostat(hass, entry)
                continue
                
            await thermostat.async_get_status()
        except PanasonicHCException as e:
            if not thermostat.is_connected:
                _LOGGER.error(
                    "[%s] PanasonicHC device disconnected: %s", 
                    thermostat.mac_address, 
                    str(e)
                )

                async_dispatcher_send(
                    hass, f"{SIGNAL_THERMOSTAT_DISCONNECTED}_{thermostat.mac_address}"
                )
                await _async_reconnect_thermostat(hass, entry)
                continue
                
            _LOGGER.error(
                "[%s] Error updating PanasonicHC device: %s", 
                thermostat.mac_address, 
                str(e)
            )
        except EOFError as e:
            # Explicitly handle EOFError - this indicates the connection was closed unexpectedly
            _LOGGER.error(
                "[%s] Connection broken (EOFError), forcing reconnection: %s", 
                thermostat.mac_address, 
                str(e)
            )
            
            async_dispatcher_send(
                hass, f"{SIGNAL_THERMOSTAT_DISCONNECTED}_{thermostat.mac_address}"
            )
            await _async_reconnect_thermostat(hass, entry)
            continue
        # Catch any other unexpected error and force reconnection
        except Exception as e:
            _LOGGER.error(
                "[%s] Unexpected error, forcing reconnection: %s", 
                thermostat.mac_address, 
                str(e)
            )
            
            # Get error details to help with debugging
            error_type, error_value, error_traceback = sys.exc_info()
            _LOGGER.error(
                "[%s] Error type: %s", 
                thermostat.mac_address, 
                error_type.__name__ if error_type else "Unknown"
            )
            
            async_dispatcher_send(
                hass, f"{SIGNAL_THERMOSTAT_DISCONNECTED}_{thermostat.mac_address}"
            )
            await _async_reconnect_thermostat(hass, entry)
            continue

        # Use the configured update interval
        await asyncio.sleep(status_update_interval)


async def _async_reconnect_thermostat(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reconnect thermostat with exponential backoff."""

    thermostat = hass.data[DOMAIN][entry.entry_id]
    attempt = 0
    
    # Get reconnection parameters from configuration options
    options = entry.options
    reconnect_base_delay = options.get(
        CONF_RECONNECT_BASE_DELAY, DEFAULT_RECONNECT_BASE_DELAY
    )
    reconnect_max_delay = options.get(
        CONF_RECONNECT_MAX_DELAY, DEFAULT_RECONNECT_MAX_DELAY
    )
    
    # Make sure we're disconnected before trying to reconnect
    try:
        if thermostat.is_connected:
            await thermostat.async_disconnect()
            # Small delay to ensure complete disconnection
            await asyncio.sleep(1)
    except Exception as e:
        _LOGGER.warning(
            "[%s] Error during disconnect before reconnection: %s",
            thermostat.mac_address,
            str(e)
        )

    while RECONNECT_MAX_ATTEMPTS == 0 or attempt < RECONNECT_MAX_ATTEMPTS:
        attempt += 1
        delay = min(reconnect_base_delay * (2 ** (attempt - 1)), reconnect_max_delay)
        
        try:
            _LOGGER.info(
                "[%s] Attempting to reconnect (attempt %d)...",
                thermostat.mac_address,
                attempt
            )
            await thermostat.async_connect()
            
            _LOGGER.info(
                "[%s] PanasonicHC device successfully reconnected",
                thermostat.mac_address
            )

            async_dispatcher_send(
                hass, f"{SIGNAL_THERMOSTAT_CONNECTED}_{thermostat.mac_address}"
            )
            return
            
        except PanasonicHCException as e:
            _LOGGER.warning(
                "[%s] Failed to reconnect (attempt %d): %s. Retrying in %d seconds...",
                thermostat.mac_address,
                attempt,
                str(e),
                delay
            )
            await asyncio.sleep(delay)
            continue
        
        except Exception as e:
            _LOGGER.error(
                "[%s] Unexpected error during reconnection (attempt %d): %s. Retrying in %d seconds...",
                thermostat.mac_address,
                attempt,
                str(e),
                delay
            )
            await asyncio.sleep(delay)
            continue
    
    _LOGGER.error(
        "[%s] Failed to reconnect after %d attempts. Giving up.",
        thermostat.mac_address,
        attempt
    )