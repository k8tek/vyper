# Add this section at the beginning of the script to import the necessary libraries:
from ina219 import INA219, DeviceRangeError

# Add this section to initialize the INA219 sensor:
SHUNT_OHMS = 0.01
MAX_EXPECTED_AMPS = 8.0
ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, busnum=1)
ina.configure(ina.RANGE_16V)

# Inside the main loop, add this section to display the INA219 sensor values on Page 4:
if Page == 4:
    # Read sensor values
    Vout = round(ina.voltage(), 3)
    Iout = round(ina.current(), 2)
    Power = round(ina.power(), 3)
    Shunt_V = round(ina.shunt_voltage(), 3)
    Load_V = round((Vout + (Shunt_V / 1000)), 3)
    
    # Display sensor values on OLED
    draw.text((0, 0), f"Vout: {Vout}V", font=font, fill=255)
    draw.text((0, 10), f"Iout: {Iout}A", font=font, fill=255)
    draw.text((0, 20), f"Power: {Power}W", font=font, fill=255)
    draw.text((0, 30), f"Shunt Voltage: {Shunt_V}V", font=font, fill=255)
    draw.text((0, 40), f"Load Voltage: {Load_V}V", font=font, fill=255)
