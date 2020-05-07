"""Reads vehicle status from BMW connected drive portal."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_ID,
    ATTR_NAME,
    LENGTH_KILOMETERS,
)

from . import BMWConnectedDriveVehicleEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "lids": ["Doors", "opening", "mdi:car-door-lock"],
    "windows": ["Windows", "opening", "mdi:car-door"],
    "door_lock_state": ["Door lock state", "lock", "mdi:car-key"],
    "lights_parking": ["Parking lights", "light", "mdi:car-parking-lights"],
    "condition_based_services": ["Condition based services", "problem", "mdi:wrench"],
    "check_control_messages": ["Control messages", "problem", "mdi:car-tire-alert"],
}

SENSOR_TYPES_ELEC = {
    "charging_status": ["Charging status", "power", "mdi:ev-station"],
    "connection_status": ["Connection status", "plug", "mdi:car-electric"],
}

SENSOR_TYPES_ELEC.update(SENSOR_TYPES)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the BMW ConnectedDrive binary sensors from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug(
        "%s %s: vehicles: %s",
        DOMAIN,
        "binary_sensor",
        ", ".join([v.name for v in coordinator.account.vehicles]),
    )

    entities = []

    for vehicle in coordinator.account.vehicles:
        sensor_types = SENSOR_TYPES
        if vehicle.has_hv_battery:
            _LOGGER.debug("BMW with a high voltage battery")
            sensor_types.update(SENSOR_TYPES_ELEC)

        for key, value in sorted(sensor_types.items()):
            if key in vehicle.available_attributes:
                sensor = BMWConnectedDriveBinarySensor(
                    coordinator,
                    vehicle,
                    {
                        ATTR_ID: key,
                        ATTR_NAME: value[0],
                        ATTR_DEVICE_CLASS: value[1],
                        ATTR_ICON: value[2],
                    },
                )
                entities.append(sensor)
    # async_add_entities([BMWLock(coordinator, vehicle, PLATFORMS[LOCK])])
    async_add_entities(entities, True)


class BMWConnectedDriveBinarySensor(BMWConnectedDriveVehicleEntity, BinarySensorEntity):
    """Representation of a BMW vehicle binary sensor."""

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        vehicle_state = self.vehicle.state
        result = {"car": self.vehicle.name}

        if self._id == "lids":
            for lid in vehicle_state.lids:
                result[lid.name] = lid.state.value
        elif self._id == "windows":
            for window in vehicle_state.windows:
                result[window.name] = window.state.value
        elif self._id == "door_lock_state":
            result["door_lock_state"] = vehicle_state.door_lock_state.value
            result["last_update_reason"] = vehicle_state.last_update_reason
        elif self._id == "lights_parking":
            result["lights_parking"] = vehicle_state.parking_lights.value
        elif self._id == "condition_based_services":
            for report in vehicle_state.condition_based_services:
                result.update(self._format_cbs_report(report))
        elif self._id == "check_control_messages":
            check_control_messages = vehicle_state.check_control_messages
            has_check_control_messages = vehicle_state.has_check_control_messages
            if has_check_control_messages:
                cbs_list = []
                for message in check_control_messages:
                    cbs_list.append(message["ccmDescriptionShort"])
                result["check_control_messages"] = cbs_list
            else:
                result["check_control_messages"] = "OK"
        elif self._id == "charging_status":
            result["charging_status"] = vehicle_state.charging_status.value
            result["last_charging_end_result"] = vehicle_state.last_charging_end_result
        elif self._id == "connection_status":
            result["connection_status"] = vehicle_state.connection_status

        return sorted(result.items())

    def _format_cbs_report(self, report):
        result = {}
        service_type = report.service_type.lower().replace("_", " ")
        result[f"{service_type} status"] = report.state.value
        if report.due_date is not None:
            result[f"{service_type} date"] = report.due_date.strftime("%Y-%m-%d")
        if report.due_distance is not None:
            distance = round(
                self.hass.config.units.length(report.due_distance, LENGTH_KILOMETERS)
            )
            result[
                f"{service_type} distance"
            ] = f"{distance} {self.hass.config.units.length_unit}"
        return result
