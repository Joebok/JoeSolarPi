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
    debug_log("getYesterdayData", False)
    plotGetData()
    status = "ok"
    try:
        global yesterday
        yesterday = date.today() + timedelta(days = -1)

        startTime = urllib.parse.quote_plus( yesterday.strftime("%Y-%m-%d")+" 00:00:00")
        endTime = urllib.parse.quote_plus( yesterday.strftime("%Y-%m-%d")+" 23:59:59")

        dailyEnergyURL = 'https://monitoringapi.solaredge.com/%20site/'+ site_id + '/energyDetails?api_key=' +api_key+'&timeUnit=DAY&startTime='+startTime+'&endTime='+endTime
        debug_log(dailyEnergyURL, False)
        day_data = requests.get(dailyEnergyURL, verify=False, timeout = responseTimeout).json()

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
        debug_log(e, True)
        status = "err"

    debug_log("Yesterday Production: {} KWh".format(yesterdayProduction), True)
    debug_log("Yesterday Consumption: {} KWh".format(yesterdayConsump), True)
    debug_log(status, True)

# get current production and consumption
def getSolarData():
    debug_log("getSolarData", False)
    plotGetData()

    gridState = ("unknown")
    batteryState = ""
    batteryFlow = 1

    try:
        startTime = urllib.parse.quote_plus( date.today().strftime("%Y-%m-%d")+" 00:00:00")
        endTime = urllib.parse.quote_plus( date.today().strftime("%Y-%m-%d")+" 23:59:59")

        dailyEnergyURL = 'https://monitoringapi.solaredge.com/%20site/'+ site_id + '/energyDetails?api_key=' +api_key+'&timeUnit=DAY&startTime='+startTime+'&endTime='+endTime
        debug_log(dailyEnergyURL, False)
        energy_data = requests.get(dailyEnergyURL, verify=False, timeout = responseTimeout).json()

        debug_log(energy_data, False)

        dayConsumption = 0
        dayProduction = 0
        dayUnit = energy_data["energyDetails"]["unit"]
        debug_log("reading meters...", False)
        for meter in energy_data["energyDetails"]["meters"]:
            debug_log(meter, False)
            if meter["type"] == "Consumption":
                try:
                    dayConsumption = meter["values"][0]["value"]
                except:
                    dayConsumption = 0
            if meter["type"] == "Production":
                try:
                    dayProduction = meter["values"][0]["value"]
                except:
                    dayProduction = 0

        currentPowerURL = 'https://monitoringapi.solaredge.com/%20site/'+ site_id + '/currentPowerFlow?api_key=' +api_key
        debug_log(currentPowerURL, False)
        power_data = requests.get(currentPowerURL, verify=False, timeout = responseTimeout).json()
        debug_log(power_data, False)

        #get units
        unit = power_data["siteCurrentPowerFlow"]["unit"]

        #determine meter states
        debug_log("reading connections...", False)
        for conn in power_data["siteCurrentPowerFlow"]["connections"]:
            debug_log(conn, False)
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
            debug_log("gridPower read fail", True)

        try:
            loadPower = power_data["siteCurrentPowerFlow"]["LOAD"]["currentPower"]
        except:
            loadPower = 0
            debug_log("loadPower read fail", True)

        try:    
            pvPower = power_data["siteCurrentPowerFlow"]["PV"]["currentPower"]
        except:
            pvPower = 0
            debug_log("pvPower read fail", True)

        try:
            batteryPower = power_data["siteCurrentPowerFlow"]["STORAGE"]["currentPower"]
        except:
            batteryPower = 0
            debug_log("batteryPower read fail", True)

        try:
            batteryLevel = power_data["siteCurrentPowerFlow"]["STORAGE"]["chargeLevel"]
        except:
            batteryLevel = 0
            debug_log("batteryLevel read fail", True)

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
        debug_log(e, True)

    debug_log("getSolarData", False)
    debug_log("Load: {} {}".format(loadPower, unit), True)
    debug_log("Grid Power: {} {} {}".format(gridPower,unit, gridState), True)
    debug_log("PV Power: {} {}".format(pvPower, unit), True)
    debug_log("Battery Power: {} {}".format(batteryFlow * batteryPower, unit), True)
    debug_log("Battery Level: {}% {}".format(batteryLevel,batteryState), True)
    debug_log("Consumption Today: {} {}".format(dayConsumption, dayUnit), True)
    debug_log("Production Today: {} {}".format(dayProduction, dayUnit), True)
    
    if "(charging)" in batteryState:
        totalLoad = loadPower + batteryPower
    else:
        totalLoad = loadPower 

    plotPower(totalLoad, pvPower, unit)
    plotEnergy(dayConsumption, dayProduction, dayUnit)
    plotBattery(batteryState, batteryPower, batteryLevel)

