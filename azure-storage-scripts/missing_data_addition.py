# CS293S W19 Soil Sensor [authors: chowdhury, kakade, wadaskar]
# contact: sayalirkakade@gmail.com
#
# missing_data_addition.py
# Interpolate Dark Sky data from 2/26/2019 7:00 PM UTC to 2/27/2019 2:15 AM UTC and insert values in data table.

import datetime, time
import requests
import json
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity


def run_first_parsing_pipeline(darksky_data):
    try:
        table_service = TableService(account_name='soilhumiditydata293s', account_key='4PSsEO1xBAIdq3/MppWm+t6eYHi+CWhVn6xNZ6i4mLVgm50K8+NK6lA94v8MxG0bvVEfYCvsv1suxCyCnUYd0A==')

        container_name = "soilmoisturemessages"
        table_name = "trainingDataPastSoilMoistureMessagesV2"

        # Generate a list of hypothetical blob datetimes to add table Entities for.
        fake_blob_list = generate_fake_blobs()

        entities_created = []
        interpolated_data = {}
        data_point_counter = 0
        message_id = 8  # values from 1 to 65 inclusive

        # Loop through blobs - run interpolation and upload every time we are in a new hour of the day.
        for blob in fake_blob_list:
            print("Currently processing blob: " + datetime.datetime.strftime(blob, "%Y/%m/%d %H:%M:%S"))
            blob_minute = blob.minute

            new_entity = Entity()
            new_entity.PartitionKey = datetime.datetime.strftime(blob, "%Y%m%d")
            message_id = integrate_localsensor_data(new_entity, blob, message_id)
            new_entity.RowKey = datetime.datetime.strftime(blob, "%H%M") \
                                + new_entity.get('messageIdLocal').zfill(2)
            entities_created.append(new_entity)
            data_point_counter += 1

            # If our blob is in 58 or 59 minute, run interpolation and upload values for the past hour.
            if blob_minute == 59:
                print("Reached end of hour: " + str(blob))
                blob_hour = blob.hour
                blob_date = blob.day

                current_hour = blob_hour + 1 if blob_hour != 23 else 0
                current_date = blob_date if blob_hour != 23 else blob_date + 1
                current_dark_sky_data = darksky_data[datetime.datetime(2019, 2, current_date, current_hour)]
                past_dark_sky_data = darksky_data[datetime.datetime(2019, 2, blob_date, blob_hour)]

                print("Interpolating for current hour batch...")
                time.sleep(2)
                for data in past_dark_sky_data:
                    if str(data) != "time":
                        starting_value = past_dark_sky_data[data]
                        ending_value = current_dark_sky_data[data]
                        delta = (ending_value - starting_value) / data_point_counter
                        interpolated_data[data] = []
                        for i in range(data_point_counter):
                            interpolated_data[data].append(starting_value + (i * delta))

                # Upload entities.
                print("Uploading for current hour batch...")
                for x in range(data_point_counter):
                    e = entities_created[x]
                    for data in interpolated_data:
                        e[data] = interpolated_data.get(data)[x]
                    table_service.insert_entity(table_name, e)

                print("Entities inserted: {}".format(len(entities_created)))

                # Reset counters.
                data_point_counter = 0
                entities_created = []
                interpolated_data = {}

    except Exception as e:
        print(e)


def integrate_localsensor_data(entity_object, blob_datetime, message_id):
    search_list = ['enqueuedTime8', '"messageId":', '"temperature":', '"humidity":', '"moisture":']

    for s in search_list:
        if s == 'enqueuedTime8':
            key_string = s[0:-1]
            value = datetime.datetime.strftime(blob_datetime, "%Y-%m-%dT%H:%M:%S.0000000")
        elif s == '"messageId":':
            key_string = s[1:-2] + "Local"
            value = str(message_id)
        else:
            key_string = s[1:-2] + "Local"
            value = -1
        entity_object[key_string] = value

    m = 1 if message_id == 65 else message_id + 1
    return m


def generate_fake_blobs():
    blob_list = []
    current_time = datetime.datetime(2019, 2, 26, hour=7, minute=0)
    while current_time != datetime.datetime(2019, 2, 26, hour=19, minute=0):
        blob_list.append(current_time)
        current_time = current_time + datetime.timedelta(minutes=1)
    return blob_list


def get_past_darksky_readings(d):
    '''
    :param d: A datetime.datetime object with a given year, month, and day.
    e.g. get_past_darksky_readings(datetime.datetime(2019, 2, 20))
    :return: Hourly weather forecasts for Goleta on the date in the past.
    '''

    # Convert to ISO format
    d_iso = int(time.mktime(d.timetuple()))
    api_query = "https://api.darksky.net/forecast/7358efac8f40bf49ceaa4a8c5278bd31/34.4099508,-119.8661304," + str(
        d_iso)
    r = requests.get(api_query)
    r = json.loads(r.content)

    parameters = ['time', 'ozone', 'windGust', 'temperature', 'dewPoint', 'humidity', 'apparentTemperature', 'pressure',
                  'windSpeed', 'precipProbability', 'visibility', 'cloudCover', 'precipIntensity']

    past_data = []

    for hour in r["hourly"]["data"]:
        hourly_data = {}
        for item in hour:
            for p in parameters:
                if item == p:
                    hourly_data[item] = hour[item]
                    if p == "time":
                        hourly_data["time"] = datetime.datetime.fromtimestamp(int(hourly_data["time"])).strftime(
                            '%Y-%m-%d %H:%M:%S')
                        hourly_data["time"] = datetime.datetime.strptime(hourly_data["time"], '%Y-%m-%d %H:%M:%S')
                        hourly_data["time"] = hourly_data["time"] + datetime.timedelta(hours=8, minutes=0)
        past_data.append(hourly_data)

    return past_data


if __name__ == '__main__':
    print("Running missing data addition from Feb 26 7 PM to Feb 27 2:15 AM.")
    print("Collecting Dark Sky data...")
    darksky_data = {}
    for date in range(25, 28):
        darksky_reading = get_past_darksky_readings(datetime.datetime(2019, 2, date))
        for hourly_data in darksky_reading:
            darksky_data[hourly_data['time']] = hourly_data

    print("Interpolating data and uploading to table. Local values indicated with '-1'.")
    run_first_parsing_pipeline(darksky_data)
