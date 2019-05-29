from __future__ import print_function
import serial, struct, sys, json
from flask import Flask, Response, render_template,  flash, redirect, url_for, session, request, make_response, jsonify, current_app
import RPi.GPIO as GPIO
import time
import numpy as np
import random,os, csv
import smbus2
import bme280
from flask_cors import CORS, cross_origin

#### BME Sensor Utility Function






def bin2dec(string_num):
    return str( int( string_num, 2 ) )



def _deployFunction(limit, PIN, reverse=True):
    counter = 0
    try:
        # here you put your main loop or block of code

        if(reverse): GPIO.output(PIN, GPIO.LOW)
        else: GPIO.output(PIN, GPIO.HIGH)

        while counter < limit:

            counter += 1
        print ("Target reached: %d" % counter)

    except KeyboardInterrupt:
        # here you put any code you want to run before the program
        # exits when you press CTRL+C
        print("\n", counter)  # print value of counter
        GPIO.cleanup()
        return False

    except:

        # this catches ALL other exceptions including errors.
        # You won't get any error messages for debugging
        # so only use it once your code is working
        print("Other error or exception occurred!")
        GPIO.cleanup()
        return False

    finally:
        print("executed")
        GPIO.cleanup()  # this ensures a clean exit

    return True



## Dust Sensor Utility Function
DEBUG = 0
CMD_MODE = 2
CMD_QUERY_DATA = 4
CMD_DEVICE_ID = 5
CMD_SLEEP = 6
CMD_FIRMWARE = 7
CMD_WORKING_PERIOD = 8
MODE_ACTIVE = 0
MODE_QUERY = 1

ser = serial.Serial()
ser.port = "/dev/ttyUSB0"
ser.baudrate = 9600

ser.open()
ser.flushInput()

byte, data = 0, ""

def dump(d, prefix=''):
    print(prefix + ' '.join(x.encode('hex') for x in d))

def construct_command(cmd, data=[]):
    assert len(data) <= 12
    data += [0,]*(12-len(data))
    checksum = (sum(data)+cmd-2)%256
    ret = "\xaa\xb4" + chr(cmd)
    ret += ''.join(chr(x) for x in data)
    ret += "\xff\xff" + chr(checksum) + "\xab"

    if DEBUG:
        dump(ret, '> ')
    return ret

def process_data(d):
    r = struct.unpack('<HHxxBB', d[2:])
    pm25 = r[0]/10.0
    pm10 = r[1]/10.0
    checksum = sum(ord(v) for v in d[2:8])%256
    return [pm25, pm10]

def process_version(d):
    r = struct.unpack('<BBBHBB', d[3:])
    checksum = sum(ord(v) for v in d[2:8])%256
    print("Y: {}, M: {}, D: {}, ID: {}, CRC={}".format(r[0], r[1], r[2], hex(r[3]), "OK" if (checksum==r[4] and r[5]==0xab) else "NOK"))

def read_response():
    byte = 0
    while byte != "\xaa":
        byte = ser.read(size=1)

    d = ser.read(size=9)

    if DEBUG:
        dump(d, '< ')
    return byte + d

def cmd_set_mode(mode=MODE_QUERY):
    ser.write(construct_command(CMD_MODE, [0x1, mode]))
    read_response()

def cmd_query_data():
    ser.write(construct_command(CMD_QUERY_DATA))
    d = read_response()
    values = []
    if d[1] == "\xc0":
        values = process_data(d)
    return values

def cmd_set_sleep(sleep=1):
    mode = 0 if sleep else 1
    ser.write(construct_command(CMD_SLEEP, [0x1, mode]))
    read_response()

def cmd_set_working_period(period):
    ser.write(construct_command(CMD_WORKING_PERIOD, [0x1, period]))
    read_response()

def cmd_firmware_ver():
    ser.write(construct_command(CMD_FIRMWARE))
    d = read_response()
    process_version(d)

def cmd_set_id(id):
    id_h = (id>>8) % 256
    id_l = id % 256
    ser.write(construct_command(CMD_DEVICE_ID, [0]*10+[id_l, id_h]))
    read_response()


############################################

app = Flask(__name__)
CORS(app, headers=['Content-Type'])
FAN_PIN = 17


@app.route('/')
def index():
    return "Hello World!"


@app.route('/read-dust', methods=["GET"])
@cross_origin(origin='*')
def readDust():
    cmd_set_sleep(0)
    cmd_set_mode(1)
    values = cmd_query_data()
    response = [
        {
         "PM25": values[0],
         "PM10": values[1]
         }
    ]

    return jsonify(response)


@app.route('/read-sensor', methods=["GET"])
@cross_origin(origin='*')
def readSensor():
    port = 1
    address = 0x77
    bus = smbus2.SMBus(port)
    task = request.args.get("task");
    calibration_params = bme280.load_calibration_params(bus, address)

    # the sample method will take a single reading and return a
    # compensated_reading object
    data = bme280.sample(bus, address, calibration_params)

    # the compensated_reading class has the following attributes
    print(data.id)
    print(data.timestamp)
    print(data.temperature)
    print(data.pressure)
    print(data.humidity)


    response = [
        {"timestamp":data.timestamp,
          "temperature":data.temperature,
          "humidity":data.humidity,
          "pressure":data.pressure,
        }
    ]


    # response.append({"timestamp": data.timestamp})
    # if(task == "getTemperature"):
    #     response.append({"sensor_val":data.temperature})
    #     return jsonify(response)
    # elif(task == "getPressure"):
    #     response.append({"sensor_val": data.pressure})
    #     return jsonify(response)
    # else:
    #     response.append({"sensor_val": data.humidity})
    return jsonify(response)





    # there is a handy string representation too




@app.route('/control-fan', methods=["GET"])
@cross_origin(origin='*')
def controlFan():

    clk_pin = 21
    anticlk_pin = 16
    task = request.args.get('task')
    print(task)


    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    #GPIO.setup(clk_pin, GPIO.OUT)
    GPIO.setup(anticlk_pin, GPIO.OUT)

    if(_deployFunction(4000000, anticlk_pin) == True):
        return jsonify({'success': 'true'})
    return jsonify({'success': 'false'})







@app.route('/control-led', methods=["GET"])
@cross_origin(origin='*')
def controlLED():

    GPIO.setmode(GPIO.BCM)
    PIN = 16

    GPIO.setup(PIN, GPIO.OUT)

    if (_deployFunction(4000000, PIN, False) == True):
        return jsonify({'success': 'true'})
    return jsonify({'success': 'false'})




if(__name__ == '__main__'):
    app.run(host='0.0.0.0', debug=True)