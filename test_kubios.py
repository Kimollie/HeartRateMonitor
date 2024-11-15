import urequests as requests
import ujson
from time import sleep
import network

class Network:
    def __init__(self):
        self.ssid = "KME761_Group_5"
        self.password = "TeamFive12345?"
        self.broker_ip = "192.168.5.253"
        self.wlan = None
        self.mqtt_client = None
    
    def connect_to_wlan(self):
        # Create WLAN instance and connect to the network
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.password)
        
        # Attempt to connect once per second
        while not self.wlan.isconnected():
            print("Connecting to WLAN...")
            time.sleep(1)
        
        # Print the IP address of the Pico
        print("Connection successful. Pico IP:", self.wlan.ifconfig()[0])
    
    def connect_mqtt(self):
        # Create and connect to MQTT client
        self.mqtt_client = MQTTClient("", self.broker_ip)
        self.mqtt_client.connect(clean_session=True)
        print(f"Connected to MQTT broker at {self.broker_ip}")
        return self.mqtt_client
    
    def send_mqtt_message(self, topic, message, interval=5):
        try:
            while True:
                # Sending a message every `interval` seconds
                self.mqtt_client.publish(topic, message)
                print(f"Sending to MQTT: {topic} -> {message}")
                sleep(interval)
        except Exception as e:
            print(f"Failed to send MQTT message: {e}")
            
Network().connect_to_wlan

APIKEY = "pbZRUi49X48I56oL1Lq8y8NDjq6rPfzX3AQeNo3a"
CLIENT_ID = "3pjgjdmamlj759te85icf0lucv"
CLIENT_SECRET = "111fqsli1eo7mejcrlffbklvftcnfl4keoadrdv1o45vt9pndlef"
LOGIN_URL = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/login"
TOKEN_URL = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/oauth2/token"
REDIRECT_URI = "https://analysis.kubioscloud.com/v1/portal/login"
response = requests.post(
    url = TOKEN_URL,
    data = 'grant_type=client_credentials&client_id={}'.format(CLIENT_ID),
    headers = {'Content-Type':'application/x-www-form-urlencoded'},
    auth = (CLIENT_ID, CLIENT_SECRET))

response = response.json() #Parse JSON response into a python dictionary
access_token = response["access_token"] #Parse access token
#Interval data to be sent to Kubios Cloud. Replace with your own data:
intervals = [828, 836, 852, 760, 800, 796, 856, 824, 808, 776, 724, 816, 800, 812, 812, 812, 756, 820, 812, 800]
#Create the dataset dictionary HERE
    
dataset = {
    "type": "RRI",
    "data": intervals,
    "analysis": {"type": "readiness"}
    }

# Make the readiness analysis with the given data
response = requests.post(
    url = "https://analysis.kubioscloud.com/v2/analytics/analyze",
    headers = { "Authorization": "Bearer {}".format(access_token), #use access token to access your Kubios Cloud analysis session
                "X-Api-Key": APIKEY},
    json = dataset) #dataset will be automatically converted to JSON by the urequests library

response = response.json()
print(response)
if not response == {'status': 'error', 'error': 'Error validating against schema'}:
# Extract the specific values from the response dictionary
    mean_hr_bpm = response['analysis']['mean_hr_bpm']
    mean_ppi_ms = response['analysis']['mean_rr_ms']
    rmssd_ms = response['analysis']['rmssd_ms']
    sdnn_ms = response['analysis']['sdnn_ms']
    sns_index = response['analysis']['sns_index']
    pns_index = response['analysis']['pns_index']
    timestamp = response['analysis']['create_timestamp']

    # Split the timestamp at 'T' to separate date and time
    date_part, time_part = timestamp.split('T')

    # Further process time_part to remove the timezone information
    time_part = time_part.split('+')[0]  # Remove timezone information
    
    timestamp = date_part + " " + time_part

    # Print the separated date and time components
    print(f"Time {timestamp}")

    #Print out the SNS and PNS values on the OLED screen here
    print(f"Mean HR: {mean_hr_bpm:.0f}")
    print(f"Mean PPI: {mean_ppi_ms:.0f}")
    print(f"RMSSD: {rmssd_ms:.0f}")
    print(f"SDNN: {sdnn_ms:.0f}")
    print(f"SNS: {sns_index:.0f}")
    print(f"PNS: {pns_index:.0f}")
else:
    print("error")