# plot current power production and consumption values
def plotPower(load, pv, unit):
    debug_log("plotPower", False)
    global maxPower
    try:
        if unit == "w":
            load = load / 1000
            pv = pv / 1000

        for i in range(powerCols-1):    
            powerList[i] = copy.deepcopy(powerList[i+1])
        
        cols=range(powerCols)
        rows = range(u_height)
        loadY = load / maxPower * u_height
        pvY = pv / maxPower * u_height

        #update maxPower
        if pv > maxPower:
            update_config("maxPower",str(pv * 1000))
            maxPower = pv
        if load > maxPower:
            update_config("maxPower",str(load * 1000))
            maxPower = load

        for y in rows:
            clr = [0,0,0]
            clr = AddColors(clr, clrPV, pvY-y)
            clr = AddColors(clr, clrLoad, loadY-y)
            
            powerList[powerCols-1][y] = copy.deepcopy(clr)
            
            for x in cols:
                unicornhathd.set_pixel(x, y, powerList[x][y][0], powerList[x][y][1], powerList[x][y][2])
        
        unicornhathd.show()
    except Exception as e:
        logger.error(e)
        debug_log(e, True)

# plot accumulated daily production and consumption totals
def plotEnergy(consumption, production, unit):
    debug_log("plotEnergy", False)
    global maxEnergy
    try:
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

        #update maxEnergy
        if consumption > maxEnergy:
            update_config("maxEnergy",str(consumption * 1000))
            maxEnergy = consumption

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
            if yesterdayConsump > 0:
                if y==yesterdayProdY:
                    unicornhathd.set_pixel(col_offset + 1, y, clrProd[0], clrProd[1], clrProd[2])
                if y==yesterdayConsumpY:
                    unicornhathd.set_pixel(col_offset + energyCols + 1, y, clrConsump[0], clrConsump[1], clrConsump[2])

        unicornhathd.show()
    except Exception as e:
        logger.error(e)
        debug_log(e, True)

# plot battery level and charge state
def plotBattery(batteryState, power, level):
    debug_log("plotBattery", False)
    try:
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
    except Exception as e:
        logger.error(e)
        debug_log(e, True)

# signal data retrieval
def plotGetData():
    debug_log("plotGetData", False)
    try:
        y = u_height-1
        for x in range(u_width):
            unicornhathd.set_pixel(x,y, 50,50,50)
            unicornhathd.show()
            time.sleep(.05)
        for x in range(u_width):
            unicornhathd.set_pixel(x,y, 0,0,0)
    except Exception as e:
        logger.error(e)
        debug_log(e, True)

# combine rgb values of two colors with frac % of second color used.
def AddColors(c1, c2, frac):
    frac = max(0,min(1,frac))
    c = [min(255, round(c1[0] + frac * c2[0])), \
         min(255, round(c1[1] + frac * c2[1])), \
         min(255, round(c1[2] + frac * c2[2]))]
    return c

# read config file - looks for "MySolarData.config" first, "SolarData.config" second
def ReadConfig():
    global configFilename
    try:
        configFilename = "MyJoeSolarPi.config"
        if not os.path.exists(configFilename):
            configFilename = "JoeSolarPi.config"
        if os.path.exists(configFilename):
            print("Reading config from {}...".format(configFilename))
            config = configparser.ConfigParser()
            config.read(configFilename)
            global api_key
            api_key = config["SolarEdge"]["api_key"]
            global site_id
            site_id = config["SolarEdge"]["site_id"]
            global responseTimeout
            responseTimeout = config["SolarEdge"].getint("responseTimeout")
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
            maxPower = config["PVSettings"].getfloat("maxPower") / 1000
            global maxEnergy
            maxEnergy = config["PVSettings"].getfloat("maxEnergy") / 1000
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
            print("MaxPower: {}, MaxEnergy: {}".format(maxPower, maxEnergy))

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

def debug_log(str, screen):
    if screen:
        print(str)
    if writedebug:
        debugfile.writelines("{}\n".format(str))
        debugfile.flush()

def update_config(key,value):
    # Read config.ini file
    edit = configparser.ConfigParser()
    edit.read(configFilename)
    #Get the pvsettings section
    pvSettings = edit["PVSettings"]
    #Update the value
    pvSettings[key] = value
    #Write changes back to file
    with open(configFilename, 'w') as configfile:
        edit.write(configfile)

# *************************************** #
#          begin main process
# *************************************** #
global logger
logging.basicConfig(filename='JoeSolarPi_err.log', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

ReadConfig()

powerList = [ [ [0,0,0] for y in range(u_height) ] for x in range(powerCols) ]
yesterday = date.today()
yesterdayProduction = 0
yesterdayConsump = 0

global writedebug 
writedebug = True
global debugfile

debugfile = open('debug.txt','w')

try:
    while True:
        if writedebug:
            if debugfile.closed == True:
                debugfile = open('debug.txt','w')
            debug_log("debug {}".format(datetime.now()), True)

        if (date.today() + timedelta(days = -1) != yesterday) or yesterdayConsump <= 0:
            getYesterdayData()

        getSolarData()
        debugfile.close()
        time.sleep(refreshRate)

except KeyboardInterrupt:
    unicornhathd.off()
