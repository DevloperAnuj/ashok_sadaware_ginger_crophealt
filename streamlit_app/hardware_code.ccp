#include <DHT.h>
#define DHTPIN 14
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);
//******************************************

#include <BluetoothSerial.h>
BluetoothSerial SerialBT;

volatile bool btConnected = false;
volatile bool btStateChanged = false;

void btCallback(esp_spp_cb_event_t event, esp_spp_cb_param_t *param) {
  if (event == ESP_SPP_SRV_OPEN_EVT) {
    btConnected = true;
    btStateChanged = true;
  } else if (event == ESP_SPP_CLOSE_EVT) {
    btConnected = false;
    btStateChanged = true;
  }
}

#include <LiquidCrystal.h>


// LCD Pins


LiquidCrystal lcd(18,19,21,17,5,22);


// Sensor Pins

#define PH_PIN    35
#define mo  34


float phValue = 0;
int moist = 0;

void setup() {
  Serial.begin(115200);
  SerialBT.register_callback(btCallback);
  SerialBT.begin("GingerMonitor");

  dht.begin();
  pinMode(mo, INPUT);

  lcd.begin(16, 2);
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("Soil Monitor");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");
  delay(2000);
  lcd.clear();
}

void loop() {

  if (btStateChanged) {
    btStateChanged = false;
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(btConnected ? "BT Connected" : "BT Disconnected");
    lcd.setCursor(0, 1);
    lcd.print(btConnected ? "Sending data..." : "Waiting phone..");
    delay(2000);
  }

float t = dht.readTemperature();
  float h = dht.readHumidity();


  moist = analogRead(mo);

Serial.print("RAW_m: ");
Serial.println(moist);

  // Read pH

  int phRaw = analogRead(PH_PIN);
  Serial.print("PH raw1:");
  Serial.println(phRaw);
  float voltagePH = phRaw * (3.3 / 4095.0);
  Serial.print("voltagePH:");
  Serial.println(voltagePH);
  phValue = 2 * voltagePH;     // Adjust after calibration

 

  // Serial Monitor
  Serial.println("----- Water Data -----");
  Serial.print("M_Lvl: ");
  Serial.println(moist);


  Serial.print("pH: ");
  Serial.println(phValue);

  Serial.print("T: ");
  Serial.println(t);

  Serial.print("h: ");
  Serial.println(h);

  // Bluetooth output
  SerialBT.println("----- Soil Data -----");
  SerialBT.print("Moisture: ");  SerialBT.println(moist);
  SerialBT.print("pH: ");        SerialBT.println(phValue);
  SerialBT.print("Temp: ");      SerialBT.println(t);
  SerialBT.print("Humidity: ");  SerialBT.println(h);

  // LCD Display
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("M_L:");
  lcd.print(moist);
  lcd.print(" PH:");
  lcd.print(phValue, 1);

  lcd.setCursor(0, 1);

  lcd.print("T:");
  lcd.print(t);
  lcd.print(" H:");
  lcd.print(h);

  lcd.setCursor(15, 0);
  lcd.print(btConnected ? "*" : " ");

  delay(1500);
}