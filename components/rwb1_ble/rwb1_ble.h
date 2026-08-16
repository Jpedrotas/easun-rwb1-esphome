#pragma once

#include "esphome/components/esp32_ble_client/ble_client_base.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/core/component.h"
#include "esphome/core/gpio.h"

#include <array>
#include <string>
#include <vector>

namespace esphome::rwb1_ble {

namespace espbt = esphome::esp32_ble_tracker;

class RWB1BLE : public esp32_ble_client::BLEClientBase {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  bool parse_device(const espbt::ESPBTDevice &device) override;
  bool gattc_event_handler(esp_gattc_cb_event_t event, esp_gatt_if_t gattc_if,
                           esp_ble_gattc_cb_param_t *param) override;

  void set_dtu_id(const std::string &dtu_id) { this->dtu_id_ = dtu_id; }
  void set_key_hex(const std::string &key_hex);
  void set_update_interval(uint32_t interval) { this->update_interval_ = interval; }
  void set_activity_led(InternalGPIOPin *pin) { this->activity_led_ = pin; }

  void set_status_sensor(sensor::Sensor *sensor) { this->status_sensor_ = sensor; }
  void set_grid_voltage_sensor(sensor::Sensor *sensor) { this->grid_voltage_sensor_ = sensor; }
  void set_grid_frequency_sensor(sensor::Sensor *sensor) { this->grid_frequency_sensor_ = sensor; }
  void set_pv_voltage_sensor(sensor::Sensor *sensor) { this->pv_voltage_sensor_ = sensor; }
  void set_pv_power_sensor(sensor::Sensor *sensor) { this->pv_power_sensor_ = sensor; }
  void set_battery_voltage_sensor(sensor::Sensor *sensor) { this->battery_voltage_sensor_ = sensor; }
  void set_battery_soc_sensor(sensor::Sensor *sensor) { this->battery_soc_sensor_ = sensor; }
  void set_battery_charge_current_sensor(sensor::Sensor *sensor) { this->battery_charge_current_sensor_ = sensor; }
  void set_battery_discharge_current_sensor(sensor::Sensor *sensor) {
    this->battery_discharge_current_sensor_ = sensor;
  }
  void set_output_voltage_sensor(sensor::Sensor *sensor) { this->output_voltage_sensor_ = sensor; }
  void set_output_frequency_sensor(sensor::Sensor *sensor) { this->output_frequency_sensor_ = sensor; }
  void set_load_apparent_power_sensor(sensor::Sensor *sensor) { this->load_apparent_power_sensor_ = sensor; }
  void set_load_active_power_sensor(sensor::Sensor *sensor) { this->load_active_power_sensor_ = sensor; }
  void set_load_percent_sensor(sensor::Sensor *sensor) { this->load_percent_sensor_ = sensor; }
  void set_rated_power_sensor(sensor::Sensor *sensor) { this->rated_power_sensor_ = sensor; }

 protected:
  bool prepare_request_();
  void send_next_fragment_();
  void consume_fragment_(const uint8_t *data, size_t length);
  bool decrypt_response_(const std::vector<uint8_t> &message, std::vector<uint8_t> &frame);
  bool publish_modbus_(const std::vector<uint8_t> &frame);
  void blink_activity_();
  static uint16_t crc16_modbus_(const uint8_t *data, size_t length);
  static bool hex_to_bytes_(const std::string &hex, std::vector<uint8_t> &out);

  std::string dtu_id_;
  std::array<uint8_t, 16> key_{};
  bool key_configured_{false};
  uint32_t update_interval_{30000};
  uint32_t last_poll_{0};
  uint32_t request_started_{0};
  uint16_t write_handle_{0};
  uint16_t indicate_handle_{0};
  bool notify_registered_{false};
  bool request_pending_{false};

  std::vector<std::vector<uint8_t>> tx_fragments_;
  size_t tx_index_{0};
  uint8_t rx_total_{0};
  std::vector<std::vector<uint8_t>> rx_fragments_;

  InternalGPIOPin *activity_led_{nullptr};
  sensor::Sensor *status_sensor_{nullptr};
  sensor::Sensor *grid_voltage_sensor_{nullptr};
  sensor::Sensor *grid_frequency_sensor_{nullptr};
  sensor::Sensor *pv_voltage_sensor_{nullptr};
  sensor::Sensor *pv_power_sensor_{nullptr};
  sensor::Sensor *battery_voltage_sensor_{nullptr};
  sensor::Sensor *battery_soc_sensor_{nullptr};
  sensor::Sensor *battery_charge_current_sensor_{nullptr};
  sensor::Sensor *battery_discharge_current_sensor_{nullptr};
  sensor::Sensor *output_voltage_sensor_{nullptr};
  sensor::Sensor *output_frequency_sensor_{nullptr};
  sensor::Sensor *load_apparent_power_sensor_{nullptr};
  sensor::Sensor *load_active_power_sensor_{nullptr};
  sensor::Sensor *load_percent_sensor_{nullptr};
  sensor::Sensor *rated_power_sensor_{nullptr};
};

}  // namespace esphome::rwb1_ble
