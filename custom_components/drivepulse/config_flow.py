"""Config flow: one click creates the webhook and shows its address."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import webhook
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_LOCAL_ONLY, CONF_SOURCES, DEFAULT_LOCAL_ONLY, DOMAIN
from .hub import Vehicle
from .units import SOURCE_UNITS, fits


def webhook_address(hass: HomeAssistant, webhook_id: str) -> str:
    """The address to paste in the app: the local one if Home Assistant has it."""
    try:
        return webhook.async_generate_url(
            hass, webhook_id, allow_external=False, allow_ip=True
        )
    except NoURLAvailableError:
        return f"http://homeassistant.local:8123/api/webhook/{webhook_id}"


class DrivePulseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add DrivePulse: no questions, the webhook is generated."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
        webhook_id = webhook.async_generate_id()
        return self.async_create_entry(
            title="DrivePulse",
            data={CONF_WEBHOOK_ID: webhook_id},
            description_placeholders={
                "webhook_url": webhook_address(self.hass, webhook_id)
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DrivePulseOptionsFlow()


class DrivePulseOptionsFlow(OptionsFlow):
    """The network switch, and the custom PIDs standing in for built-in sensors."""

    _slug: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["network", "sources"],
            description_placeholders=self._address(),
        )

    def _address(self) -> dict[str, str]:
        return {
            "webhook_url": webhook_address(
                self.hass, self.config_entry.data[CONF_WEBHOOK_ID]
            )
        }

    def _save(self, **changes: Any) -> ConfigFlowResult:
        # The options are replaced as a whole: keep the other ones.
        return self.async_create_entry(data={**self.config_entry.options, **changes})

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the webhook address again, and the local-only switch."""
        if user_input is not None:
            return self._save(**user_input)
        return self.async_show_form(
            step_id="network",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCAL_ONLY,
                        default=self.config_entry.options.get(
                            CONF_LOCAL_ONLY, DEFAULT_LOCAL_ONLY
                        ),
                    ): bool
                }
            ),
            description_placeholders=self._address(),
        )

    def _vehicles(self) -> dict[str, Vehicle]:
        """The vehicles that have sent a custom PID: the only ones to set up."""
        hub = getattr(self.config_entry, "runtime_data", None)
        if hub is None:
            return {}
        return {slug: v for slug, v in hub.vehicles.items() if v.custom}

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the vehicle, when there is more than one to pick from."""
        vehicles = self._vehicles()
        if not vehicles:
            return self.async_abort(reason="no_custom_pids")
        if len(vehicles) == 1:
            self._slug = next(iter(vehicles))
            return await self.async_step_vehicle_sources()
        if user_input is not None and user_input.get("vehicle") in vehicles:
            self._slug = user_input["vehicle"]
            return await self.async_step_vehicle_sources()
        return self.async_show_form(
            step_id="sources",
            data_schema=vol.Schema(
                {
                    vol.Required("vehicle"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=slug, label=vehicle.name)
                                for slug, vehicle in sorted(
                                    vehicles.items(), key=lambda item: item[1].name
                                )
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_vehicle_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """One field per built-in sensor: empty keeps the app's own reading."""
        vehicle = self._vehicles().get(self._slug or "")
        if vehicle is None:
            return self.async_abort(reason="no_custom_pids")
        saved = self.config_entry.options.get(CONF_SOURCES, {})
        current = saved.get(vehicle.slug, {}) if isinstance(saved, dict) else {}
        errors: dict[str, str] = {}

        if user_input is not None:
            chosen = {
                key: cp_id
                for key, cp_id in user_input.items()
                if key in SOURCE_UNITS and cp_id in vehicle.custom
            }
            for key, cp_id in chosen.items():
                if not fits(vehicle.custom[cp_id].unit, SOURCE_UNITS[key]):
                    errors[key] = "wrong_unit"
            if not errors:
                sources = {**(saved if isinstance(saved, dict) else {})}
                if chosen:
                    sources[vehicle.slug] = chosen
                else:
                    sources.pop(vehicle.slug, None)
                return self._save(**{CONF_SOURCES: sources})
            current = chosen

        options = [
            SelectOptionDict(
                value=cp_id,
                label=f"{pid.name} ({pid.unit})" if pid.unit else pid.name,
            )
            for cp_id, pid in sorted(vehicle.custom.items(), key=lambda i: i[1].name)
        ]
        # suggested_value, not default: a default would come back when the
        # user clears the field, and clearing is how to go back to the app.
        schema = {
            vol.Optional(key, description={"suggested_value": current.get(key)}): (
                SelectSelector(
                    SelectSelectorConfig(
                        options=options, mode=SelectSelectorMode.DROPDOWN
                    )
                )
            )
            for key in SOURCE_UNITS
        }
        return self.async_show_form(
            step_id="vehicle_sources",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={"vehicle": vehicle.name},
        )
