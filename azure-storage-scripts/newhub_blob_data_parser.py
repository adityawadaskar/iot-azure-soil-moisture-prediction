# CS293S W19 Soil Sensor [authors: chowdhury, kakade, wadaskar]
# contact: sayalirkakade@gmail.com
#
# previousdata_blob_parser.py
# Run once to parse all blob data from soil-mosture-hub/02/2019/02/21/00/00 to
# soil-moisture-hub-free-293s/00/2019/02/28/04/11. For each hour of blob data, one Dark Sky API call is made using the
# same time as the sensor data and one for one hour later, and the values in the blob are linearly interpolated based
# on the number of blob data points available in that hour.

import datetime, time
import requests
import json
from azure.storage.blob import BlockBlobService
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity


def run_first_parsing_pipeline(darksky_data):
    try:
        block_blob_service = BlockBlobService(account_name='soilhumiditydata293s', account_key='4PSsEO1xBAIdq3/MppWm+t6eYHi+CWhVn6xNZ6i4mLVgm50K8+NK6lA94v8MxG0bvVEfYCvsv1suxCyCnUYd0A==')
        table_service = TableService(account_name='soilhumiditydata293s', account_key='4PSsEO1xBAIdq3/MppWm+t6eYHi+CWhVn6xNZ6i4mLVgm50K8+NK6lA94v8MxG0bvVEfYCvsv1suxCyCnUYd0A==')

        container_name = "soilmoisturemessages"
        table_name = "trainingDataPastSoilMoistureMessagesV2"

        # First, collect data from the old soil moisture hub blobs.
        sensor_blob_list = block_blob_service.list_blobs(container_name, prefix='soil-moisture-hub-free-293s')
        sensor_blob_list = [x for x in sensor_blob_list if True]

        ending_blob_name = 'soil-moisture-hub-free-293s/00/2019/02/28/04/11'

        # Find starting bound of blobs to be processed.
        ending_index = 0
        for blob in sensor_blob_list:
            if blob.name == ending_blob_name:
                ending_index = sensor_blob_list.index(blob)
                break

        entities_created = []
        interpolated_data = {}
        data_point_counter = 0

        # Loop through blobs - run interpolation and upload every time we are in a new hour of the day.
        for blob in sensor_blob_list[:ending_index + 1]:
            print("Currently processing blob: " + blob.name)
            blob_minute = blob.name[-2:]
            blob_content = block_blob_service.get_blob_to_text(container_name, blob.name, encoding='latin-1').content

            next_temp = 0
            while next_temp != -1:
                blob_content = blob_content[next_temp:]
                new_entity = Entity()
                new_entity.PartitionKey = datetime.datetime.strftime(blob.properties.creation_time, "%Y%m%d")
                next_temp = integrate_localsensor_data(new_entity, blob_content)
                new_entity.RowKey = datetime.datetime.strftime(blob.properties.creation_time, "%H%M") \
                                    + new_entity.get('messageIdLocal').zfill(2)
                entities_created.append(new_entity)
                data_point_counter += 1

            # If our blob is in 58 or 59 minute, run interpolation and upload values for the past hour.
            if blob_minute == '58' or blob_minute == '59' or blob.name == 'soil-moisture-hub-free-293s/00/2019/02/28/04/11':
                print("Reached end of hour: " + blob.name)
                blob_hour = int(blob.name[-5:-3])
                blob_date = int(blob.name[-8:-6])

                current_hour = blob_hour + 1 if blob_hour != 23 else 0
                current_date = blob_date if blob_hour != 23 else blob_date + 1
                current_dark_sky_data = darksky_data[datetime.datetime(2019, 2, current_date, current_hour)]
                past_dark_sky_data = darksky_data[datetime.datetime(2019, 2, blob_date, blob_hour)]

                print("Interpolating for current hour batch...")
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


def integrate_localsensor_data(entity_object, blob_content):
    search_list = ['enqueuedTime8', '"messageId":', '"temperature":', '"humidity":', '"moisture":']
    end_index = 0

    for str in search_list:
        start_index = blob_content.find(str) + len(str)
        if str == 'enqueuedTime8':
            end_index = blob_content.find('Z', start_index)
            key_string = str[0:-1]
        else:
            end_index = blob_content.find(',', start_index)
            key_string = str[1:-2] + "Local"
        sensor_val = blob_content[start_index: end_index]
        entity_object[key_string] = sensor_val

    return blob_content.find('enqueuedTime8', end_index)


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
    print("Running parsing for soil moisture data from soil-mosture-hub/02/2019/02/21/00/00 to \n"
          "soil-mosture-hub/02/2019/02/26/06/57.")
    print("Collecting dark sky data from Feb 21 to Feb 26.")
    darksky_data_first_batch = {}
    for date in range(25, 29):
        darksky_reading = get_past_darksky_readings(datetime.datetime(2019, 2, date))
        for hourly_data in darksky_reading:
            darksky_data_first_batch[hourly_data['time']] = hourly_data

    print("Uploading first batch of data to table.")
    run_first_parsing_pipeline(darksky_data_first_batch)
