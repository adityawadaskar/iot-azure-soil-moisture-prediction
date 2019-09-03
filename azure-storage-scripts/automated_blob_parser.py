# CS293S W19 Soil Sensor [authors: chowdhury, kakade, wadaskar]
# contact: sayalirkakade@gmail.com
#
# automated_blob_parser.py
# Cron job runs this script every 5 minutes. During each run, the unparsed local sensor data blobs are parsed and for
# the number of messages available in these blobs, values from the Dark Sky API for weather statistics are appended to
# each of the local sensor data messages. Each messages forms an entity which is uploaded to the
# 'parsedsoilmoisturemessages' table.

import datetime
from forecastiopy import *
from azure.storage.blob import BlockBlobService
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity

# ------------ GLOBAL CONSTANTS ------------------------------------------
# FULL filepath to file storing the last blob that was processed and uploaded.
filename = "/fs/student/sayalikakade/cs293s/soil-sensor-293s/last_blob_processed.txt"


def run_parsing_pipeline():
    try:
        block_blob_service = BlockBlobService(account_name='soilhumiditydata293s', account_key='4PSsEO1xBAIdq3/MppWm+t6eYHi+CWhVn6xNZ6i4mLVgm50K8+NK6lA94v8MxG0bvVEfYCvsv1suxCyCnUYd0A==')
        table_service = TableService(account_name='soilhumiditydata293s', account_key='4PSsEO1xBAIdq3/MppWm+t6eYHi+CWhVn6xNZ6i4mLVgm50K8+NK6lA94v8MxG0bvVEfYCvsv1suxCyCnUYd0A==')

        container_name = "soilmoisturemessages"
        table_name = "parsedsoilmoisturemessages"

        sensor_blob_list = block_blob_service.list_blobs(container_name, prefix='soil-moisture-hub-free-293s')
        sensor_blob_list = [x for x in sensor_blob_list if True]

        dark_sky_current_reading = get_current_darksky_readings()

        # Get the name of the final processed blob from the file.
        f = open(filename, 'r')
        starting_blob_name = f.read()
        f.close()

        # Find starting bound of blobs to be processed.
        starting_index = 0
        for blob in sensor_blob_list:
            if blob.name == starting_blob_name:
                starting_index = sensor_blob_list.index(blob)
                break

        entities_created = []
        for blob in sensor_blob_list[starting_index + 1:]:
            print("Currently processing blob: " + blob.name)
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

        # Upload all the new entities.
        for e in entities_created:
            for data in dark_sky_current_reading:
                if data is not 'time':
                    e[data] = dark_sky_current_reading.get(data)
            table_service.insert_entity(table_name, e)

        print("Entities written: {}".format(len(entities_created)))

        # Store last processed blob name in same text file.
        f = open(filename, 'w')
        f.write(sensor_blob_list[-1].name)
        print("Final blob processed: " + sensor_blob_list[-1].name)
        f.close()

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


def get_current_darksky_readings():
    darksky_api_key = '7358efac8f40bf49ceaa4a8c5278bd31'
    goleta_coordinates = [34.4099508, -119.8661304]

    fio = ForecastIO.ForecastIO(darksky_api_key,
                                units=ForecastIO.ForecastIO.UNITS_SI,
                                lang=ForecastIO.ForecastIO.LANG_ENGLISH,
                                latitude=goleta_coordinates[0], longitude=goleta_coordinates[1])

    parameters = ['time', 'ozone', 'windGust', 'temperature', 'dewPoint', 'humidity', 'apparentTemperature', 'pressure',
                  'windSpeed', 'precipProbability', 'visibility', 'cloudCover', 'precipIntensity']

    if fio.has_currently() is True:
        currently = FIOCurrently.FIOCurrently(fio)

        store_values = {}

        for item in parameters:
            if item == 'time':
                currently.time = datetime.datetime.fromtimestamp(int(currently.time)).strftime('%Y-%m-%d %H:%M:%S')
                currently.time = datetime.datetime.strptime(currently.time, '%Y-%m-%d %H:%M:%S')
                currently.time = currently.time + datetime.timedelta(hours=8, minutes=0)
                store_values[item] = currently.time
            else:
                store_values[item] = currently.get()[item]

        return store_values

    else:
        return -1


if __name__ == '__main__':
    run_parsing_pipeline()
