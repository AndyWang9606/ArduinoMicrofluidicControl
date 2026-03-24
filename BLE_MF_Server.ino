#include <ArduinoBLE.h>
#include <ContinuousStepper.h>
#include <ArduinoLowPower.h>

BLEService ledService("19B10000-E8F2-537E-4F6C-D104768A1214"); // Bluetooth® Low Energy LED Service
BLEService motorService("265470a5-21a7-4c8c-bb5a-b0d18d9c4324"); // Motor Control Service
BLEService calibrationService("3f525e2d-b187-4eac-9e7d-cef297c15f08");
BLEService idleHourService("c29af831-47b4-4aac-bf9a-27a98f64ed66");
BLEService idleMinuteService("e96a07a9-9469-476c-a677-51764916b957");

// Bluetooth® Low Energy LED Switch Characteristic - custom 128-bit UUID, read and writable by central
BLEByteCharacteristic countdownCharacteristic("19B10001-E8F2-537E-4F6C-D104768A1214", BLERead);
BLELongCharacteristic motorCharacteristic("265470a5-21a7-4c8c-bb5a-b0d18d9c4324", BLERead | BLEWrite);
BLEIntCharacteristic calibrationCharacteristic("3f525e2d-b187-4eac-9e7d-cef297c15f08", BLERead | BLEWrite);
BLEIntCharacteristic idleHourCharacteristic("c29af831-47b4-4aac-bf9a-27a98f64ed66", BLERead | BLEWrite);
BLEIntCharacteristic idleMinuteCharacteristic("e96a07a9-9469-476c-a677-51764916b957", BLERead | BLEWrite);

ContinuousStepper<StepperDriver> stepper;

const int ledPin = LED_BUILTIN; // pin to use for the LED
const int stepPin = 3;
const int dirPin = 2;
const int sleepPin = 4; 

bool marked = false;
bool BLEOn = false;
bool stepperInit = false;
long lastTotalMillis = 0;
long lastCalibrationMillis = 0;
long lastLowSpeedMillis = 0;
long lastLowSpeedStateMillis = 0;
long prevMotorSpeed = 0;

bool lowSpeed = false;

long real_disconnect_time = 60L * 1000 * 5;
long real_idle_time = 3600L * 1000 * 6;
long minute_time = 60L * 1000;
long lowSpeedStateHigh_time = 0;

long disconnect_time = 0;
long idle_time = 0;

void checkLowSpeed() {
  // if low speed flag is set
  //    if total time exceeds one minute, reset all timers
  //    if on timer is still going, stepper.spin(-1000)
  //    if not, stepper.spin(0)
  if (lowSpeed) {
    if (millis() - lastLowSpeedMillis >= minute_time) {
      lastLowSpeedMillis = millis();
      lastLowSpeedStateMillis = millis();
    }
    if (millis() - lastLowSpeedStateMillis >= lowSpeedStateHigh_time) {
      stepper.spin(-1000);
    }
    else {
      stepper.spin(0);
    }
  }
}

void BLESetup() {
  if (!BLE.begin()) {
    // Serial.println("starting Bluetooth® Low Energy module failed!");

    while (1);
  }

  // set advertised local name and service UUID:
  BLE.setLocalName("HELLO WORLD!");
  BLE.setAdvertisedService(ledService);
  BLE.setAdvertisedService(motorService);
  BLE.setAdvertisedService(calibrationService);
  BLE.setAdvertisedService(idleHourService);
  BLE.setAdvertisedService(idleMinuteService);

  // add the characteristic to the service
  ledService.addCharacteristic(countdownCharacteristic);
  motorService.addCharacteristic(motorCharacteristic);
  calibrationService.addCharacteristic(calibrationCharacteristic);
  idleHourService.addCharacteristic(idleHourCharacteristic);
  idleMinuteService.addCharacteristic(idleMinuteCharacteristic);

  // add service
  BLE.addService(ledService);
  BLE.addService(motorService);
  BLE.addService(calibrationService);
  BLE.addService(idleHourService);
  BLE.addService(idleMinuteService);

  // set the initial value for the characteristic:
  countdownCharacteristic.writeValue(0);
  motorCharacteristic.writeValue(prevMotorSpeed);
  // Serial.println(motorCharacteristic.value());
  calibrationCharacteristic.writeValue(0);
  idleHourCharacteristic.writeValue(6);
  idleMinuteCharacteristic.writeValue(0);

  // start advertising
  BLE.advertise();

  // Serial.println("STARTED");
  if (!stepperInit) {
    stepper.begin(stepPin, dirPin);
    stepper.spin(-motorCharacteristic.value());
  }

  // Serial.println("BLE LED Peripheral");
  BLEOn = true;
  stepperInit = true;
}

