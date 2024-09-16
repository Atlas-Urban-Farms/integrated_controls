#include <ArduinoJson.h>
#include <WiFi.h>
#include <string.h>

void playStartup(void);
void respondToMessage(const char *id, JsonDocument data, JsonDocument (*handler)(JsonDocument data));
JsonDocument respondUnimplemented(JsonObjectConst data);
JsonDocument respondConfirmIdentity(JsonDocument data);
JsonDocument respondStartWater(JsonObjectConst data);
JsonDocument respondStartLight(JsonObjectConst data);


// command codes
#define ConfirmIdentity "CC1"
#define StartWater "CC2"
#define EndWater "CC3"
#define StartLight "CC4"
#define EndLight "CC5"

// pins
#define BUZZER_PIN 15
#define PUMP_PIN 2
#define LED_PIN 3
#define AUX1_PIN 6
#define AUX2_PIN 7
#define AUX3_PIN 8
#define AUX4_PIN 9

char mac[6];

constexpr unsigned int hash(const char *s, int off = 0) {
  return !s[off] ? 5381 : (hash(s, off+1)*33) ^ s[off];                           
} 

void play_startup(void)
{
  #ifdef BUZZER_PIN 
  tone(BUZZER_PIN, 440, 250);
  delay(125);
  tone(BUZZER_PIN, 440, 250);
  delay(125);
  tone(BUZZER_PIN, 880, 500);
  #endif
}

void pin_setup(void)
{
  /* this just sets up the pinmodes and outputs 
  for all the pins that need it */
  pinMode(LED_BUILTIN,OUTPUT);
  digitalWrite(LED_BUILTIN,HIGH);
  //SET PINMODES
  #ifdef BUZZER_PIN
  pinMode(BUZZER_PIN,OUTPUT);
  #endif
  pinMode(PUMP_PIN,OUTPUT);
  pinMode(LED_PIN,OUTPUT);
  pinMode(AUX1_PIN,OUTPUT);
  pinMode(AUX2_PIN,OUTPUT);
  pinMode(AUX3_PIN,OUTPUT);
  pinMode(AUX4_PIN,OUTPUT);
  //set mosfets to off
  //digitalWrite(PUMP_PIN, HIGH);
  //delay(10000);
  digitalWrite(PUMP_PIN, LOW);
  analogWrite(LED_PIN, 0);
  digitalWrite(AUX1_PIN, LOW);
  digitalWrite(AUX2_PIN, LOW);
  digitalWrite(AUX3_PIN, LOW);
  digitalWrite(AUX4_PIN, LOW);
}

void setup()
{
  Serial.begin(9600);
  Serial.flush();

  pin_setup();

  byte temp[6];
  WiFi.macAddress(temp);
  sprintf(mac, "%02X:%02X:%02X:%02X:%02X:%02X", temp[0], temp[1], temp[2], temp[3], temp[4], temp[5]);
}

unsigned long waterStart;
unsigned long waterDuration;
unsigned long lightStart;
unsigned long lightDuration;

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
    case hash(StartWater):
      respondToMessage(id, data, respondStartWater);
    case hash(StartLight):
      respondToMessage(id, data, respondStartLight);
    default:
      respondToMessage(id, data, respondUnimplemented);
    }
  }

  unsigned long now = millis();

  digitalWrite(PUMP_PIN, now > waterStart + waterDuration);
  digitalWrite(LED_PIN, now > lightStart + lightDuration);
}

void playStartup(void)
{
  #ifdef BUZZER_PIN 
  tone(BUZZER_PIN, 440, 250);
  delay(125);
  tone(BUZZER_PIN, 440, 250);
  delay(125);
  tone(BUZZER_PIN, 880, 500);
  #endif
}

void respondToMessage(const char *id, JsonObjectConst data, JsonDocument (*handler)(JsonObjectConst data))
{
  JsonDocument doc;

  JsonDocument respData = handler(data);

  doc["command_id"] = id;
  doc["data"] = respData;
  doc["serial_number"] = mac;

  String output;

  doc.shrinkToFit();

  serializeJson(doc, output);

  Serial.print(output);
  Serial.write((byte) 0x00);
}

JsonDocument respondUnimplemented(JsonObjectConst data)
{
  JsonDocument doc;

  doc["error"] = "Not Implemented";

  return doc;
}

JsonDocument respondConfirmIdentity(JsonObjectConst data)
{
  JsonDocument doc;

  doc["used_memory"] = rp2040.getUsedHeap();
  doc["free_memory"] = rp2040.getFreeHeap();
  doc["total_memory"] = rp2040.getTotalHeap();

  playStartup();

  return doc;
}

JsonDocument respondStartWater(JsonObjectConst data)
{
  JsonDocument doc;

  unsigned long duration = data["duration"].as<unsigned long>();

  if (duration > 5 * 60000) { // if duration is longer than 5 minutes
    doc["error"] = "Watering Duration Longer Than 5 Minutes";
    return doc;
  }

  waterStart = millis();
  waterDuration = duration;

  return doc;
}

JsonDocument respondStartLight(JsonObjectConst data)
{
  JsonDocument doc;

  unsigned long duration = data["duration"].as<unsigned long>();

  lightStart = millis();
  lightDuration = duration;

  return doc;
}