from utils import *
from datetime import datetime, timedelta
import matplotlib.dates as mdates
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity
import matplotlib.pyplot as plt
import numpy as np
import pickle
from time import sleep

all_features = ["apparentTemperature", "temperatureLocal", "messageIdLocal", "dewPoint", "Timestamp", "humidityLocal", "RowKey", "cloudCover", "humidity", "ozone", "pressure", "windSpeed", "PartitionKey", "visibility", "moistureLocal", "windGust", "etag", "precipIntensity", "temperature", "enqueuedTime", "precipProbability"]
numerical_features = ["hour", "apparentTemperature", "temperatureLocal", "dewPoint", "humidityLocal", "cloudCover", "humidity", "ozone", "pressure", "windSpeed", "visibility", "moistureLocal", "windGust", "precipIntensity", "temperature", "precipProbability"]
local_features = ["moistureLocal", "temperatureLocal", "humidityLocal"]
excluded_features = ["PartitionKey", "RowKey", "enqueuedTime", "Timestamp", "etag", "messageIdLocal"]

# Load data
def load_data(file, load=False):
    data = None
    
    if load: # Load saved data (for faster testing)
        pickleFile = open(file, 'rb')
        data = pickle.load(pickleFile)
        pickleFile.close()
    else: # Collect data from Azure table (and save local copy)
        data = combine_data()
        pickleFile = open(file, 'wb')
        pickle.dump(data, pickleFile)
        pickleFile.close()
    
    data = preprocess_data(data)#, 2)
        
    return data


# Combine past and present data
def combine_data():
    # Collect data from both tables
    pastdata = get_data_from_table("trainingDataPastSoilMoistureMessagesV2")
    
    # Convert past data readings to celsius
    for d in pastdata:
        d['temperature'] = convert_to_celsius(d['temperature'])
        d['apparentTemperature'] = convert_to_celsius(d['apparentTemperature'])
        d['dewPoint'] = convert_to_celsius(d['dewPoint'])
    
    data = pastdata
    # data = []
    # for i in range(len(pastdata)):
        # if pastdata[i]['enqueuedTime'] > datetime(2019, 2, 23):
            # data.append(pastdata[i])
    
    recent_data = get_data_from_table("parsedsoilmoisturemessages")
    data.extend(recent_data)
    
    # Sort by enqueuedTime
    data = sorted(data, key=lambda k: k['enqueuedTime'])
    
    # Add missing data points, correct moisture readings, make 15-min timestamps
    data = add_missing_values(data)
    data = correct_moisture_readings(data)
    
    return data
    
    
# Extract tabular data
def get_data_from_table(table_name):

    # Connect to account
    table_service = TableService(account_name='soilhumiditydata293s', account_key='4PSsEO1xBAIdq3/MppWm+t6eYHi+CWhVn6xNZ6i4mLVgm50K8+NK6lA94v8MxG0bvVEfYCvsv1suxCyCnUYd0A==')
    
    # Check if table exists
    if not table_service.exists(table_name):
        print ("Table does NOT exist.")
        return -1
    
    # Retrieve all values from table
    table = table_service.query_entities(table_name)
    
    data = []
    for entry in table:
        # Format timestamp
        eTime = entry['enqueuedTime']
        eTime = datetime.strptime(str(eTime[:10]) + " " + str(eTime[11:-8]), '%Y-%m-%d %H:%M:%S')
        entry['enqueuedTime'] = find_closest_15th_minute(eTime) # Round to closest 15th minute
        entry['hour'] = float(entry['enqueuedTime'].hour)
        
        data.append(entry)
        
    # Sort by time of reading
    data = sorted(data, key=lambda k: k['enqueuedTime'])
    
    return data
    
    
# For Feb 26 7 AM - Feb 27 2:20 AM
def add_missing_values(data):

    data_to_copy = []
    m = 0

    for i in range(len(data)):
        point = {}
        
        # Save values to copy
        if data[i]['enqueuedTime'] > datetime(2019, 2, 25, 6, 30, 0) and data[i]['enqueuedTime'] <= datetime(2019, 2, 26, 2, 30, 0):
        
            for f in data[i]:
                if f not in excluded_features:
                    point[f] = float(data[i][f])
        
            point['enqueuedTime'] = data[i]['enqueuedTime'] + timedelta(days=1)
            point['moistureLocal'] -= 30.0
            point['temperatureLocal'] -= 1.0
            point['humidityLocal'] += 4.0
            data_to_copy.append(point)
        
        # Change local values for Feb 26 to Feb 27
        if data[i]['moistureLocal'] == -1 or data[i]['temperatureLocal'] == -1 or data[i]['humidityLocal'] == -1:
            data[i]['moistureLocal'] = float(data_to_copy[m]['moistureLocal'])
            data[i]['temperatureLocal'] = float(data_to_copy[m]['temperatureLocal'])
            data[i]['humidityLocal'] = float(data_to_copy[m]['humidityLocal'])
            m += 1
                
    return data


# Correcting readings for when we moved soil sensor and there was a loose connection
def correct_moisture_readings(data):
    start = datetime(2019, 3, 1, 21, 45, 0)
    end = datetime(2019, 3, 2, 5, 10, 0)
    count = startindex = 0
    
    for d in range(len(data)):
        if data[d]['enqueuedTime'] > start and data[d]['enqueuedTime'] < end:
            if startindex == 0:
                startindex = d
            count += 1
            
    noise = np.random.normal(0, 1, count) # Add noise to make it slightly nonlinear
    
    for d in range(startindex, startindex+count):
        data[d]['moistureLocal'] = 341 + (6.0 / count)*(d - startindex - 341) + noise[d-startindex]
        
    return data


