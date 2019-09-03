# Helper functions
from datetime import datetime, timedelta
from darksky import forecast
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity
import numpy as np
from azure.storage.file import FileService
from azure.storage.file import ContentSettings
    
# Stores predictions from ML in Azure table
def store_predictions_in_table(predictions, times, table_name="predictedSoilMoistureMessages"):
    
    # Connect to account
    table_service = TableService(account_name='soilhumiditydata293s', account_key='4PSsEO1xBAIdq3/MppWm+t6eYHi+CWhVn6xNZ6i4mLVgm50K8+NK6lA94v8MxG0bvVEfYCvsv1suxCyCnUYd0A==')
    
    # Delete existing table predictions
    table = table_service.query_entities(table_name)
    for entry in table:
        table_service.delete_entity(table_name, entry['PartitionKey'], entry['RowKey']) #'tasksSeattle', '001')

    # Store values in table
    for i in range(len(predictions)):
        new_entity = Entity()
        new_entity.PartitionKey = datetime.strftime(times[i], "%Y-%m-%d %H:%M:%S")
        new_entity.RowKey = str(i)
        new_entity['soilmoistureprediction'] = str(predictions[i])
        
        table_service.insert_entity(table_name, new_entity)


# Return weather forecast for current + next 48 hours = 49 hours of data
def get_weather_forecast():
    apikey = '7358efac8f40bf49ceaa4a8c5278bd31'
    Goleta = [34.4099508, -119.8661304]
    
    goleta = forecast(apikey, Goleta[0], Goleta[1])
    
    parameters = ['time', 'ozone', 'windGust', 'temperature', 'dewPoint', 'humidity', 'apparentTemperature', 'pressure', 'windSpeed', 'precipProbability', 'visibility', 'cloudCover', 'precipIntensity']
    
    forecast_data = []
    
    for hour in goleta['hourly']['data']:
        hourly_data = {}
        
        for item in hour:
            if item in parameters:
                hourly_data[item] = hour[item]
                if item == 'temperature' or item == 'apparentTemperature' or item == 'dewPoint':
                    hourly_data[item] = convert_to_celsius(hourly_data[item])
        
        time = datetime.fromtimestamp(int(hour['time'])).strftime('%Y-%m-%d %H:%M:%S')
        time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
        time = time + timedelta(hours=8, minutes=0)
        hourly_data['time'] = time
        hourly_data['hour'] = time.hour
        
        forecast_data.append(hourly_data)
        
    return forecast_data


def convert_to_voltage(moisture):
    return ((moisture / 1023.0) * 4.3)
    
    
def find_closest_15th_minute(sample_time):

    ignore_seconds = datetime(sample_time.year, sample_time.month, sample_time.day, sample_time.hour, sample_time.minute)
    
    minute = sample_time.minute
    minutedelta = 0
    
    if minute >= 53:
        minutedelta = 60 - minute
    elif minute <= 7:
        minutedelta = 0 - minute
    elif minute >= 8 and minute <= 22:
        minutedelta = 15 - minute
    elif minute >= 23 and minute <= 37:
        minutedelta = 30 - minute
    else:
        minutedelta = 45 - minute
        
    return ignore_seconds + timedelta(minutes = minutedelta)
    

def store_trained_model_in_azure(model):
    file_service = FileService(account_name='soilhumiditydata293s', account_key='4PSsEO1xBAIdq3/MppWm+t6eYHi+CWhVn6xNZ6i4mLVgm50K8+NK6lA94v8MxG0bvVEfYCvsv1suxCyCnUYd0A==')
    
    file_service.delete_file('model', None, 'model')
    
    file_service.create_file_from_path('model', None, 'model', '/fs/student/aditya_wadaskar/iot/ML_training/model')
    
    
def running_mean(x, N=12):
    # print x
    r = []
    for i in range(N/2):
        r.append(x[0])
    r.extend(x)
    for i in range(N/2):
        r.append(x[len(x)-1])
    cumsum = np.cumsum(r)
    return (cumsum[N:] - cumsum[:-N]) / float(N)
    
    
def convert_to_celsius (Fahrenheit):
    return ((Fahrenheit - 32) * 5.0/9.0)
    
