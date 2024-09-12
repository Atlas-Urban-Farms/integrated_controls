#include <ArduinoJson.h>
#include <WiFi.h>
#include <string.h>

void respondToMessage(const char *id, JsonDocument data, JsonDocument (*handler)(JsonDocument data));
JsonDocument respondConfirmIdentity(JsonDocument data);

#define ConfirmIdentity "CC1"
#define StartWater "CC2"
#define EndWater "CC3"
#define StartLight "CC4"
#define EndLight "CC5"

char mac[6];

constexpr unsigned int hash(const char *s, int off = 0) {
  return !s[off] ? 5381 : (hash(s, off+1)*33) ^ s[off];                           
} 

void setup()
{
  Serial.begin(9600);

  byte temp[6];

  WiFi.macAddress(temp);

  sprintf(mac, "%02X:%02X:%02X:%02X:%02X:%02X", temp[0], temp[1], temp[2], temp[3], temp[4], temp[5]);
}

void loop()
{
  if (Serial.available())
  {
    String stringMessage = Serial.readStringUntil('\0');

    JsonDocument message;
    deserializeJson(message, stringMessage);

    const char *code = message["code"];
    const char *id = message["id"];
    JsonObjectConst data = message["data"].as<JsonObject>();

    switch (hash(code))
    {
    case hash(ConfirmIdentity):
      respondToMessage(id, data, respondConfirmIdentity);
    }
  }
}



void respondToMessage(const char *id, JsonObjectConst data, JsonDocument (*handler)(JsonObjectConst data))
{
  JsonDocument doc;

  JsonDocument resp = handler(data);

  doc["command_id"] = id;
  doc["data"] = resp;
  doc["serial_number"] = mac;

  String output;

  doc.shrinkToFit();

  serializeJson(doc, output);

  Serial.print(output);
  Serial.write((byte) 0x00);
}

JsonDocument respondConfirmIdentity(JsonObjectConst data)
{
  JsonDocument doc;

  doc["serial_number"] = mac;
  doc["name"] = "AUF-00000";
  doc["used_memory"] = rp2040.getUsedHeap();
  doc["free_memory"] = rp2040.getFreeHeap();
  doc["total_memory"] = rp2040.getTotalHeap();

  return doc;
}