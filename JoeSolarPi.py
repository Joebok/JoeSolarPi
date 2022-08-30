import requests
import json
from datetime import date
from datetime import datetime
from datetime import timedelta
import urllib.parse
import time
import copy
import configparser
import os.path
import logging

#use the unicornhathd simulator if not running on pi with UnicornHatHD installed
#
try:
    import unicornhathd 
    print("unicorn hat hd detected")
    sim = 0
except ImportError:
    from unicorn_hat_sim import unicornhathd
    print("using unicorn hat simulator")
    sim = 1

# get previous day's production and consumption
def getYesterdayData():
    plotGetData()
    status = "ok"
    try:
        global yesterday
        yesterday = date.today() + timedelta(days = -1)

        startTime = urllib.parse.quote_plus( yesterday.strftime("%Y-%m-%d")+" 00:00:00")
        endTime = urllib.parse.quote_plus( yesterday.strftime("%Y-%m-%d")+" 23:59:59")

        dailyEnergyURL = 'zhttps://monitoringapi.solaredge.com/%20site/'+ site_id + '/energyDetails?api_key=' +api_key+'&timeUnit=DAY&startTime='+startTime+'&endTime='+endTime
        day_data = requests.get(dailyEnergyURL, verify=False).json()

        global yesterdayConsump 
        global yesterdayProduction 

        dayUnit = day_data["energyDetails"]["unit"]

        for meter in day_data["energyDetails"]["meters"]:
            #print(meter)
            if meter["type"] == "Consumption":
                try:
                    yesterdayConsump = meter["values"][0]["value"]
                except:
                    yesterdayConsump = 0
            if meter["type"] == "Production":
                try:
                    yesterdayProduction = meter["values"][0]["value"]
                except:
                    yesterdayProduction = 0

        if dayUnit == "Wh":
            yesterdayConsump = yesterdayConsump / 1000
            yesterdayProduction = yesterdayProduction / 1000

    except Exception as e:
        logger.error(e)
        yesterdayConsump = 0
        yesterdayProduction = 0
        status = "err"

    print("Yesterday Production: {} KWh".format(yesterdayProduction))
    print("Yesterday Consumption: {} KWh".format(yesterdayConsump))
    if status != "ok":
        print(status)
        
# get current production and consumption
def getSolarData():
    plotGetData()

    try:
        startTime = urllib.parse.quote_plus( date.today().strftime("%Y-%m-%d")+" 00:00:00")
        endTime = urllib.parse.quote_plus( date.today().strftime("%Y-%m-%d")+" 23:59:59")

        dailyEnergyURL = 'https://monitoringapi.solaredge.com/%20site/'+ site_id + '/energyDetails?api_key=' +api_key+'&timeUnit=DAY&startTime='+startTime+'&endTime='+endTime
        print("reading energy values...")
        energy_data = requests.get(dailyEnergyURL, verify=False).json()

        dayConsumption = 0
        dayProduction = 0
        dayUnit = energy_data["energyDetails"]["unit"]
        for meter in energy_data["energyDetails"]["meters"]:
            #print(meter)
            if meter["type"] == "Consumption":
                dayConsumption = meter["values"][0]["value"]
            if meter["type"] == "Production":
                dayProduction = meter["values"][0]["value"]

        currentPowerURL = 'https://monitoringapi.solaredge.com/%20site/'+ site_id + '/currentPowerFlow?api_key=' +api_key
        power_data = requests.get(currentPowerURL, verify=False).json()

        #get units
        unit = power_data["siteCurrentPowerFlow"]["unit"]

        #determine if battery is charging or discharging
        batteryState = ""
        batteryFlow = 1
        for conn in power_data["siteCurrentPowerFlow"]["connections"]:
            #print(conn)
            if conn["from"].lower()=="storage":
                batteryState = "(discharging)"
                batteryFlow = -1
            if conn["to"].lower()=="storage":
                batteryState="(charging)"
                batteryFlow = 1
            if conn["to"].lower()=="grid":
                gridState="(selling)"
            if conn["from"].lower()=="grid":
                gridState="(buying)"

        try:
            gridPower = power_data["siteCurrentPowerFlow"]["GRID"]["currentPower"]
        except:
            gridPower = 0

        try:
            loadPower = power_data["siteCurrentPowerFlow"]["LOAD"]["currentPower"]
        except:
            loadPower = 0

        try:    
            pvPower = power_data["siteCurrentPowerFlow"]["PV"]["currentPower"]
        except:
            pvPower = 0

        try:
            batteryPower = power_data["siteCurrentPowerFlow"]["STORAGE"]["currentPower"]
        except:
            batteryPower = 0

        try:
            batteryLevel = power_data["siteCurrentPowerFlow"]["STORAGE"]["chargeLevel"]
        except:
            batteryLevel = 0

    except Exception as e:
        loadPower = 0
        gridPower = 0
        pvPower = 0
        batteryFlow = 0
        batteryLevel = 0
        batteryPower = 0
        batteryState = ""
        dayConsumption = 0
        dayProduction = 0
        unit = "err"
        dayUnit = "err"
        logger.error(e)

    print()
    print(datetime.now())
    print("Load: {} {}".format(loadPower, unit))
    print("Grid Power: {} {} {}".format(gridPower,unit, gridState))
    print("PV Power: {} {}".format(pvPower, unit))
    print("Battery Power: {} {}".format(batteryFlow * batteryPower, unit))
    print("Battery Level: {}% {}".format(batteryLevel,batteryState))
    print("Consumption Today: {} {}".format(dayConsumption, dayUnit))
    print("Production Today: {} {}".format(dayProduction, dayUnit))
    print()
    
    if "(charging)" in batteryState:
        totalLoad = loadPower + batteryPower
    else:
        totalLoad = loadPower 

    plotPower(totalLoad, pvPower, unit)
    plotEnergy(dayConsumption, dayProduction, dayUnit)
    plotBattery(batteryState, batteryPower, batteryLevel)

