import asyncio
import datetime
import os
import numpy as np

from bleak import BleakClient
from bleak import BleakScanner
import aioconsole

DEVICE_NAME ='HELLO WORLD!'
MOTOR_UUID = '265470a5-21a7-4c8c-bb5a-b0d18d9c4324'
COUNTDOWN_UUID = '19B10001-E8F2-537E-4F6C-D104768A1214'
CALIBRATION_UUID = '3f525e2d-b187-4eac-9e7d-cef297c15f08'
DURATION_HOUR_UUID = 'c29af831-47b4-4aac-bf9a-27a98f64ed66'
DURATION_MINUTE_UUID = 'e96a07a9-9469-476c-a677-51764916b957'

writeMotorUL = False
writeMotorSPS = False
writeDurationMode = False
readMotor = False
calibrateMode = False
mainMenuOn = True
prevCountdownActive = 0
countdownActive = 0
disconnect_time = None
next_active_time = None
clear = lambda: os.system('cls')

slope = 0.015

calibrationMotorArray = [1000., 2000., 3000., 4000.]
calibrationResponseArray = [0., 0., 0., 0.]

startTime = None

async def connect_and_read():
    global countdownActive
    while True:
        print("Searching...")
        myDevice = ""
        devices = await BleakScanner.discover(5.0, return_adv=True)
        for d in devices:
            if (devices[d][1].local_name == DEVICE_NAME):
                clear()
                print("Connected")
                myDevice = d
        if not myDevice:
            continue
        address = myDevice
        async with BleakClient(address) as client:
            while client.is_connected:
                try:
                    countdownActive = await client.read_gatt_char(COUNTDOWN_UUID)
                    countdownActive = int.from_bytes(countdownActive, byteorder='little')
                    if countdownActive != 0:
                        print(f"Disconnecting at: {disconnect_time}")
                        print(f"Next active at: {next_active_time}\n")
                    await mainMenu(client)
                    await checkMotorSpeed(client)
                    await writeuL(client)
                    await writesps(client)
                    await calibrate(client)
                    await writeDuration(client)
                except OSError:
                    pass
            print("Disconnected")

async def writeuL(client):
    global writeMotorUL, mainMenuOn, prevCountdownActive, next_active_time, disconnect_time, countdownActive, startTime
    if client.is_connected and writeMotorUL:
        print("Enter q to go back to main menu")
        print(f"Valid Range: 0-{4000 * slope}")
        user_response = await aioconsole.ainput("Motor Speed (uL/minute): ")
        if not user_response.replace('.', '', 1).isdigit() and not user_response == "q":
            clear()
            print("Please enter a valid number")
            return
        if user_response == "q":
            writeMotorUL = False
            mainMenuOn = True
        elif float(user_response) < 0 or float(user_response) > 4000 * slope:
            clear()
            print("Please enter a valid number")
            return
        else:
            user_response = float(user_response) / slope
            byte_user_response = bytearray(int(user_response).to_bytes(16, byteorder='little'))
            await client.write_gatt_char(MOTOR_UUID, byte_user_response)  # Send command
            countdownActive = await client.read_gatt_char(COUNTDOWN_UUID)
            countdownActive = int.from_bytes(countdownActive, byteorder='little')
            if prevCountdownActive != countdownActive:
                if countdownActive != 0:
                    startTime = datetime.datetime.now()
                    hours = int.from_bytes(await client.read_gatt_char(DURATION_HOUR_UUID), byteorder='little')
                    minutes = int.from_bytes(await client.read_gatt_char(DURATION_MINUTE_UUID), byteorder='little')
                    next_active_time = startTime + datetime.timedelta(hours=hours, minutes=minutes)
                    disconnect_time = startTime + datetime.timedelta(minutes=5)
        clear()
        prevCountdownActive = countdownActive

