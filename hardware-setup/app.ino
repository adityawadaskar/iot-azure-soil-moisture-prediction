// Aditya Wadaskar, Sayali Kakade, Himangshu Chowdhury
// UCSB CS 293S - Winter 2019
// Final Project - Soil Moisture Prediction

#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiUdp.h>

#include <AzureIoTHub.h>
#include <AzureIoTProtocol_MQTT.h>
#include <AzureIoTUtility.h>

#include "config.h"

// WiFi Settings
static char *ssid = "Corinne Barnes <3";
static char *pass = "iobject!";

// Connection Settings
static char *connectionString = "HostName=soil-moisture-hub-free-293s.azure-devices.net;DeviceId=soil-moisture-sensor-device;SharedAccessKey=hHIPMtMSyEpRjo0eH8zOWQ3HCD3EI80qH0j9Rub0Va4=";

// Message Status
static bool messagePending = false;
static bool messageSending = true;

static int interval = INTERVAL;
static int messageCount = 1;
static IOTHUB_CLIENT_LL_HANDLE iotHubClientHandle;


// Soil Moisture Sensor
/* The default dry and wet values for the sensor are 520 and 260 (no voltage divider). 
 *  To calibrate your sensor, run this code and open the Serial Monitor.
 *  Record the value being measured as your new "dry" value.
 *  Insert the sensor to the white line in a cup of water. Record the new reading as the "wet" value.
 */
const int dryVal = 3; //567;
const int wetVal = 500; //367;

// Hardware Setup
void setup() {
    
    pinMode(LED_PIN, OUTPUT);

    // Initialize operations
    initSerial();
    delay(2000);
    initWifi();
    initTime();
    initSensor();

    // Setup iotHubClientHandle parameters
    iotHubClientHandle = IoTHubClient_LL_CreateFromConnectionString(connectionString, MQTT_Protocol);
    if (iotHubClientHandle == NULL) {
        Serial.println("Failed on IoTHubClient_CreateFromConnectionString.");
        while (1);
    }

    // Setup iotHubClientHandle parameters
    IoTHubClient_LL_SetOption(iotHubClientHandle, "product_info", "HappyPath_AdafruitFeatherHuzzah-C");
    IoTHubClient_LL_SetMessageCallback(iotHubClientHandle, receiveMessageCallback, NULL);
    IoTHubClient_LL_SetDeviceMethodCallback(iotHubClientHandle, deviceMethodCallback, NULL);
    IoTHubClient_LL_SetDeviceTwinCallback(iotHubClientHandle, twinCallback, NULL);
}


//Collect, process, and upload data
void loop() {
    if (!messagePending && messageSending) {
        char messagePayload[MESSAGE_MAX_LEN];
        bool temperatureAlert = readMessage(messageCount, messagePayload);
        sendMessage(iotHubClientHandle, messagePayload, temperatureAlert);
        messageCount++;
        delay(interval);
    }
    IoTHubClient_LL_DoWork(iotHubClientHandle);
    delay(10);
}

void blinkLED() {
    digitalWrite(LED_PIN, HIGH);
    delay(500);
    digitalWrite(LED_PIN, LOW);
}

void initWifi() {
    // Attempt to connect to Wifi network:
    Serial.printf("Attempting to connect to SSID: %s.\r\n", ssid);

    // Connect to WPA/WPA2 network. Change this line if using open or WEP network:
    WiFi.begin(ssid, pass);
    while (WiFi.status() != WL_CONNECTED)
    {
        // Get Mac Address and show it. WiFi.macAddress(mac) save the mac address into a six length array, but the endian may be different.
        // The huzzah board should start from mac[0] to mac[5], but some other kinds of board run in the oppsite direction.
        uint8_t mac[6];
        WiFi.macAddress(mac);
        Serial.printf("You device with MAC address %02x:%02x:%02x:%02x:%02x:%02x connects to %s failed! Waiting 10 seconds to retry.\r\n",
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5], ssid);
        WiFi.begin(ssid, pass);
        delay(10000);
    }
    Serial.printf("Connected to wifi %s.\r\n", ssid);
}

void initTime() {
    time_t epochTime;
    configTime(-8 * 3600, 0, "pool.ntp.org", "time.nist.gov");
    while (true) {
        epochTime = time(NULL);
        if (epochTime == 0) {
            Serial.println("Fetching NTP epoch time failed! Waiting 2 seconds to retry.");
            delay(2000);
        }
        else {
            Serial.printf("Fetched NTP epoch time is: %lu.\r\n", epochTime);
            break;
        }
    }
}