# plot current power production and consumption values
def plotPower(load, pv, unit):
    if unit == "w":
        load = load / 1000
        pv = pv / 1000

    for i in range(powerCols-1):    
        powerList[i] = copy.deepcopy(powerList[i+1])
    
    cols=range(powerCols)
    rows = range(u_height)
    loadY = load / maxPower * u_height
    pvY = pv / maxPower * u_height

    for y in rows:
        clr = [0,0,0]
        clr = AddColors(clr, clrPV, pvY-y)
        clr = AddColors(clr, clrLoad, loadY-y)
        
        powerList[powerCols-1][y] = copy.deepcopy(clr)
        
        for x in cols:
            unicornhathd.set_pixel(x, y, powerList[x][y][0], powerList[x][y][1], powerList[x][y][2])
       
    unicornhathd.show()

# plot accumulated daily production and consumption totals
def plotEnergy(consumption, production, unit):
    if unit == "Wh":
        consumption = consumption / 1000
        production = production / 1000
    
    cols=range( 2 * energyCols )
    col_offset = powerCols+1
    rows = range(u_height)
    consumpY = consumption / maxEnergy * u_height
    prodY = production / maxEnergy * u_height

    yesterdayConsumpY = round(yesterdayConsump / maxEnergy * u_height, 0)
    yesterdayProdY = round(yesterdayProduction / maxEnergy * u_height,0 )

    for y in rows:
        clrProd = AddColors([0,0,0], clrProdEnergy, prodY-y)    
        clrConsump = AddColors([0,0,0], clrConsumeEnergy, consumpY-y)
        for x in cols:
            if x < energyCols:
                unicornhathd.set_pixel(x+col_offset, y, clrProd[0], clrProd[1], clrProd[2])
            else:
                unicornhathd.set_pixel(x+col_offset, y, clrConsump[0], clrConsump[1], clrConsump[2])
        
        clrProd = AddColors([50,50,50], clrProdEnergy, .5)
        clrProd = AddColors([0,0,0],clrProd,.5)
        clrConsump = AddColors([110,110,110], clrConsumeEnergy, .5)
        clrConsump = AddColors([0,0,0],clrConsump,.5)
        if y==yesterdayProdY:
            unicornhathd.set_pixel(col_offset + 1, y, clrProd[0], clrProd[1], clrProd[2])
        if y==yesterdayConsumpY:
            unicornhathd.set_pixel(col_offset + energyCols + 1, y, clrConsump[0], clrConsump[1], clrConsump[2])

    unicornhathd.show()

