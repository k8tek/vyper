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
import adafruit_ina219

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

# Define INA219 sensor with calibration values
ina = adafruit_ina219.INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, busnum=1, address=0x40)
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
