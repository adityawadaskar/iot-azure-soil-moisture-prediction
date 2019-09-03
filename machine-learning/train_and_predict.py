"""
CS293S W19 Soil Sensor [authors: chowdhury, kakade, wadaskar]

train_and_predict.py

What  :  Retrieves sensor data from Azure, trains ML model to predict soil moisture levels, updates predictions to Azure
When  :  Every 30 minutes (cron job)
Where :  CSIL Server
Who   :  wadaskar.aditya@gmail.com

"""

from data import *
from sklearn.model_selection import train_test_split
from sklearn import linear_model
from sklearn.metrics import mean_squared_error
from sklearn.ensemble import RandomForestRegressor

load_existing = False
plot = True

# ------------------------------------------------
# Train and store ML model
# ------------------------------------------------

# Load data
data = load_data("data_pickle", load_existing)

# Format data as X and Y
X, Y = format_X_Y(data)

if plot:
    plot_data(data)

reg = linear_model.LinearRegression(normalize=True)
reg.fit(X, Y)

# Store ML model
pickle_store_model = open("/fs/student/aditya_wadaskar/iot/ML_training/model", 'wb')
pickle.dump(reg, pickle_store_model)
pickle_store_model.close()

store_trained_model_in_azure(reg)

# ------------------------------------------------
# Make and store prediction for current timestamp
# ------------------------------------------------

forecast = get_weather_forecast()
last_data_points = []
for i in range(48, -1, -4):
    last_data_points.append(data[len(data)-1-i])

X, times = create_x_vector(last_data_points, forecast) # Format input vector
Y_pred = [last_data_points[len(last_data_points)-1]['moistureLocal']]
Y_pred.extend(reg.predict([X])[0])

for i in range(len(Y_pred)):
    if Y_pred[i] < 0.0:
        Y_pred[i] = 0.0

store_predictions_in_table(Y_pred, times)
    
# main()