async def writesps(client):
    global writeMotorSPS, mainMenuOn, prevCountdownActive, next_active_time, disconnect_time, countdownActive, startTime
    if client.is_connected and writeMotorSPS:
        print("Enter q to go back to main menu")
        print(f"Valid Range: 0-4000")
        user_response = await aioconsole.ainput("Motor Speed (steps/second): ")
        if not user_response.isdigit() and not user_response == "q":
            clear()
            print("Please enter a valid number")
            return
        if user_response == "q":
            writeMotorSPS = False
            mainMenuOn = True
        elif int(user_response) < 0 or int(user_response) > 4000:
            clear()
            print("Please enter a valid number")
            return
        else:
            byte_user_response = bytearray(int(user_response).to_bytes(16, byteorder='little'))
            await client.write_gatt_char(MOTOR_UUID, byte_user_response)  # Send command
            countdownActive = await client.read_gatt_char(COUNTDOWN_UUID)
            countdownActive = int.from_bytes(countdownActive, byteorder='little')
            if prevCountdownActive != countdownActive:
                if countdownActive != 0:
                    startTime = datetime.datetime.now()
                    hours = int.from_bytes(await client.read_gatt_char(DURATION_HOUR_UUID), byteorder='little')
                    minutes = int.from_bytes(await client.read_gatt_char(DURATION_MINUTE_UUID), byteorder='little')
                    next_active_time = startTime + datetime.timedelta(hours=hours, minutes=minutes)
                    disconnect_time = startTime + datetime.timedelta(minutes=5)
        clear()
        prevCountdownActive = countdownActive

async def checkMotorSpeed(client):
    global readMotor, mainMenuOn
    if client.is_connected and readMotor:
        datafromBLE = await client.read_gatt_char(MOTOR_UUID)
        datafromBLE = datafromBLE[-4:]
        current = int.from_bytes(datafromBLE, "little")
        uLperMin = current  * slope
        print("Current Motor Speed: " + str(uLperMin) + " (uL/minute)")
        print("                     " + str(current) + " (steps/second)")
        await aioconsole.ainput("Press RETURN to go back to main menu")
        readMotor = False
        mainMenuOn = True
        clear()

async def calibrate(client):
    global mainMenuOn, calibrateMode, slope
    if client.is_connected and calibrateMode:
        user_response = await aioconsole.ainput("Ready for calibration (y\\n)? ")
        if user_response.lower() == "y":
            print("Writing to motor 4000 steps/second...")
            await client.write_gatt_char(CALIBRATION_UUID, bytearray(int(1).to_bytes(1, byteorder='little')))
            # set motor speed to 4000
            await client.write_gatt_char(MOTOR_UUID, bytearray(int(4000).to_bytes(16, byteorder='little')))
            print("Motor running...")
            await asyncio.sleep(60)
            # ask for data value and store somewhere
            user_response = await aioconsole.ainput("Type measured amount for 4000 steps/second: ")
            while not user_response.replace('.', '', 1).isdigit():
                clear()
                print("Please enter a valid number")
                user_response = await aioconsole.ainput("Type measured amount for 4000 steps/second: ")
            calibrationResponseArray[3] = float(user_response)
            clear()
            # repeat for 3000, 2000, 1000
            print("Writing to motor 3000 steps/second...")
            await client.write_gatt_char(MOTOR_UUID, bytearray(int(3000).to_bytes(16, byteorder='little')))
            print("Motor running...")
            await asyncio.sleep(60)
            user_response = await aioconsole.ainput("Type measured amount for 3000 steps/second: ")
            while not user_response.replace('.', '', 1).isdigit():
                clear()
                print("Please enter a valid number")
                user_response = await aioconsole.ainput("Type measured amount for 3000 steps/second: ")
            calibrationResponseArray[2] = float(user_response)

            print("Writing to motor 2000 steps/second...")
            await client.write_gatt_char(MOTOR_UUID, bytearray(int(2000).to_bytes(16, byteorder='little')))
            print("Motor running...")
            await asyncio.sleep(60)
            user_response = await aioconsole.ainput("Type measured amount for 2000 steps/second: ")
            while not user_response.replace('.', '', 1).isdigit():
                clear()
                print("Please enter a valid number")
                user_response = await aioconsole.ainput("Type measured amount for 2000 steps/second: ")
            calibrationResponseArray[1] = float(user_response)

            print("Writing to motor 1000 steps/second...")
            await client.write_gatt_char(MOTOR_UUID, bytearray(int(1000).to_bytes(16, byteorder='little')))
            print("Motor running...")
            await asyncio.sleep(60)
            user_response = await aioconsole.ainput("Type measured amount for 1000 steps/second: ")
            while not user_response.replace('.', '', 1).isdigit():
                clear()
                print("Please enter a valid number")
                user_response = await aioconsole.ainput("Type measured amount for 1000 steps/second: ")
            calibrationResponseArray[0] = float(user_response)
            # perform np.polyfit
            coefficients = np.polyfit(calibrationMotorArray, calibrationResponseArray, 1)
            # store slope and use that for calculating uL/min
            slope = coefficients[0]
            mainMenuOn = True
            calibrateMode = False
            clear()
            print("Calibrated!")
            await client.write_gatt_char(CALIBRATION_UUID, bytearray(int(0).to_bytes(1, byteorder='little')))
            await asyncio.sleep(3)
        else:
            mainMenuOn = True
            calibrateMode = False

