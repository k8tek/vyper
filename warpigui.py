#!/usr/bin/python3
# encoding=utf-8

# Menu for the wigle/replacement device
# https://www.designer2k2.at 2021-2022
#
# This is working on a rpi4 with kali 64bit os
#
# Libs:
# gpsd https://github.com/MartijnBraam/gpsd-py3
#
#
# kismet conf must be correct!
# gpsd will be called, check that it works with UART
#
# it expects a USB drive on /media/usb/ with the folder kismet there.
# Logs will be written to /media/usb/
#
# Warning:
# there are only some failsafes, it will stop working on error!

# The username and password must match with kismet_site.conf
httpd_username = "root"
httpd_password = "toor"

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M",
    filename="/media/usb/warpi.log",
)

logging.info("Startup")

# Sync HW Clock::
import subprocess

subprocess.run(["hwclock", "-s"])

logging.debug("HW Clock synced")

import board
import busio
from digitalio import DigitalInOut, Direction, Pull
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
from time import sleep, localtime, strftime
import gpsd
import psutil
import os
import signal
import RPi.GPIO as GPIO
import json
import requests
import socket
from ina219 import INA219, DeviceRangeError

logging.debug("All imports done")

# Turn some logger to only show warnings:
logging.getLogger("gpsd").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Create the I2C interface.
i2c = busio.I2C(board.SCL, board.SDA)

# Create the SSD1306 OLED class.
disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

# flip screen that the usb ports from the rpi are on top
disp.rotation = 2

# Input Pin:
GPIO.setmode(GPIO.BCM)

logging.debug("IO Setup")

# Page:
Page = 1


def InterruptLeft(_):
    global Page
    # Loop over Pager 1,2,3,4,5
    if Page > 4:
        Page = 1
    else:
        Page = Page + 1
    print(f"Page to be shown: {Page}")


def InterruptB(_):
    fshutdown()


def InterruptA(_):
    freboot()


def InterruptUp(_):
    startservice()


def InterruptDown(_):
    stopservice()


# 5 button A reboot
GPIO.setup(5, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(5, GPIO.RISING, callback=InterruptA, bouncetime=300)

# 6 button B shutdown
GPIO.setup(6, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(6, GPIO.RISING, callback=InterruptB, bouncetime=300)

# Up dir button start
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(22, GPIO.RISING, callback=InterruptUp, bouncetime=300)

# Down dir button stop
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(17, GPIO.RISING, callback=InterruptDown, bouncetime=300)

# Left dir button (switch display info)
GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(23, GPIO.RISING, callback=InterruptLeft, bouncetime=300)

logging.debug("GPIO Setup done")

# Clear display.
disp.fill(0)
disp.show()

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new("1", (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0, 0, width, height), outline=0, fill=0)

# Load a font
font = ImageFont.truetype("/home/kali/Minecraftia.ttf", 8)
fontbig = ImageFont.truetype("/home/kali/arial.ttf", 24)

logging.debug("Display setup done")

# set country code
# call("iw reg set AT", shell=True)

gpsrun = False
life = True
sleeptime = 1

# globals for the log:
kisuselog = open("/media/usb/kisuselog.log", "w")  # new every time
kiserrlog = open("/media/usb/kiserrlog.log", "a+")  # append
kissubproc = 0

# this delay will be waited, then it starts automatically
autostart = 10
autostarted = False

# Define INA219 calibration values
SHUNT_OHMS = 0.01
MAX_EXPECTED_AMPS = 8.0
ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, busnum=1)
ina.configure(ina.RANGE_16V)

def startservice():
    logging.info("Starting GPSD / Kismet")
    subprocess.Popen(["gpsd", "/dev/serial0", "-s", "9600"])
    global kisuselog, kiserrlog, gpsrun, kissubproc
    kissubproc = subprocess.Popen(["kismet"], stdout=kisuselog, stderr=kiserrlog)
    gpsrun = True

def stopservice():
    logging.info("Stopping GPSD / Kismet")
    global gpsrun, kissubproc
    gpsrun = False
    # Send a polite INT (CTRL+C)
    kissubproc.send_signal(signal.SIGINT)
    try:
        kissubproc.wait(10)  # wait max 10sec to close
    except subprocess.TimeoutExpired:
        logging.debug("timeout during kill kismet happened")
    try:
        subprocess.run(
            ["killall", "gpsd", "--verbose", "--wait", "--signal", "QUIT"], timeout=5
        )
    except subprocess.TimeoutExpired:
        logging.debug("timeout during kill gpsd happened")

def freboot():
    logging.info("Rebooting")
    global looping
    looping = False
    disp.fill(0)
    disp.show()
    subprocess.Popen(["reboot"])
    quit()

def fshutdown():
    global looping, kisuselog, kiserrlog
    looping = False
    logging.info("Shutdown")
    stopservice()
    kisuselog.close()
    kiserrlog.close()
    logging.debug("Kismet shutdown")
    draw.rectangle((0, 0, width, height), outline=0, fill=0)
    draw.text((0, 20), "Shutdown", font=fontbig, fill=255)
    disp.image(image)
    disp.show()
    logging.debug("LCD Black")
    subprocess.call("sudo shutdown -h now", shell=True)
    logging.debug("shutdown -h triggered")
    quit()

def display_page1():
    draw.text(
        (0, 0),
        f"CPU: {cpu / 100:>4.0%}  M: {mem / 100:>4.0%} T: {ct:5.1f}",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 54), strftime("%Y-%m-%d   %H:%M:%S", localtime()), font=font, fill=255
    )

    if gpsrun:
        try:
            gpsd.connect()
            packet = gpsd.get_current()
            draw.text(
                (0, 10),
                f"GPS: {packet.mode}  SAT: {packet.sats:>3}  Use: {packet.sats_valid:>3}",
                font=font,
                fill=255,
            )
            if packet.mode == 0:
                draw.rectangle((115, 20, width - 2, 10), outline=0, fill=0)
            if packet.mode == 1:
                draw.rectangle((120, 18, width - 4, 14), outline=255, fill=0)
            if packet.mode == 2:
                draw.rectangle((120, 18, width - 4, 14), outline=255, fill=1)
            if packet.mode == 3:
                draw.rectangle((115, 20, width - 2, 10), outline=255, fill=1)
            resp = requests.get(
                "http://127.0.0.1:2501/system/status.json",
                auth=(httpd_username, httpd_password),
            )
            data = resp.json()
            devices = data["kismet.system.devices.count"]
            kismetmemory = data["kismet.system.memory.rss"] / 1024
            draw.text((0, 20), f"D {devices:>7}", font=fontbig, fill=255)
            draw.text(
                (0, 44),
                f"Kismet mem: {kismetmemory:>4.0f}mb",
                font=font,
                fill=255,
            )
        except Exception as e:
            logging.error(f"An exception occurred {e}")

