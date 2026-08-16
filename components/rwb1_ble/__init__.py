"""Read-only EASUN RWB1 Bluetooth telemetry component."""

import os

import esphome.codegen as cg
from esphome.components import esp32_ble, esp32_ble_client, esp32_ble_tracker, sensor
from esphome.components.esp32_ble import BTLoggers
import esphome.config_validation as cv
from esphome.const import (
    CONF_ID,
    CONF_UPDATE_INTERVAL,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_FREQUENCY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    STATE_CLASS_MEASUREMENT,
    UNIT_AMPERE,
    UNIT_HERTZ,
    UNIT_PERCENT,
    UNIT_VOLT,
    UNIT_WATT,
)
from esphome import pins

AUTO_LOAD = ["esp32_ble_client", "sensor"]
DEPENDENCIES = ["esp32", "esp32_ble_tracker"]
CODEOWNERS = []

CONF_DTU_ID = "dtu_id"
CONF_ACTIVITY_LED = "activity_led"
CONF_STATUS_CODE = "status_code"
CONF_GRID_VOLTAGE = "grid_voltage"
CONF_GRID_FREQUENCY = "grid_frequency"
CONF_PV_VOLTAGE = "pv_voltage"
CONF_PV_POWER = "pv_power"
CONF_BATTERY_VOLTAGE = "battery_voltage"
CONF_BATTERY_SOC = "battery_soc"
CONF_BATTERY_CHARGE_CURRENT = "battery_charge_current"
CONF_BATTERY_DISCHARGE_CURRENT = "battery_discharge_current"
CONF_OUTPUT_VOLTAGE = "output_voltage"
CONF_OUTPUT_FREQUENCY = "output_frequency"
CONF_LOAD_APPARENT_POWER = "load_apparent_power"
CONF_LOAD_ACTIVE_POWER = "load_active_power"
CONF_LOAD_PERCENT = "load_percent"
CONF_RATED_POWER = "rated_power"

rwb1_ns = cg.esphome_ns.namespace("rwb1_ble")
RWB1BLE = rwb1_ns.class_("RWB1BLE", esp32_ble_client.BLEClientBase)


def measurement(unit, device_class=None, accuracy_decimals=0):
    kwargs = dict(
        unit_of_measurement=unit,
        accuracy_decimals=accuracy_decimals,
        state_class=STATE_CLASS_MEASUREMENT,
    )
    if device_class is not None:
        kwargs["device_class"] = device_class
    return sensor.sensor_schema(**kwargs)


SENSORS = {
    CONF_STATUS_CODE: (sensor.sensor_schema(accuracy_decimals=0), "set_status_sensor"),
    CONF_GRID_VOLTAGE: (measurement(UNIT_VOLT, DEVICE_CLASS_VOLTAGE, 1), "set_grid_voltage_sensor"),
    CONF_GRID_FREQUENCY: (measurement(UNIT_HERTZ, DEVICE_CLASS_FREQUENCY, 1), "set_grid_frequency_sensor"),
    CONF_PV_VOLTAGE: (measurement(UNIT_VOLT, DEVICE_CLASS_VOLTAGE, 1), "set_pv_voltage_sensor"),
    CONF_PV_POWER: (measurement(UNIT_WATT, DEVICE_CLASS_POWER), "set_pv_power_sensor"),
    CONF_BATTERY_VOLTAGE: (
        measurement(UNIT_VOLT, DEVICE_CLASS_VOLTAGE, 1),
        "set_battery_voltage_sensor",
    ),
    CONF_BATTERY_SOC: (
        measurement(UNIT_PERCENT, DEVICE_CLASS_BATTERY),
        "set_battery_soc_sensor",
    ),
    CONF_BATTERY_CHARGE_CURRENT: (
        measurement(UNIT_AMPERE, DEVICE_CLASS_CURRENT),
        "set_battery_charge_current_sensor",
    ),
    CONF_BATTERY_DISCHARGE_CURRENT: (
        measurement(UNIT_AMPERE, DEVICE_CLASS_CURRENT),
        "set_battery_discharge_current_sensor",
    ),
    CONF_OUTPUT_VOLTAGE: (
        measurement(UNIT_VOLT, DEVICE_CLASS_VOLTAGE, 1),
        "set_output_voltage_sensor",
    ),
    CONF_OUTPUT_FREQUENCY: (
        measurement(UNIT_HERTZ, DEVICE_CLASS_FREQUENCY, 1),
        "set_output_frequency_sensor",
    ),
    CONF_LOAD_APPARENT_POWER: (
        measurement("VA", DEVICE_CLASS_POWER),
        "set_load_apparent_power_sensor",
    ),
    CONF_LOAD_ACTIVE_POWER: (
        measurement(UNIT_WATT, DEVICE_CLASS_POWER),
        "set_load_active_power_sensor",
    ),
    CONF_LOAD_PERCENT: (measurement(UNIT_PERCENT), "set_load_percent_sensor"),
    CONF_RATED_POWER: (measurement(UNIT_WATT, DEVICE_CLASS_POWER), "set_rated_power_sensor"),
}

def validate_identity(config):
    if CONF_DTU_ID not in config and not os.environ.get("RWB1_AES_KEY_HEX"):
        raise cv.Invalid("dtu_id is required")
    return config


def validate_update_interval(value):
    interval = cv.positive_time_period_milliseconds(value)
    if interval.total_milliseconds < 2000:
        raise cv.Invalid("minimum update_interval: 2s")
    return interval


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(RWB1BLE),
            cv.Optional(CONF_DTU_ID): cv.string_strict,
            cv.Optional(CONF_UPDATE_INTERVAL, default="30s"): validate_update_interval,
            cv.Optional(CONF_ACTIVITY_LED): pins.gpio_output_pin_schema,
            **{cv.Optional(key): schema for key, (schema, _setter) in SENSORS.items()},
        }
    )
    .extend(cv.COMPONENT_SCHEMA)
    .extend(esp32_ble_tracker.ESP_BLE_DEVICE_SCHEMA),
    validate_identity,
    esp32_ble.consume_connection_slots(1, "rwb1_ble"),
)


async def to_code(config):
    esp32_ble.register_bt_logger(BTLoggers.GATT)
    cg.add_define("USE_ESP32_BLE_UUID")

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await esp32_ble_tracker.register_client(var, config)
    if CONF_DTU_ID in config:
        cg.add(var.set_dtu_id(config[CONF_DTU_ID]))
    else:
        # Development/test override; normal public configurations use dtu_id.
        cg.add(var.set_key_hex(os.environ["RWB1_AES_KEY_HEX"]))
    cg.add(var.set_update_interval(config[CONF_UPDATE_INTERVAL]))
    cg.add(var.set_auto_connect(True))

    if CONF_ACTIVITY_LED in config:
        pin = await cg.gpio_pin_expression(config[CONF_ACTIVITY_LED])
        cg.add(var.set_activity_led(pin))

    for key, (_schema, setter) in SENSORS.items():
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(getattr(var, setter)(sens))
