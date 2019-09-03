#include <Adafruit_Sensor.h>
#include <ArduinoJson.h>
#include <DHT.h>

#if SIMULATED_DATA

void initSensor() {
    // use SIMULATED_DATA, no sensor need to be inited
}

float readTemperature() {
    return random(20, 30);
}

float readHumidity() {
    return random(30, 40);
}

#else

static DHT dht(DHT_PIN, DHT_TYPE);
void initSensor() {
    dht.begin();
}

float readTemperature() {
    return dht.readTemperature();
}

float readHumidity() {
    return dht.readHumidity();
}

int readMoisture() {
    int val = analogRead(SOIL_PIN);
    return val;// * 100.0 / 1024.0;
}

#endif

bool readMessage(int messageId, char *payload)
{
    float temperature = 0.0, humidity = 0.0;
    int moisture = 0, h_count = 0, t_count = 0;

    // Take average over N samples
    int N = 200;
    for (int i = 0; i < N; i++) {
        float tempTemp = readTemperature();
        float humidityTemp = readHumidity();
        moisture += readMoisture();
        
        if (!std::isnan(humidityTemp)) {
            humidity += humidityTemp;
            h_count += 1;
        }
        if (!std::isnan(tempTemp)) {
            temperature += tempTemp;
            t_count += 1;
        }
    }

    // Find average of values
    moisture = moisture / N;
    if (h_count > 0) 
        humidity = humidity / h_count;
    if (t_count > 0)
        temperature = temperature / t_count;

    StaticJsonBuffer<MESSAGE_MAX_LEN> jsonBuffer;
    JsonObject &root = jsonBuffer.createObject();
    root["messageId"] = messageId;
    bool temperatureAlert = false;

    // NAN is not the valid json, change it to NULL
    // Temperature
    if (t_count == 0 || std::isnan(temperature))
        root["temperature"] = NULL;
    else {
        root["temperature"] = temperature;
        if (temperature > TEMPERATURE_ALERT)
            temperatureAlert = true;
    }

    // Humidity
    if (h_count == 0 || std::isnan(humidity)) root["humidity"] = NULL;
    else root["humidity"] = humidity;

    // Moisture
    root["moisture"] = moisture;

    // To store message in cloud
    root["level"] = "storage";
    
    root.printTo(payload, MESSAGE_MAX_LEN);
    return temperatureAlert;
}

void parseTwinMessage(char *message)
{
    StaticJsonBuffer<MESSAGE_MAX_LEN> jsonBuffer;
    JsonObject &root = jsonBuffer.parseObject(message);
    if (!root.success()) {
        Serial.printf("Parse %s failed.\r\n", message);
        return;
    }

    if (root["desired"]["interval"].success()) {
        interval = root["desired"]["interval"];
    }
    else if (root.containsKey("interval")) {
        interval = root["interval"];
    }
}
