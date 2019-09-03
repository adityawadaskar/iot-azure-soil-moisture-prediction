# SoilSmart - Final Project
CMPSC 293S - Winter 2019 | Himangshu Chowdhury, Sayali Kakade, Aditya Wadaskar

## Project Description

The goal of this project is to predict soil moisture levels for next 24 hours using data from a local sensor setup and weather forecast.

### Repo Breakdown

1. hardware-setup: Contains Arduino .ino files that are executing on ESP8266. Collect sensor data and upload to Azure IoT Hub.
2. azure-storage-scripts: Parse sensor data stored in blobs and save data in tabular format with Dark Sky API weather data.
3. machine-learning: Script that trains linear regression model and saves predictions in Azure
4. webapp-files: HTML/CSS/JavaScript files for Dashboard UI for insights into moisture predictions.

## Built With

* [Scikit-Learn](https://scikit-learn.org/) - The machine learning toolset used
* [Dark Sky Weather API](https://darksky.net/dev) - Weather API for forecast and past data
* [Azure Cloud](https://azure.microsoft.com/en-us/) - Used to store data and predictions
* [amCharts](https://www.amcharts.com/) - JavaScript tool for visualization

## Authors

* **Himangshu Chowdhury** - *Hardware Setup, Dashboard* - [GitHub](https://github.com/himangshuc)
* **Sayali Kakade** - *Azure Setup, Dashboard* - [GitHub](https://github.com/sayalirkakade)
* **Aditya Wadaskar** - *Machine Learning* - [GitHub](https://github.com/adityawadaskar)

## Acknowledgments

* Markus Mock - Visiting Professor from Germany at UCSB
* Chandra Krintz - Computer Science Professor at UCSB
* Rich Wolski - Computer Science Professor at UCSB
# iot-azure-soil-moisture-prediction