void setup() {
  //Serial.begin(9600); 
  //while (!Serial);

  // set LED pin to output mode
  pinMode(ledPin, OUTPUT);
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(sleepPin, OUTPUT);

  // begin initialization
  BLESetup();

  digitalWrite(sleepPin, HIGH);
}

void loop() {

  // listen for Bluetooth® Low Energy peripherals to connect:
  if (BLEOn) {
    BLEDevice central = BLE.central();

    // if a central is connected to peripheral:
    if (central) {
      // Serial.print("Connected to central: ");
      // print the central's MAC address:
      // Serial.println(central.address());

      // while the central is still connected to peripheral:
      while (central.connected()) {
        // if the remote device wrote to the characteristic,
        // use the value to control the LED:
        if (motorCharacteristic.written()) {
          prevMotorSpeed = motorCharacteristic.value();
          // Serial.println(prevMotorSpeed);
          if (prevMotorSpeed < 1000 && prevMotorSpeed != 0) {
            // Set timer for interval (ask Weibo what interval is needed)
            stepper.spin(-1000);
            // set low speed flag
            lowSpeed = true;
            // begin tracking time
            lastLowSpeedMillis = millis();
            lastLowSpeedStateMillis = millis();
            lowSpeedStateHigh_time = long(double(prevMotorSpeed) / 1000.0 * minute_time);
          }
          else {
            lowSpeed = false;
            stepper.spin(-motorCharacteristic.value());
          }
          lastTotalMillis = millis();
          if (!marked && !calibrationCharacteristic.value()) {
            countdownCharacteristic.writeValue(1);
            disconnect_time = real_disconnect_time;
            idle_time = real_idle_time;
            marked = true;
          }
        }
        if (marked && (millis() - lastTotalMillis >= disconnect_time)) {
          BLE.end();
          BLEOn = false;
          // Serial.println("DISCO");
          stepper.loop();
          break;
        }

        // if calibration mode
        //    if total time exceeds one minute, stepper.spin(0)
        if (calibrationCharacteristic.value()) {
          if (millis() - lastTotalMillis >= minute_time) {
            motorCharacteristic.writeValue(0);
            stepper.spin(0);
          }
        }

        // if low speed flag is set
        //    if total time exceeds one minute, reset all timers
        //    if on timer is still going, stepper.spin(-1000)
        //    if not, stepper.spin(0)
        checkLowSpeed();

        // if total period is written to (make a new characteristic)
        //    set real_idle_time somehow idk (maybe go hours minute)
        if (idleHourCharacteristic.written()) {
          real_idle_time = 3600L * 1000 * idleHourCharacteristic.value();
        }
        if (idleMinuteCharacteristic.written()) {
          real_idle_time += 60L * 1000 * idleMinuteCharacteristic.value();
        }
        if (idleHourCharacteristic.written() || idleMinuteCharacteristic.written()) {
          idle_time = real_idle_time;
        }
        stepper.loop(); 
      }
    }
  }
  else {
    if (millis() - lastTotalMillis >= idle_time) {
      // Will deep sleep board upon timer hit
      stepper.spin(0);
      LowPower.deepSleep();
    }
  }
  // if low speed flag is set
  //    if total time exceeds one minute, reset all timers
  //    if on timer is still going, stepper.spin(-1000)
  //    if not, stepper.spin(0)
  checkLowSpeed();
  stepper.loop();
  
}