# plot battery level and charge state
def plotBattery(batteryState, power, level):
    cols = range(2)
    col_offset = powerCols + 2 * energyCols + 2
    batRows = 10
    rows = range(batRows)
    
    clrDimBat = AddColors([0,0,0], clrBatteryLevel, dimBat)

    levelY = level / 100 * batRows * 2
    for y in rows:
        for x in cols:
            clr = AddColors(clrDimBat, clrBatteryLevel, levelY-(2 * y + x))
            unicornhathd.set_pixel(x+col_offset, y, clr[0], clr[1], clr[2])

        #indicator
        unicornhathd.set_pixel(col_offset, batRows, 0,0,0)
        unicornhathd.set_pixel(col_offset+1, batRows, 0,0,0)
        if "discharging" in batteryState:
            unicornhathd.set_pixel(col_offset, 0, 175,0,0)
            unicornhathd.set_pixel(col_offset+1, 0, 175,0,0)
        elif "charging" in batteryState:
            unicornhathd.set_pixel(col_offset, batRows, 0,175,0)
            unicornhathd.set_pixel(col_offset+1, batRows, 0,175,0)

    unicornhathd.show()

# signal data retrieval
def plotGetData():
    y = u_height-1
    for x in range(u_width):
        unicornhathd.set_pixel(x,y, 50,50,50)
        unicornhathd.show()
        time.sleep(.05)
    for x in range(u_width):
        unicornhathd.set_pixel(x,y, 0,0,0)

# combine rgb values of two colors with frac % of second color used.
def AddColors(c1, c2, frac):
    frac = max(0,min(1,frac))
    c = [min(255, round(c1[0] + frac * c2[0])), \
         min(255, round(c1[1] + frac * c2[1])), \
         min(255, round(c1[2] + frac * c2[2]))]
    return c

# read config file - looks for "MySolarData.config" first, "SolarData.config" second
def ReadConfig():
    try:
        filename = "MyJoeSolarPi.config"
        if not os.path.exists(filename):
            filename = "JoeSolarPi.config"
        if os.path.exists(filename):
            print("Reading config from {}...".format(filename))
            config = configparser.ConfigParser()
            config.read(filename)
            global api_key
            api_key = config["SolarEdge"]["api_key"]
            global site_id
            site_id = config["SolarEdge"]["site_id"]
            global refreshRate
            refreshRate = config["DisplaySettings"].getint("refreshRate")
            global powerCols
            powerCols = config["DisplaySettings"].getint("powerCols")
            global energyCols
            energyCols = config["DisplaySettings"].getint("energyCols")
            global dimBat
            dimBat = config["DisplaySettings"].getfloat("dimBat")
            global rotation
            rotation = config["DisplaySettings"].getint("rotation")
            global brightness
            brightness = config["DisplaySettings"].getfloat("brightness")
            global maxPower
            maxPower = config["PVSettings"].getint("maxPower")
            global maxEnergy
            maxEnergy = config["PVSettings"].getint("maxEnergy")
            global clrPV
            clrPV = json.loads(config.get("Colors","PVpower"))
            global clrLoad
            clrLoad = json.loads(config.get("Colors","LoadPower"))
            global clrProdEnergy
            clrProdEnergy = json.loads(config.get("Colors","ProdEnergy"))
            global clrConsumeEnergy
            clrConsumeEnergy = json.loads(config.get("Colors","ConsumeEnergy"))
            global clrBatteryLevel
            clrBatteryLevel = json.loads(config.get("Colors","BatteryLevel"))

        try:
            unicornhathd.rotation(rotation)
            if sim==1:
                unicornhathd.rotation(180)
            unicornhathd.brightness(brightness)
            global u_width
            global u_height
            u_width, u_height = unicornhathd.get_shape()
        except Exception as e:
            logger.error(e)

    except Exception as e:
        logger.error(e)

# *************************************** #
#          begin main process
# *************************************** #

logging.basicConfig(filename='JoeSolarPi_err.log', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

ReadConfig()

powerList = [ [ [0,0,0] for y in range(u_height) ] for x in range(powerCols) ]

yesterday = date.today()

try:
    while True:
        if (date.today() + timedelta(days = -1) != yesterday) or yesterdayConsump <= 0:
            getYesterdayData()

        getSolarData()
        time.sleep(refreshRate)

except KeyboardInterrupt:
    unicornhathd.off()
