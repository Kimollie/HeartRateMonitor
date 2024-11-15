import network
from time import sleep
from umqtt.simple import MQTTClient
import ujson

# Replace these values with your own
SSID = "KME761_Group_5"
PASSWORD = "TeamFive12345?"
BROKER_IP = "192.168.5.253"

# Function to connect to WLAN
def connect_wlan():
    # Connecting to the group WLAN
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    # Attempt to connect once per second
    while wlan.isconnected() == False:
        print("Connecting... ")
        sleep(1)

    # Print the IP address of the Pico
    print("Connection successful. Pico IP:", wlan.ifconfig()[0])
    
def connect_mqtt():
    mqtt_client=MQTTClient("", BROKER_IP)
    mqtt_client.connect(clean_session=True)
    return mqtt_client
mean_hr = 70
mean_ppi = 80
rmssd = 20
sdnn = 23
# Main program
if __name__ == "__main__":
    #Connect to WLAN
    connect_wlan()
    
    # Connect to MQTT
    try:
        mqtt_client=connect_mqtt()
        
    except Exception as e:
        print(f"Failed to connect to MQTT: {e}")

    # Send MQTT message
    try:
        while True:
            # Sending a message every 5 seconds.
            topic = "HRV"
            message = {
                "sdnn": sdnn,
                "mean_hr": mean_hr,
                "mean_ppi": mean_ppi,
                "rmssd": rmssd
                }
            json_message = ujson.dumps(message)
            mqtt_client.publish(topic, json_message)
            print(f"Sending to MQTT: {topic} -> {json_message}")
            sleep(5)
            
    except Exception as e:
        print(f"Failed to send MQTT message: {e}")