async def writeDuration(client):
    global mainMenuOn, writeDurationMode, startTime, next_active_time
    if client.is_connected and writeDurationMode:
        print("Enter q to go back to main menu")
        hour_duration = await aioconsole.ainput("Please input the hour duration: ")
        if hour_duration.lower() == "q":
            writeDurationMode = False
            mainMenuOn = True
            clear()
            return
        while not hour_duration.isdigit() or int(hour_duration) < 0:
            clear()
            print("Enter q to go back to main menu")
            print("Please enter a valid number")
            hour_duration = await aioconsole.ainput("Please input the hour duration: ")
            if hour_duration.lower() == "q":
                writeDurationMode = False
                mainMenuOn = True
                clear()
                return
        minute_duration = await aioconsole.ainput("Please input the minute duration: ")
        if minute_duration.lower() == "q":
            writeDurationMode = False
            mainMenuOn = True
            clear()
            return
        while not minute_duration.isdigit() or int(minute_duration) < 0 or int(minute_duration) > 59:
            clear()
            print("Enter q to go back to main menu")
            print("Please enter a valid number")
            print(f"Please input the hour duration: {hour_duration}")
            minute_duration = await aioconsole.ainput("Please input the minute duration: ")
            if minute_duration.lower() == "q":
                writeDurationMode = False
                mainMenuOn = True
                clear()
                return
        await client.write_gatt_char(DURATION_HOUR_UUID, bytearray(int(hour_duration).to_bytes(4, byteorder='little')))
        await client.write_gatt_char(DURATION_MINUTE_UUID, bytearray(int(minute_duration).to_bytes(8, byteorder='little')))
        print("\nDuration set!")
        await asyncio.sleep(1)
        writeDurationMode = False
        mainMenuOn = True
        clear()
        if countdownActive != 0:
            hours = int.from_bytes(await client.read_gatt_char(DURATION_HOUR_UUID), byteorder='little')
            minutes = int.from_bytes(await client.read_gatt_char(DURATION_MINUTE_UUID), byteorder='little')
            next_active_time = startTime + datetime.timedelta(hours=hours, minutes=minutes)

async def mainMenu(client):
    global writeMotorUL, readMotor, mainMenuOn, calibrateMode, writeMotorSPS, writeDurationMode
    if client.is_connected and mainMenuOn:
        print("Main Menu")
        print("---------")
        print("  1. Calibrate")
        print("  2. Check Motor Speed")
        print("  3. Write Motor Speed (uL/min)")
        print("  4. Write Motor Speed (steps/second)")
        print("  5. Write Motor Run Duration\n")
        user_response = await aioconsole.ainput("Choose an option: ")
        if user_response == "1":
            calibrateMode = True
            mainMenuOn = False
        if user_response == "2":
            readMotor = True
            mainMenuOn = False
        if user_response == "3":
            writeMotorUL = True
            mainMenuOn = False
        if user_response == "4":
            writeMotorSPS = True
            mainMenuOn = False
        if user_response == "5":
            writeDurationMode = True
            mainMenuOn = False
        clear()


if __name__ == "__main__":
    asyncio.run(connect_and_read())