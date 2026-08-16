#include "rwb1_ble.h"

#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstring>

#include <esp_random.h>
#include <mbedtls/aes.h>
#include <mbedtls/base64.h>
#include <mbedtls/md5.h>

namespace esphome::rwb1_ble {

static const char *const TAG = "rwb1_ble";
static constexpr uint16_t SERVICE_UUID = 0xFEE7;
static constexpr uint16_t WRITE_UUID = 0xFED5;
static constexpr uint16_t INDICATE_UUID = 0xFED6;
static constexpr uint8_t MODBUS_REQUEST[] = {0x05, 0x03, 0x11, 0x95, 0x00, 0x15, 0x90, 0x91};

void RWB1BLE::setup() {
  BLEClientBase::setup();
  if (this->activity_led_ != nullptr) {
    this->activity_led_->setup();
    this->activity_led_->digital_write(false);
  }
  if (!this->key_configured_) {
    const std::string key_input = this->dtu_id_ + "SEC_";
    if (mbedtls_md5(reinterpret_cast<const unsigned char *>(key_input.data()), key_input.size(), this->key_.data()) !=
        0) {
      ESP_LOGE(TAG, "Could not derive the local key");
      this->mark_failed();
      return;
    }
  }
  ESP_LOGI(TAG, "Read-only RWB1 component started");
}

void RWB1BLE::set_key_hex(const std::string &key_hex) {
  std::vector<uint8_t> key;
  if (this->hex_to_bytes_(key_hex, key) && key.size() == this->key_.size()) {
    std::copy(key.begin(), key.end(), this->key_.begin());
    this->key_configured_ = true;
  }
}

void RWB1BLE::dump_config() {
  ESP_LOGCONFIG(TAG, "EASUN RWB1 BLE:");
  ESP_LOGCONFIG(TAG, "  Update interval: %lu ms", static_cast<unsigned long>(this->update_interval_));
  ESP_LOGCONFIG(TAG, "  Discovery: automatic by SSL_ prefix");
  ESP_LOGCONFIG(TAG, "  Configuration writes: disabled");
}

bool RWB1BLE::parse_device(const espbt::ESPBTDevice &device) {
  if (this->state() != espbt::ClientState::IDLE)
    return false;
  const auto &name = device.get_name();
  if (name.rfind("SSL_", 0) != 0)
    return false;
  this->set_address(device.address_uint64());
  this->set_remote_addr_type(device.get_address_type());
  this->set_state(espbt::ClientState::DISCOVERED);
  ESP_LOGI(TAG, "RWB1 discovered; starting connection");
  return true;
}

void RWB1BLE::loop() {
  BLEClientBase::loop();
  if (this->is_failed())
    return;
  const uint32_t now = millis();
  if (this->request_pending_ && now - this->request_started_ > 10000) {
    ESP_LOGW(TAG, "RWB1 read timed out");
    this->request_pending_ = false;
    this->tx_fragments_.clear();
    this->status_set_warning();
  }
  if (this->state() == espbt::ClientState::ESTABLISHED && this->notify_registered_ &&
      !this->request_pending_ && (this->last_poll_ == 0 || now - this->last_poll_ >= this->update_interval_)) {
    this->last_poll_ = now;
    if (this->prepare_request_())
      this->send_next_fragment_();
  }
}

bool RWB1BLE::gattc_event_handler(esp_gattc_cb_event_t event, esp_gatt_if_t gattc_if,
                                  esp_ble_gattc_cb_param_t *param) {
  if (!BLEClientBase::gattc_event_handler(event, gattc_if, param))
    return false;

  switch (event) {
    case ESP_GATTC_SEARCH_CMPL_EVT: {
      auto *write = this->get_characteristic(SERVICE_UUID, WRITE_UUID);
      auto *indicate = this->get_characteristic(SERVICE_UUID, INDICATE_UUID);
      if (write == nullptr || indicate == nullptr) {
        ESP_LOGE(TAG, "FED5/FED6 characteristics not found");
        this->status_set_error();
        this->disconnect();
        break;
      }
      this->write_handle_ = write->handle;
      this->indicate_handle_ = indicate->handle;
      const auto status = esp_ble_gattc_register_for_notify(this->get_gattc_if(), this->get_remote_bda(),
                                                            this->indicate_handle_);
      if (status != ESP_OK) {
        ESP_LOGE(TAG, "Failed to enable indications, status=%d", status);
        this->status_set_error();
      }
      break;
    }
    case ESP_GATTC_REG_FOR_NOTIFY_EVT:
      if (param->reg_for_notify.handle == this->indicate_handle_) {
        this->notify_registered_ = param->reg_for_notify.status == ESP_GATT_OK;
        if (this->notify_registered_) {
          ESP_LOGI(TAG, "RWB1 telemetry channel ready");
          this->last_poll_ = 0;
        }
      }
      break;
    case ESP_GATTC_WRITE_CHAR_EVT:
      if (param->write.handle == this->write_handle_ && this->request_pending_) {
        if (param->write.status != ESP_GATT_OK) {
          ESP_LOGW(TAG, "Read fragment failed, status=%d", param->write.status);
          this->request_pending_ = false;
          this->status_set_warning();
        } else {
          this->send_next_fragment_();
        }
      }
      break;
    case ESP_GATTC_NOTIFY_EVT:
      if (param->notify.handle == this->indicate_handle_)
        this->consume_fragment_(param->notify.value, param->notify.value_len);
      break;
    case ESP_GATTC_DISCONNECT_EVT:
    case ESP_GATTC_CLOSE_EVT:
      this->notify_registered_ = false;
      this->request_pending_ = false;
      this->write_handle_ = 0;
      this->indicate_handle_ = 0;
      this->rx_fragments_.clear();
      break;
    default:
      break;
  }
  return true;
}

bool RWB1BLE::prepare_request_() {
  if (this->write_handle_ == 0)
    return false;

  static constexpr char ALPHANUM[] = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
  char cmd_no[5];
  uint32_t random = esp_random();
  for (size_t i = 0; i < 4; i++) {
    cmd_no[i] = ALPHANUM[random % (sizeof(ALPHANUM) - 1)];
    random /= sizeof(ALPHANUM) - 1;
  }
  cmd_no[4] = '\0';

  char json[320];
  const int json_length = snprintf(
      json, sizeof(json),
      "{\"CID\":30024,\"PL\":{\"Req\":\"0503119500159091\",\"Uart\":{\"BaudRate\":2400,\"DataBit\":8,"
      "\"ParityBit\":\"NONE\",\"StopBit\":1},\"CmdType\":\"gatherSingleDevProps\",\"CmdNo\":\"%s\"}}",
      cmd_no);
  if (json_length <= 0 || static_cast<size_t>(json_length) >= sizeof(json))
    return false;

  const size_t padded_length = static_cast<size_t>(json_length) + (16 - static_cast<size_t>(json_length) % 16);
  std::vector<uint8_t> padded(padded_length, 0);
  memcpy(padded.data(), json, json_length);
  std::vector<uint8_t> encrypted(padded_length);
  std::array<uint8_t, 16> iv = this->key_;
  mbedtls_aes_context aes;
  mbedtls_aes_init(&aes);
  int result = mbedtls_aes_setkey_enc(&aes, this->key_.data(), 128);
  if (result == 0)
    result = mbedtls_aes_crypt_cbc(&aes, MBEDTLS_AES_ENCRYPT, padded.size(), iv.data(), padded.data(),
                                   encrypted.data());
  mbedtls_aes_free(&aes);
  if (result != 0) {
    ESP_LOGE(TAG, "Failed to encrypt read request");
    return false;
  }

  size_t encoded_length = 0;
  std::vector<uint8_t> encoded(((encrypted.size() + 2) / 3) * 4 + 1);
  result = mbedtls_base64_encode(encoded.data(), encoded.size(), &encoded_length, encrypted.data(), encrypted.size());
  if (result != 0)
    return false;
  encoded.resize(encoded_length);

  const size_t fragment_payload = std::max<size_t>(1, std::min<size_t>(227, this->mtu_ > 6 ? this->mtu_ - 6 : 17));
  const size_t total = (encoded.size() + fragment_payload - 1) / fragment_payload;
  if (total == 0 || total > 255)
    return false;
  this->tx_fragments_.clear();
  for (size_t offset = 0, index = 1; offset < encoded.size(); offset += fragment_payload, index++) {
    const size_t length = std::min(fragment_payload, encoded.size() - offset);
    std::vector<uint8_t> fragment;
    fragment.reserve(length + 3);
    fragment.push_back(static_cast<uint8_t>(index));
    fragment.push_back(static_cast<uint8_t>(total));
    fragment.push_back(static_cast<uint8_t>(length));
    fragment.insert(fragment.end(), encoded.begin() + offset, encoded.begin() + offset + length);
    this->tx_fragments_.push_back(std::move(fragment));
  }
  this->tx_index_ = 0;
  this->request_pending_ = true;
  this->request_started_ = millis();
  return true;
}

void RWB1BLE::send_next_fragment_() {
  if (!this->request_pending_ || this->tx_index_ >= this->tx_fragments_.size())
    return;
  auto &fragment = this->tx_fragments_[this->tx_index_++];
  const auto status = esp_ble_gattc_write_char(this->get_gattc_if(), this->get_conn_id(), this->write_handle_,
                                               fragment.size(), fragment.data(), ESP_GATT_WRITE_TYPE_RSP,
                                               ESP_GATT_AUTH_REQ_NONE);
  if (status != ESP_OK) {
    ESP_LOGW(TAG, "Could not send fragment, status=%d", status);
    this->request_pending_ = false;
    this->status_set_warning();
  } else {
    this->blink_activity_();
  }
}

void RWB1BLE::consume_fragment_(const uint8_t *data, size_t length) {
  if (length < 3)
    return;
  const uint8_t index = data[0];
  const uint8_t total = data[1];
  const uint8_t payload_length = data[2];
  if (index == 0 || total == 0 || index > total || payload_length != length - 3)
    return;
  if (index == 1 || total != this->rx_total_) {
    this->rx_total_ = total;
    this->rx_fragments_.assign(total, {});
  }
  if (this->rx_fragments_.size() != total)
    return;
  this->rx_fragments_[index - 1].assign(data + 3, data + length);
  for (const auto &fragment : this->rx_fragments_)
    if (fragment.empty())
      return;

  std::vector<uint8_t> message;
  for (const auto &fragment : this->rx_fragments_)
    message.insert(message.end(), fragment.begin(), fragment.end());
  this->rx_fragments_.clear();
  this->rx_total_ = 0;

  std::vector<uint8_t> frame;
  if (this->decrypt_response_(message, frame) && this->publish_modbus_(frame)) {
    this->status_clear_warning();
    ESP_LOGI(TAG, "Telemetry validated: 21 registers, CRC valid");
    this->blink_activity_();
  } else {
    ESP_LOGW(TAG, "Invalid RWB1 response");
    this->status_set_warning();
  }
  this->request_pending_ = false;
  this->tx_fragments_.clear();
}

bool RWB1BLE::decrypt_response_(const std::vector<uint8_t> &message, std::vector<uint8_t> &frame) {
  size_t decoded_length = 0;
  std::vector<uint8_t> encrypted((message.size() * 3) / 4 + 4);
  if (mbedtls_base64_decode(encrypted.data(), encrypted.size(), &decoded_length, message.data(), message.size()) != 0 ||
      decoded_length == 0 || decoded_length % 16 != 0)
    return false;
  encrypted.resize(decoded_length);

  std::vector<uint8_t> plaintext(encrypted.size());
  std::array<uint8_t, 16> iv = this->key_;
  mbedtls_aes_context aes;
  mbedtls_aes_init(&aes);
  int result = mbedtls_aes_setkey_dec(&aes, this->key_.data(), 128);
  if (result == 0)
    result = mbedtls_aes_crypt_cbc(&aes, MBEDTLS_AES_DECRYPT, encrypted.size(), iv.data(), encrypted.data(),
                                   plaintext.data());
  mbedtls_aes_free(&aes);
  if (result != 0)
    return false;
  while (!plaintext.empty() && plaintext.back() == 0)
    plaintext.pop_back();
  const std::string json(plaintext.begin(), plaintext.end());
  if (json.find("\"CID\":30025") == std::string::npos || json.find("\"RC\":0") == std::string::npos)
    return false;
  const std::string marker = "\"Rsp\":\"";
  const size_t start = json.find(marker);
  if (start == std::string::npos)
    return false;
  const size_t value_start = start + marker.size();
  const size_t end = json.find('"', value_start);
  if (end == std::string::npos)
    return false;
  return this->hex_to_bytes_(json.substr(value_start, end - value_start), frame);
}

bool RWB1BLE::publish_modbus_(const std::vector<uint8_t> &frame) {
  if (frame.size() != 47 || frame[0] != MODBUS_REQUEST[0] || frame[1] != 0x03 || frame[2] != 42)
    return false;
  const uint16_t expected_crc = frame[frame.size() - 2] | (static_cast<uint16_t>(frame.back()) << 8);
  if (this->crc16_modbus_(frame.data(), frame.size() - 2) != expected_crc)
    return false;
  std::array<uint16_t, 21> words{};
  for (size_t i = 0; i < words.size(); i++)
    words[i] = frame[3 + i * 2] | (static_cast<uint16_t>(frame[4 + i * 2]) << 8);

  if (this->status_sensor_ != nullptr) this->status_sensor_->publish_state(words[0]);
  if (this->grid_voltage_sensor_ != nullptr) this->grid_voltage_sensor_->publish_state(words[1] * 0.1f);
  if (this->grid_frequency_sensor_ != nullptr) this->grid_frequency_sensor_->publish_state(words[2] * 0.1f);
  if (this->pv_voltage_sensor_ != nullptr) this->pv_voltage_sensor_->publish_state(words[3] * 0.1f);
  if (this->pv_power_sensor_ != nullptr) this->pv_power_sensor_->publish_state(words[4]);
  if (this->battery_voltage_sensor_ != nullptr) this->battery_voltage_sensor_->publish_state(words[5] * 0.1f);
  if (this->battery_soc_sensor_ != nullptr) this->battery_soc_sensor_->publish_state(words[6]);
  if (this->battery_charge_current_sensor_ != nullptr) this->battery_charge_current_sensor_->publish_state(words[7]);
  if (this->battery_discharge_current_sensor_ != nullptr)
    this->battery_discharge_current_sensor_->publish_state(words[8]);
  if (this->output_voltage_sensor_ != nullptr) this->output_voltage_sensor_->publish_state(words[9] * 0.1f);
  if (this->output_frequency_sensor_ != nullptr) this->output_frequency_sensor_->publish_state(words[10] * 0.1f);
  if (this->load_apparent_power_sensor_ != nullptr) this->load_apparent_power_sensor_->publish_state(words[11]);
  if (this->load_active_power_sensor_ != nullptr) this->load_active_power_sensor_->publish_state(words[12]);
  if (this->load_percent_sensor_ != nullptr) this->load_percent_sensor_->publish_state(words[13]);
  if (this->rated_power_sensor_ != nullptr) this->rated_power_sensor_->publish_state(words[20]);
  return true;
}

void RWB1BLE::blink_activity_() {
  if (this->activity_led_ == nullptr)
    return;
  this->activity_led_->digital_write(true);
  this->set_timeout("activity_led", 100, [this]() { this->activity_led_->digital_write(false); });
}

uint16_t RWB1BLE::crc16_modbus_(const uint8_t *data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < length; i++) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; bit++)
      crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
  }
  return crc;
}

bool RWB1BLE::hex_to_bytes_(const std::string &hex, std::vector<uint8_t> &out) {
  if (hex.size() % 2 != 0)
    return false;
  out.clear();
  out.reserve(hex.size() / 2);
  auto nibble = [](char value) -> int {
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    return -1;
  };
  for (size_t i = 0; i < hex.size(); i += 2) {
    const int high = nibble(hex[i]);
    const int low = nibble(hex[i + 1]);
    if (high < 0 || low < 0)
      return false;
    out.push_back(static_cast<uint8_t>((high << 4) | low));
  }
  return true;
}

}  // namespace esphome::rwb1_ble
