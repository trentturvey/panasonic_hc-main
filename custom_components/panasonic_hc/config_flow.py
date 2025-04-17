"""Config flow for Panasonic H&C."""

import logging
from typing import Any

from habluetooth import BluetoothServiceInfoBleak
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_MAC
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_RECONNECT_BASE_DELAY,
    CONF_RECONNECT_MAX_DELAY,
    CONF_NOTIFICATION_TIMEOUT,
    CONF_TEMP_CHANGE_THRESHOLD,
    CONF_TEMP_VALIDATION_WINDOW,
    CONF_TEMP_VALIDATION_ENABLED,
    CONF_STATUS_UPDATE_INTERVAL,
    CONF_CONSUMPTION_UPDATE_INTERVAL,
    DEFAULT_RECONNECT_BASE_DELAY,
    DEFAULT_RECONNECT_MAX_DELAY,
    DEFAULT_NOTIFICATION_TIMEOUT,
    DEFAULT_TEMP_CHANGE_THRESHOLD,
    DEFAULT_TEMP_VALIDATION_WINDOW,
    DEFAULT_TEMP_VALIDATION_ENABLED,
    DEFAULT_STATUS_UPDATE_INTERVAL,
    DEFAULT_CONSUMPTION_UPDATE_INTERVAL,
    DOMAIN,
    MODEL,
)

SCHEMA_MAC = vol.Schema({vol.Required(CONF_MAC): str})

_LOGGER = logging.getLogger(__name__)


class PanasonicHCConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Panasonic H&C controller."""

    def __init__(self) -> None:
        """Initialise config flow."""
        self.mac_address: str
        super().__init__()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle flow initiated by user."""

        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_MAC,
                errors=errors,
            )

        self.mac_address = format_mac(user_input[CONF_MAC])

        if not validate_mac(self.mac_address):
            errors[CONF_MAC] = "invalid_mac_address"
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_MAC,
                errors=errors,
            )

        await self.async_set_unique_id(self.mac_address)
        self._abort_if_unique_id_configured(updates=user_input)

        return self.async_create_entry(
            title=f"{MODEL}_{self.mac_address[-8:].replace(':','')}", 
            data={},
            options={
                CONF_RECONNECT_BASE_DELAY: DEFAULT_RECONNECT_BASE_DELAY,
                CONF_RECONNECT_MAX_DELAY: DEFAULT_RECONNECT_MAX_DELAY,
                CONF_NOTIFICATION_TIMEOUT: DEFAULT_NOTIFICATION_TIMEOUT,
                CONF_TEMP_CHANGE_THRESHOLD: DEFAULT_TEMP_CHANGE_THRESHOLD,
                CONF_TEMP_VALIDATION_WINDOW: DEFAULT_TEMP_VALIDATION_WINDOW,
                CONF_TEMP_VALIDATION_ENABLED: DEFAULT_TEMP_VALIDATION_ENABLED,
                CONF_STATUS_UPDATE_INTERVAL: DEFAULT_STATUS_UPDATE_INTERVAL,
                CONF_CONSUMPTION_UPDATE_INTERVAL: DEFAULT_CONSUMPTION_UPDATE_INTERVAL,
            }
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery phase."""

        _LOGGER.info("Discovered Bluetooth Device")

        self.mac_address = format_mac(discovery_info.address)

        await self.async_set_unique_id(self.mac_address)
        self._abort_if_unique_id_configured()

        self.context.update({"title_placeholders": {CONF_MAC: self.mac_address}})

        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle flow start."""

        if user_input is None:
            return self.async_show_form(
                step_id="init", description_placeholders={CONF_MAC: self.mac_address}
            )

        await self.async_set_unique_id(self.mac_address)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{MODEL}_{self.mac_address[-8:].replace(':','')}",
            data={},
            options={
                CONF_RECONNECT_BASE_DELAY: DEFAULT_RECONNECT_BASE_DELAY,
                CONF_RECONNECT_MAX_DELAY: DEFAULT_RECONNECT_MAX_DELAY,
                CONF_NOTIFICATION_TIMEOUT: DEFAULT_NOTIFICATION_TIMEOUT,
                CONF_TEMP_CHANGE_THRESHOLD: DEFAULT_TEMP_CHANGE_THRESHOLD,
                CONF_TEMP_VALIDATION_WINDOW: DEFAULT_TEMP_VALIDATION_WINDOW,
                CONF_TEMP_VALIDATION_ENABLED: DEFAULT_TEMP_VALIDATION_ENABLED,
                CONF_STATUS_UPDATE_INTERVAL: DEFAULT_STATUS_UPDATE_INTERVAL,
                CONF_CONSUMPTION_UPDATE_INTERVAL: DEFAULT_CONSUMPTION_UPDATE_INTERVAL,
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PanasonicHCOptionsFlow(config_entry)


class PanasonicHCOptionsFlow(OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
    # No need to explicitly store config_entry as an instance variable
    # It's already available as self.config_entry in OptionsFlow
        super().__init__()

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options

        connection_schema = vol.Schema(
            {
                vol.Required(
                    CONF_RECONNECT_BASE_DELAY,
                    default=options.get(CONF_RECONNECT_BASE_DELAY, DEFAULT_RECONNECT_BASE_DELAY),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required(
                    CONF_RECONNECT_MAX_DELAY,
                    default=options.get(CONF_RECONNECT_MAX_DELAY, DEFAULT_RECONNECT_MAX_DELAY),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                vol.Required(
                    CONF_NOTIFICATION_TIMEOUT,
                    default=options.get(CONF_NOTIFICATION_TIMEOUT, DEFAULT_NOTIFICATION_TIMEOUT),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
            }
        )

        temperature_schema = vol.Schema(
            {
                vol.Required(
                    CONF_TEMP_VALIDATION_ENABLED,
                    default=options.get(CONF_TEMP_VALIDATION_ENABLED, DEFAULT_TEMP_VALIDATION_ENABLED),
                ): bool,
                vol.Required(
                    CONF_TEMP_CHANGE_THRESHOLD,
                    default=options.get(CONF_TEMP_CHANGE_THRESHOLD, DEFAULT_TEMP_CHANGE_THRESHOLD),
                ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=20.0)),
                vol.Required(
                    CONF_TEMP_VALIDATION_WINDOW,
                    default=options.get(CONF_TEMP_VALIDATION_WINDOW, DEFAULT_TEMP_VALIDATION_WINDOW),
                ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=60.0)),
            }
        )

        polling_schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATUS_UPDATE_INTERVAL,
                    default=options.get(CONF_STATUS_UPDATE_INTERVAL, DEFAULT_STATUS_UPDATE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Required(
                    CONF_CONSUMPTION_UPDATE_INTERVAL,
                    default=options.get(CONF_CONSUMPTION_UPDATE_INTERVAL, DEFAULT_CONSUMPTION_UPDATE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
            }
        )

        return self.async_show_menu(
            step_id="init",
            menu_options=["connection_settings", "temperature_settings", "polling_settings"],
        )

    async def async_step_connection_settings(self, user_input=None):
        """Handle connection settings step."""
        options = self.config_entry.options
        
        if user_input is not None:
            updated_options = {**options, **user_input}
            return self.async_create_entry(title="", data=updated_options)

        connection_schema = vol.Schema(
            {
                vol.Required(
                    CONF_RECONNECT_BASE_DELAY,
                    default=options.get(CONF_RECONNECT_BASE_DELAY, DEFAULT_RECONNECT_BASE_DELAY),
                    description="Initial delay (seconds) between reconnection attempts. Doubles with each attempt.",
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required(
                    CONF_RECONNECT_MAX_DELAY,
                    default=options.get(CONF_RECONNECT_MAX_DELAY, DEFAULT_RECONNECT_MAX_DELAY),
                    description="Maximum delay (seconds) between reconnection attempts.",
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                vol.Required(
                    CONF_NOTIFICATION_TIMEOUT,
                    default=options.get(CONF_NOTIFICATION_TIMEOUT, DEFAULT_NOTIFICATION_TIMEOUT),
                    description="Time (seconds) without notifications before considering the device disconnected.",
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
            }
        )

        return self.async_show_form(
            step_id="connection_settings", 
            data_schema=connection_schema,
            description_placeholders={
                "name": "Connection Settings",
                "description": "Configure how the integration manages Bluetooth connections",
            },
        )

    async def async_step_temperature_settings(self, user_input=None):
        """Handle temperature settings step."""
        options = self.config_entry.options
        
        if user_input is not None:
            updated_options = {**options, **user_input}
            return self.async_create_entry(title="", data=updated_options)

        temperature_schema = vol.Schema(
            {
                vol.Required(
                    CONF_TEMP_VALIDATION_ENABLED,
                    default=options.get(CONF_TEMP_VALIDATION_ENABLED, DEFAULT_TEMP_VALIDATION_ENABLED),
                    description="Enable validation to filter out anomalous temperature readings.",
                ): bool,
                vol.Required(
                    CONF_TEMP_CHANGE_THRESHOLD,
                    default=options.get(CONF_TEMP_CHANGE_THRESHOLD, DEFAULT_TEMP_CHANGE_THRESHOLD),
                    description="Temperature change (°C) threshold to consider as anomalous.",
                ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=20.0)),
                vol.Required(
                    CONF_TEMP_VALIDATION_WINDOW,
                    default=options.get(CONF_TEMP_VALIDATION_WINDOW, DEFAULT_TEMP_VALIDATION_WINDOW),
                    description="Time window (seconds) to check for anomalous temperature changes.",
                ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=60.0)),
            }
        )

        return self.async_show_form(
            step_id="temperature_settings", 
            data_schema=temperature_schema,
            description_placeholders={
                "name": "Temperature Validation",
                "description": "Configure how the integration filters out anomalous temperature readings",
            },
        )

    async def async_step_polling_settings(self, user_input=None):
        """Handle polling settings step."""
        options = self.config_entry.options
        
        if user_input is not None:
            updated_options = {**options, **user_input}
            return self.async_create_entry(title="", data=updated_options)

        polling_schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATUS_UPDATE_INTERVAL,
                    default=options.get(CONF_STATUS_UPDATE_INTERVAL, DEFAULT_STATUS_UPDATE_INTERVAL),
                    description="How often (seconds) to request status updates from the device.",
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Required(
                    CONF_CONSUMPTION_UPDATE_INTERVAL,
                    default=options.get(CONF_CONSUMPTION_UPDATE_INTERVAL, DEFAULT_CONSUMPTION_UPDATE_INTERVAL),
                    description="How often (seconds) to request energy consumption data.",
                ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
            }
        )

        return self.async_show_form(
            step_id="polling_settings", 
            data_schema=polling_schema,
            description_placeholders={
                "name": "Polling Settings",
                "description": "Configure how often the integration polls the device for updates",
            },
        )


def validate_mac(mac: str) -> bool:
    """Return whether or not given value is a valid MAC address."""

    return bool(
        mac
        and len(mac) == 17
        and mac.count(":") == 5
        and all(int(part, 16) < 256 for part in mac.split(":") if part)
    )