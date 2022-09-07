import configparser

# writes out default config file in format that can be read by main program
# change site_id and api_key to values for your system
# suggest to copy file and rename "MySolarData.config"

config = configparser.ConfigParser(allow_no_value=True)
config['SolarEdge'] = {'; Use your site_id and api_key for your system':None, 'api_key': 'abcde', 'site_id':'123'}
config['PVSettings'] = {'; Determine scales to use for how much your system will produce. maxPower is the most watts your system will procude at a time. maxEnergy is the max watt hours your system produces or that you use in a day.':None, 'maxPower':'7600', 'maxEnergy':'38000'}
config['DisplaySettings']={'; Refresh is in seconds':None, 'refreshRate':'120', 'powerCols':'6', 'energyCols':'3', 'dimBat':'.3','rotation':'90','brightness':'.6'}
config['Colors']={'; Color values are [red][green][blue], all 0-255.':None, 'PVpower':'[0,255,0]','LoadPower':'[255,0,0]','ProdEnergy':'[0,250,125]','ConsumeEnergy':'[200,0,175]','BatteryLevel':'[0,0,255]'}

with open ('JoeSolarPi.config','w') as configfile:
    config.write(configfile)