# Make time between each successive point in dataset 15 minutes
# Also smoothen data through averaging
def preprocess_data(data, moving_average = 30):

    processed_data = []
    
    run_mean_vectors = {}
    
    # select_data = []
    # start_date = datetime(2019, 2, 20)
    # end_date = datetime(2019, 3, 1)
    # for i in range(len(data)):
        # if data[i]['enqueuedTime'] > start_date and data[i]['enqueuedTime'] < end_date:
            # select_data.append(data[i])
    # data = select_data

    # Find average of points - spread over 15 minutes (4 / hour)
    i = 0
    while i < len(data):
        point = {}
        
        point_time = data[i]['enqueuedTime']
        
        count = 0
        while i < len(data) and data[i]['enqueuedTime'] == point_time:
            for f in data[i]:
                if f not in excluded_features:
                    if f not in point and f != 'hour':
                        point[f] = float(data[i][f])
                    elif f != 'hour':
                        point[f] += float(data[i][f])
            i += 1
            count += 1
        
        # Find average of sums
        for f in point:
            point[f] /= float(count)

        for f in point:
            if f not in run_mean_vectors:
                run_mean_vectors[f] = []
            run_mean_vectors[f].append(point[f])
            
        point['enqueuedTime'] = point_time
        point['hour'] = point_time.hour
        
        processed_data.append(point)
        
        
    for f in run_mean_vectors:
        rm = running_mean(run_mean_vectors[f], moving_average)
        for i in range(len(processed_data)):
            processed_data[i][f] = rm[i]
    
    return processed_data


# Format vector
def create_x_vector_u(last_data_point, forecast):
    X = []
    times = []
    
    # Add current timestamp's values to X vector
    for f in numerical_features:
        X.append(float(last_data_point[f]))
    times.append(forecast[0]['time'])
    
    # Add forecast values to X vector
    for hour in range(1, 25):
        for f in numerical_features:
            if f not in local_features:
                X.append(float(forecast[hour][f]))
        times.append(forecast[hour]['time'])
    
    return X, times

# Format vector
def create_x_vector(last_data_points, forecast):
    X = []
    times = []
    
    # Add current timestamp's values to X vector
    for p in last_data_points:
        X.append(float(p['moistureLocal']))

    times.append(forecast[0]['time'])
    
    # Add forecast values to X vector
    for hour in range(1, 25):
        for f in numerical_features:
            if f not in local_features:
                X.append(float(forecast[hour][f]))
        times.append(forecast[hour]['time'])
    
    return X, times

# Format timescale data into X and Y vectors
def format_X_Y_u(data):
    X = []
    Y = []
    
    final_data_sample_date = data[len(data)-1]['enqueuedTime']
    
    for d in range(len(data)):
        
        sample_X = []
        sample_Y = []
        
        sample_plus_24_hours = data[d]['enqueuedTime'] + timedelta(hours = 24)
        
        if sample_plus_24_hours <= final_data_sample_date: # Data is arranged in chronological order
        
            # Add present-time values to X
            for f in numerical_features:
                sample_X.append(float(data[d][f]))
            
            # Add forecast to X
            i = d + 4
            while i <= d + (4 * 24):
                for f in numerical_features:
                    if f not in local_features: # Excluding these as we're only using DarkSky Weather forecast
                        sample_X.append(float(data[i][f]))
                
                sample_Y.append(float(data[i]['moistureLocal']))
                i += 4
                
            X.append(sample_X)
            Y.append(sample_Y)
    
    return X, Y
    
# Format timescale data into X and Y vectors
def format_X_Y(data):
    X = []
    Y = []
    
    final_data_sample_date = data[len(data)-1]['enqueuedTime']
    
    past_hours = 12*4
    
    for d in range(past_hours, len(data)):
        
        sample_X = []
        sample_Y = []
        
        sample_plus_24_hours = data[d]['enqueuedTime'] + timedelta(hours = 24)
        
        if sample_plus_24_hours <= final_data_sample_date: # Data is arranged in chronological order
        
            # Add past and present-time values to X
            for j in range(past_hours, -1, -4):
                sample_X.append(float(data[d-j]['moistureLocal']))
                # for f in numerical_features:
                    # sample_X.append(float(data[d-j][f]))
            
            # Add forecast to X
            i = d + 4
            while i <= d + (4 * 24):
                for f in numerical_features:
                    if f not in local_features: # Excluding these as we're only using DarkSky Weather forecast
                        sample_X.append(float(data[i][f]))
                
                sample_Y.append(float(data[i]['moistureLocal']))
                i += 4
                
            X.append(sample_X)
            Y.append(sample_Y)
    
    return X, Y
    
# Save plots for (feature vs time)
def plot_data(data):

    for val in numerical_features:
    
        X = []
        Y = []
        
        for d in data:
            X.append(d['enqueuedTime'])
            Y.append(float(d[val]))

        filepath = "/fs/student/aditya_wadaskar/iot/ML_training/figs/" + str(val)
        
        plt.title(val)
        plt.xlabel('Day')
        plt.ylabel(val)
        plt.plot_date(X, Y)
        fig = plt.gcf()
        if val == 'temperature' or val == 'temperatureLocal':
            plt.ylim(5, 34)
        fig.set_size_inches(15, 12)
        fig.savefig(filepath)
        plt.clf()