def display_page2():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(("10.254.254.254", 1))
        rpiIP = s.getsockname()[0]
    except Exception:
        rpiIP = "127.0.0.1"
    finally:
        s.close()
    draw.text(
        (0, 0),
        f"SSH IP: {rpiIP}",
        font=font,
        fill=255,
    )

def display_page3():
    draw.text(
        (0, 0),
        f"#5 button = reboot",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 10),
        f"#6 button = shutdown",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 20),
        f"up arrow = start",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 30),
        f"down arrow = stop",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 40),
        f"left arrow = screen",
        font=font,
        fill=255,
    )

def display_page4():
    voltage = ina.voltage()
    current = ina.current()
    power = ina.power()
    shunt_voltage = ina.shunt_voltage()
    load_voltage = voltage + (shunt_voltage / 1000)

    draw.text(
        (0, 0),
        f"Voltage: {voltage:.3f}V",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 10),
        f"Current: {current:.2f}A",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 20),
        f"Power: {power:.3f}W",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 30),
        f"Shunt Voltage: {shunt_voltage:.3f}V",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 40),
        f"Load Voltage: {load_voltage:.3f}V",
        font=font,
        fill=255,
    )

def display_page5():
    # Add your code here for displaying the INA219 sensor data
    Vout = round(ina.voltage(), 3)
    Iout = round(ina.current(), 2)
    Power = round(ina.power(), 3)
    Shunt_V = round(ina.shunt_voltage(), 3)
    Load_V  = round((Vout + (Shunt_V/1000)), 3)

    draw.text(
        (0, 0),
        f"Vout: {Vout}V",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 10),
        f"Iout: {Iout}A",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 20),
        f"Power: {Power}W",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 30),
        f"Shunt Voltage: {Shunt_V}V",
        font=font,
        fill=255,
    )
    draw.text(
        (0, 40),
        f"Load Voltage: {Load_V}V",
        font=font,
        fill=255,
    )


def display_page(page):
    draw.rectangle((0, 0, width, height), outline=0, fill=0)
    if page == 1:
        display_page1()
    elif page == 2:
        display_page2()
    elif page == 3:
        display_page3()
    elif page == 4:
        display_page4()
    elif page == 5:
        display_page5()
    disp.image(image)
    disp.show()


logging.debug("Start the loop")

while life:
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory().percent
        ct = psutil.sensors_temperatures()["cpu-thermal"][0][1]
        logging.debug(f"CPU: {cpu} M: {mem} T: {ct}")
        display_page(Page)
    except Exception as e:
        logging.error(f"An exception occurred {e}")

