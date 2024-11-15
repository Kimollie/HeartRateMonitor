import micropython
micropython.alloc_emergency_exception_buf(200)
from machine import Pin, ADC, I2C
from ssd1306 import SSD1306_I2C
from fifo import Fifo
from led import Led
import time
from piotimer import Piotimer
import math
import network
from umqtt.simple import MQTTClient
import ujson as json
import urequests as requests


##################################### CHANGEABLE VARIABLES LOCATION ########################################


"Class NETWORK: Network's ssid, password, and Pico's broker ip"
"Class KUBIOS: Kubios's api key, client id and client secret"
"Class OLED: OLED settings: scl pin, sda pin, width, height, frequency, font size"
"Class SENSOR: data sampling frequency, ADC pin, beat LED pin, min max interval range, data filter range"


########################################### STARTER CLASSES ###############################################


# class Encoder for handling rotation and button press
class Encoder:
    def __init__(self):
        self.a = Pin(10, mode = Pin.IN, pull = Pin.PULL_UP)
        self.b = Pin(11, mode = Pin.IN, pull = Pin.PULL_UP)
        self.btn = Pin(12, mode = Pin.IN, pull = Pin.PULL_UP)
        self.fifo = Fifo(30, typecode = 'i') #fifo to store rotate/ press event 
        self.a.irq(handler = self.rot_handler, trigger = Pin.IRQ_RISING, hard = True)
        self.btn.irq(handler = self.btn_handler, trigger = Pin.IRQ_RISING, hard = True)
        self.current_time = 0 #keep track of time diff bw button press
        self.prev_time = 0
        
    def rot_handler(self, pin):
        if self.b():
            self.fifo.put(-1) #to move arrow up when turn anti-clockwise
        else:
            self.fifo.put(1) #to move arrow down when turn clockwise
    
    def btn_handler(self, pin):
        self.current_time = time.ticks_ms()
        if int(self.current_time) - int(self.prev_time) > 300: #debounce time 300ms bw button press
            self.fifo.put(5) #track btn press with different value
            self.prev_time = self.current_time
            
            
# class Network for WiFi and MQTT connections
class Network:
    def __init__(self):
        self.ssid = "KME761_Group_5"
        self.password = "TeamFive12345?"
        self.broker_ip = "192.168.5.253"
        self.wlan = network.WLAN(network.STA_IF)
        self.mqtt_client = None
        self.oled = OLED()
    
    def connect_to_wlan(self):
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.password)
    
        max_attempts = 5 #5 attempts to try connect to network
        attempt = 0        
        while not self.wlan.isconnected() and attempt <= max_attempts:
            self.oled.display_message("Connect WLAN..") #display message when waiting for connection
            time.sleep(1)  
            attempt += 1
        
        #display if Wifi connected or no network available
        if self.wlan.isconnected():
            self.oled.display_message("WLAN Connected") 
            time.sleep(0.5)
        else:
            self.oled.display_message("No Network")
            time.sleep(1)

    def connect_mqtt(self):
        self.mqtt_client = MQTTClient("", self.broker_ip)
        self.mqtt_client.connect(clean_session=True)
        return self.mqtt_client
    
    def send_mqtt_message(self, topic, message):
        self.mqtt_client.publish(topic, message)


# class Kubios for handling authentification and sending data
class Kubios:
    def __init__(self):
        self.api_key = "pbZRUi49X48I56oL1Lq8y8NDjq6rPfzX3AQeNo3a" 
        self.client_id = "3pjgjdmamlj759te85icf0lucv"
        self.client_secret = "111fqsli1eo7mejcrlffbklvftcnfl4keoadrdv1o45vt9pndlef"
        self.login_url = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/login"
        self.token_url = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/oauth2/token"
        self.redirect_uri = "https://analysis.kubioscloud.com/v1/portal/login"
        self.access_token = None
    
    def authenticate(self): #use given info to access to Kubios
        response = requests.post(
            url=self.token_url,
            data=f'grant_type=client_credentials&client_id={self.client_id}',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            auth=(self.client_id, self.client_secret)
        )
        response_data = response.json()  
        self.access_token = response_data.get("access_token")  #parse access token

    def send_data_to_kubios(self, data):
        # Create the dataset dictionary from data array
        dataset = {
            "type": "RRI",
            "data": data,
            "analysis": {"type": "readiness"}
            }
        response = requests.post(
            url="https://analysis.kubioscloud.com/v2/analytics/analyze",
            headers={
                "Authorization": f"Bearer {self.access_token}",  #use access token to access Kubios Cloud analysis session
                "X-Api-Key": self.api_key
            },
            json=dataset  #dataset automatically converted to JSON by the urequests library
        )
        response_data = response.json()  #parse the JSON response        
        return response_data



##################################### DATA PROCESSING/DISPLAYING CLASSES #####################################
 
 

# class OLED for display menu, heart rate, time, signal, message, HRV, Kubios
class OLED:
    def __init__(self, scl_pin=15, sda_pin=14, width=128, height=64, freq=400000):
        self.i2c = I2C(1, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
        self.oled = SSD1306_I2C(width, height, self.i2c)
        self.heart = [
            [0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 1, 0, 0, 0, 1, 1, 0],
            [1, 1, 1, 1, 0, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 1, 1, 0],
            [0, 0, 1, 1, 1, 1, 1, 0, 0],
            [0, 0, 0, 1, 1, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0, 0, 0],
        ]
        self.size = 8 #font size
        self.max_adc = 65535 #max val read from sensor => this use for display raw signal
        self.last_x = -1 
        self.last_y = self.oled.height//2 #last y pos middle of screen
        
    def display_menu(self, lines, arrow_pos, left_arrow, right_arrow):
        self.oled.fill(0)  
        for i, line in enumerate(lines): #display each line of the menu
            self.oled.text(line, self.size, i * self.size * 2)
        self.oled.text(left_arrow, 0, arrow_pos) #display left and right arrows
        right_arrow_x = len(lines[0]) * self.size + self.size
        self.oled.text(right_arrow, right_arrow_x, arrow_pos)
        self.oled.show()
        
    def display_heart_rate(self, hr): #display heart rate on top/ not show, as it will be refreshed with raw signal (which constantly updated)
        self.oled.fill_rect(0, 0, self.oled.width, self.size, 0) #clear top rect
        self.oled.text(f"{hr} bpm", 45, 0)
        for y, row in enumerate(self.heart): #draw heart before heart rate
            for x, c in enumerate(row):
                self.oled.pixel(x+30, y, c)
        
    def display_time(self, time): #display time at bottom /no oled.show cause will be showed together with raw signal (which constantly updated)        
        self.oled.fill_rect(0, self.oled.height-self.size, self.oled.width, self.oled.height, 0) #clear bottom rect
        self.oled.text(f"Time: {time}s", 30, self.oled.height-8)
       
    def display_signal(self,val): #display raw signal
        y = self.oled.height - int(val*self.oled.height/self.max_adc) #scale y-value(0-65535) to (0-63) => invert y values
        y = max(self.size + 2, min(self.oled.height-self.size-2 , y)) #cap y values to (10-53), cause top and bottom reserved for hr and time ,+2/-2 for spacing
        x = self.last_x + 1 # x increment
        self.oled.line(self.last_x, self.last_y, x, y, 1) #draw line from last xy and new xy values
        self.oled.show()         
        self.last_x = x
        self.last_y = y
        if self.last_x > self.oled.width-1: #check if line reach right edge
            self.oled.fill_rect(0,self.size, self.oled.width, self.oled.height- 2*self.size, 0) #clear middle rect
            self.last_x = -1        
    
    def display_message(self,text): #display any message
        self.oled.fill(1)
        margin = (self.oled.width - (len(text)*self.size))//2
        self.oled.text(text, margin, self.oled.height//2, 0) #make sure message in middle screen            
        self.oled.show()
        
    def display_HRV(self, mean_hr, mean_ppi, rmssd, sdnn): 
        self.oled.fill(0) 
        HRV = [
            f"Mean HR: {mean_hr:.0f}",
            f"Mean PPI: {mean_ppi:.0f}",
            f"RMSSD: {rmssd:.0f}",
            f"SDNN: {sdnn:.0f}",
        ]        
        for i, line in enumerate(HRV): #display HRV lines
            self.oled.text(line, 0, i * 16)
        self.oled.show()
    
    def display_kubios(self, timestamp, mean_hr, mean_ppi, rmssd, sdnn, sns, pns):
        self.oled.fill(0)
        data = [
            f"{timestamp}",
            f"Mean HR: {mean_hr:.0f}",
            f"Mean PPI: {mean_ppi:.0f}",
            f"RMSSD: {rmssd:.0f}",
            f"SDNN: {sdnn:.0f}",
            f"SNS: {sns:.4f}",
            f"PNS: {pns:.4f}"
        ]
        for i, line in enumerate(data):
            self.oled.text(line, 0, i * 9)
        self.oled.show()


# class Sensor to collect and process signal
class Sensor:
    def __init__(self,option):
        self.option = option #keep track of which option is running and use option's or menu's function
        self.freq = 250
        self.adc = ADC(26)
        self.data = Fifo(500)
        self.oled = OLED()
        self.led = Led(21, Pin.OUT, 0.5)
        self.running = True

    def read_sample(self, tid): #collect data from ADC
        self.data.put(self.adc.read_u16())
    
    def reset(self): #clear out all previous data/ reseting timer and time tracker
        self.samples = []
        self.MAX_SAMPLES = 150  # Maximum 150 samples in samples array
        self.min_interval = self.freq * 0.25  # Maximum heart rate 240 BPM => max PPI 250 ms => min sample interval = 0.25 * freq (62.5 samples)
        self.max_interval = self.freq * 2  # Minimum heart rate 30 BPM => min PPI 2000 ms => max sample interval = 2 * freq (500 samples)
        self.rise = False
        self.ris_edges = [0]
        self.hr_arr = []
        self.PPI_arr = []
        self.index = 0
        self.bad_signal_count = 0
        self.hr_5s = []
        
        #PIOTimer
        self.timer = Piotimer(mode=Piotimer.PERIODIC, freq=self.freq, callback=self.read_sample)

        #Time tracker
        self.start_time = time.time()
        self.elapsed_time = 0
        self.last_hr_time = self.start_time  #track the last time heart rate was printed
        self.last_time = self.start_time  #track the last time <time> was printed
    
    def calculate_hr(self, interval):
        return int(60 / (interval / self.freq))
    
    def calculate_mean_hr(self):
        if len(self.hr_arr) > 2:
            return round(sum(self.hr_arr) / len(self.hr_arr))
        else:
            return None

    def calculate_mean_ppi(self): 
        return round(sum(self.PPI_arr) / len(self.PPI_arr)) #no need to check if >2 cause this is only called at end of HRV, PPI will be >2
    
    def calculate_rmssd(self):
        successive_diff = [self.PPI_arr[i] - self.PPI_arr[i - 1] for i in range(1, len(self.PPI_arr))]
        squared_diff = [diff ** 2 for diff in successive_diff]
        mean_squared_diff = sum(squared_diff) / len(squared_diff)
        return round(math.sqrt(mean_squared_diff))
    
    def calculate_sdnn(self):
        mean_ppi = self.calculate_mean_ppi() #calculate the mean of PPI array
        variance = sum([(ppi - mean_ppi) ** 2 for ppi in self.PPI_arr]) / len(self.PPI_arr)
        return round(math.sqrt(variance))
    
    def run(self):
        while self.data.has_data():
            val = self.data.get()
            self.index += 1
            if self.index % 20 == 0:
                self.oled.display_signal(val) #display raw data on OLED
            self.samples.append(val)    
            self.samples = self.samples[-self.MAX_SAMPLES:]  #keep most recent 150 samples for dynamic threshold
            if len(self.samples) == self.MAX_SAMPLES: #start when 150 samples collected
                min_val, max_val = min(self.samples), max(self.samples)
                if 3000 < max_val - min_val< 45000: #filter too small or to big diff bw max min (potential noises)
                    threshold_on = (min_val + max_val * 3) // 4  # Higher threshold to detect rising (75%)
                    threshold_off = (min_val + max_val) // 2  # Lower threshold to stop detecting new edge (eliminate lower rising edges)
                    hr = self.detect_hr(val, threshold_on, threshold_off)
            self.hr_update() #check to update heart rate every 5s
            self.stop_check() #check for btn press to stop sensor running

    def detect_hr(self, val, threshold_on, threshold_off): 
        interval = self.index - self.ris_edges[-1] #calculate how many samples between current val and last detected rising edge
        if not self.rise and val > threshold_on and self.min_interval <= interval <= self.max_interval: #detect edge within acceptable range (30-240bpm)
            self.rise = True
            self.ris_edges.append(self.index)
            self.led.on()
            if len(self.ris_edges) > 2: #detect at least 2 rising edge
                hr = self.calculate_hr(interval)
                self.hr_arr.append(hr)
                self.hr_5s.append(hr)
                self.PPI_arr.append(interval*4)
                return hr                    
        elif self.rise and val < threshold_off:
            self.rise = False
            self.led.off()
    
    def hr_update(self): #check to update hr or send bad signal message
        current_time = time.time() 
        self.elapsed_time = current_time - self.start_time # calculate elapsed time since the start running sensor        
        if current_time - self.last_time >= 1:
            self.oled.display_time(self.elapsed_time) #display time every 1s
            self.last_time = current_time            
        if current_time - self.last_hr_time >= 5:#check if 5 seconds have elapsed => display the heart rate or "Bad signal"
            if len(self.hr_5s) > 2: 
                update1 = self.calculate_mean_hr()
                self.bad_signal_count = 0 #reset signal count cause only if 2 consecutive bad signal => stop
                self.oled.display_heart_rate(update1) #display heart rate
            else:    
                self.bad_signal_count += 1 #if in 5s less than 2 beats detected
                if self.bad_signal_count > 1: #2 consecutive bad signal => stop
                    self.stop()
                    self.oled.display_message("Bad Signal")                        
            self.hr_5s = []  #reset after 5s                  
            self.last_hr_time = current_time #set last hr printed time is current time
    
    def start(self): #start option 1 "Measuring heart rate"
        self.reset()
        while self.running:
            self.run() #run the sensor until btn press
        if self.elapsed_time >= 30:
            self.option.is_option1_menu = True
        else:
            self.option.running = False
                
    def start_op2(self): #start option 2 "HRV"
        self.reset()
        while self.elapsed_time < 30 and self.running:
            self.run()            
        self.timer.deinit() #stop read data for ADC        
        self.HRV_display()
        self.stop() #stop option and return to previous state
        self.option.running = False
        
    def HRV_display(self): #process data to calculate HRV and display on OLED
        #Processing 30s data
        if len(self.hr_arr) > 5 and self.elapsed_time >= 30: #check if there more than 5 beats detected
            mean_hr = self.calculate_mean_hr()
            mean_ppi = self.calculate_mean_ppi()
            rmssd = self.calculate_rmssd()
            sdnn = self.calculate_sdnn()           
            if self.option.menu.network.wlan.isconnected(): #check if wifi connected
                self.option.menu.network.connect_mqtt() #connect to mqtt
                topic = "HRV"
                #reformating data to be in 1 message
                message = {
                    "mean_hr": mean_hr,
                    "mean_ppi": mean_ppi,
                    "rmssd": rmssd,
                    "sdnn": sdnn
                    }
                json_message = json.dumps(message) #jsonfy message
                self.option.menu.network.send_mqtt_message(topic, json_message) #send to mqtt to show on subcriber
            else:
                self.oled.display_message("No internet") #if no internet then not send to mqtt
                time.sleep(1)
            self.oled.display_HRV(mean_hr, mean_ppi, rmssd, sdnn) #display HRV values
            
    def start_op3(self):
        self.reset()
        if self.option.menu.network.wlan.isconnected():            
            while self.elapsed_time < 30 and self.running:
                self.run()
            self.timer.deinit()
            self.Kubios_display()   
        else:
            self.oled.display_message("No internet") #if no network then kubios wont run
            time.sleep(1)
        self.stop()
        self.option.running = False
    
    def Kubios_display(self): #send data to Kubios and display analysis on OLED
        if len(self.PPI_arr) > 5 and self.elapsed_time >= 30:
            self.oled.display_message("Sending.....") #authenticate then send data to kubios             
            self.option.menu.kubios.authenticate()
            response = self.option.menu.kubios.send_data_to_kubios(self.PPI_arr)
            if not response == {'status': 'error', 'error': 'Error validating against schema'}: #check if response is valid
                mean_hr_bpm = response['analysis']['mean_hr_bpm']
                mean_ppi_ms = response['analysis']['mean_rr_ms']
                rmssd_ms = response['analysis']['rmssd_ms']
                sdnn_ms = response['analysis']['sdnn_ms']
                sns_index = response['analysis']['sns_index']
                pns_index = response['analysis']['pns_index']
                timestamp = response['analysis']['create_timestamp'] 
                data_date, data_time = timestamp.split('T')#split the timestamp at 'T' to separate date and time
                data_time = data_time.split('+')[0]  #remove timezone                     
                timestamp = data_date + " " + data_time #new clearer timestamp
                    
                #store data from Kubios to Menu's history
                new_data = {"timestamp": timestamp,"mean_hr_bpm": mean_hr_bpm,"mean_ppi_ms": mean_ppi_ms,"rmssd_ms": rmssd_ms,"sdnn_ms": sdnn_ms,"sns_index": sns_index,"pns_index": pns_index}
                with open("history.json", "r") as f: 
                    history = json.load(f)  #load existing data from history.json
                history.append(new_data)
                if len(history) > 4:
                    history = history[-4:] #keep only the 4 most recent data entries
                with open("history.json", "w") as f:
                    json.dump(history, f) #save the updated data back to history.json
                self.oled.display_kubios(timestamp, mean_hr_bpm, mean_ppi_ms, rmssd_ms, sdnn_ms, sns_index, pns_index)
            else:
                self.oled.display_message("Error") #if response for kubios is not valid            
        else:
            self.oled.display_message("Data not enough") #if stop befor 30s or less than 5 beats collected
    
    def stop_check(self): #check for btn press to stop sensor
        while self.option.menu.encoder.fifo.has_data():
            if self.option.menu.encoder.fifo.get() == 5:
                self.stop()
    
    def stop(self): #stop sensor, set sensor and option running state to false, stop ADC read, turn off LED
        self.led.off()
        self.timer.deinit()
        self.running = False

    

##################################### MAIN MENU/PROGRAM CLASSES #####################################



#class Menu to for user interaction, keep track of option, and init network connection
class Menu:
    def __init__(self):
        self.oled = OLED()
        self.encoder = Encoder()
        self.network = Network()
        self.network.connect_to_wlan() #connect to wifi
        self.kubios = Kubios() #init kubios here so it can be use in sensor class
        self.lines = ["1.MEASURE HR", "2.BASIC HRV", "3.KUBIOS", "4.HISTORY"] 
        self.left_arrow = "<"
        self.right_arrow = ">"
        self.arrow_pos = 0 #arrow position
        self.is_main_menu = True  # flag to track whether the main menu is being displayed
        self.size = 8
                
    def run(self):
        while True:
            if self.is_main_menu:
                self.oled.display_menu(self.lines, self.arrow_pos, self.left_arrow, self.right_arrow)
                while self.encoder.fifo.has_data():
                    v = self.encoder.fifo.get()
                    if not v == 5:
                        direction = v
                        self.arrow_pos = min(max(self.arrow_pos + (direction * self.size * 2), 0), self.size * 6)  # Adjust arrow position
                    elif v == 5:
                         self.select_option()
            else:
                while self.encoder.fifo.has_data():
                    if self.encoder.fifo.get() == 5: #go back to main menu when btn press
                        self.is_main_menu = True
    
    def select_option(self):
        option_index = self.arrow_pos // (self.size * 2)
        if option_index == 0: #MEASURE HR            
            Option1(self).start()
        elif option_index == 1: #BASIC HRV
            Option2(self).start()
        elif option_index == 2: #KUBIOS
            Option3(self).start()
        elif option_index == 3: #HISTORY
            Option4(self).start()
        self.is_main_menu = False #set is_main_menu flag to False => btn press then back to main menu


#class Option1: MEASURE HEART RATE 
class Option1:
    def __init__(self, menu):
        self.menu = menu
        self.oled = self.menu.oled
        self.encoder = self.menu.encoder
        self.sensor = Sensor(self)
        self.running = True
        self.lines = ["BASIC HRV", "KUBIOS", "EXIT"] 
        self.left_arrow = "<"
        self.right_arrow = ">"
        self.arrow_pos = 0 #arrow position
        self.is_option1_menu = False  # flag to track whether the main menu is being displayed
        self.size = 8
    
    def start(self):
        self.oled.display_message("Press to Start")
        btn_press_count = 0
        while self.running:
            while self.encoder.fifo.has_data():
                v = self.encoder.fifo.get()
                if v == 5:
                    btn_press_count += 1
                    if btn_press_count == 1:
                        self.sensor.start()
                        
                if self.is_option1_menu and btn_press_count > 1:
                        self.oled.display_menu(self.lines, self.arrow_pos, self.left_arrow, self.right_arrow)
                        if not btn_press_count > 2:
                            direction = v
                            self.arrow_pos = min(max(self.arrow_pos + (direction * self.size * 2), 0), self.size * 4)  #adjust arrow position
                        elif btn_press_count >2:
                            self.select_option()
        
    def select_option(self):
        option_index = self.arrow_pos // (self.size * 2)
        if option_index == 0: # Basic HRV
            self.sensor.HRV_display()
        elif option_index == 1: #Kubios
            if self.menu.network.wlan.isconnected():            
                self.sensor.Kubios_display()
            else:
                self.oled.display_message("No internet") #if no network then kubios wont run
        elif option_index == 2: #EXIT
            self.oled.display_message("Back to Menu")
        self.is_option1_menu = False 
        self.running = False
                    
                    
#class Option2: BASIC HRV to collect 30s data => Mqtt and display HRV
class Option2:
    def __init__(self, menu):
        self.menu = menu
        self.oled = self.menu.oled
        self.encoder = self.menu.encoder
        self.sensor = Sensor(self)
        self.running = True
        
    def start(self):
        self.oled.display_message("Press to start")
        while self.running: 
            while self.encoder.fifo.has_data():
                if self.encoder.fifo.get() == 5:
                    self.oled.display_message("Measuring....")
                    time.sleep(0.5)
                    self.sensor.start_op2()
            

#class Option3: KUBIOS to collect 30s data => Kubios and display analysis
class Option3:
    def __init__(self, menu):
        self.menu = menu
        self.oled = self.menu.oled
        self.encoder = self.menu.encoder
        self.sensor = Sensor(self)
        self.running = True
        
    def start(self):
        self.oled.display_message("Press to start")
        while self.running: 
            while self.encoder.fifo.has_data():
                if self.encoder.fifo.get() == 5:
                    self.oled.display_message("Collecting....")
                    time.sleep(0.5)
                    self.sensor.start_op3()


#class Option4: HISTORY for displaying measurement menu and displaying previous Kubios measurement    
class Option4:
    def __init__(self, menu):
        self.menu = menu
        self.oled = self.menu.oled
        self.encoder = self.menu.encoder
        self.running = True
        self.lines = ["MEASUREMENT 1", "MEASUREMENT 2", "MEASUREMENT 3", "MEASUREMENT 4"] 
        self.left_arrow = "<"
        self.right_arrow = ">"
        self.arrow_pos = 0 #arrow position
        self.is_history_menu = True  # flag to track whether the main menu is being displayed
        self.size = 8

    def display_history(self, index):
        with open("history.json", "r") as f:
            history = json.load(f)
            
        timestamp = history[index].get("timestamp")
        mean_hr = history[index].get("mean_hr_bpm")
        mean_ppi = history[index].get("mean_ppi_ms")
        rmssd = history[index].get("rmssd_ms")
        sdnn = history[index].get("sdnn_ms")
        sns = history[index].get("sns_index")
        pns = history[index].get("pns_index")
        self.oled.display_kubios(timestamp, mean_hr, mean_ppi, rmssd, sdnn, sns, pns)

    def start(self):
        while self.running:
            if self.is_history_menu:
                self.oled.display_menu(self.lines, self.arrow_pos, self.left_arrow, self.right_arrow)
                while self.encoder.fifo.has_data():
                    v = self.encoder.fifo.get()
                    if not v == 5:
                        direction = v
                        self.arrow_pos = min(max(self.arrow_pos + (direction * self.size * 2), 0), self.size * 6)  #adjust arrow position
                    elif v == 5:
                         self.select_option()
        
    def select_option(self):
        option_index = self.arrow_pos // (self.size * 2)
        if option_index == 0: #Measurement 1
            self.display_history(option_index)
        elif option_index == 1: #Measurement 2
            self.display_history(option_index)
        elif option_index == 2: #Measurement 3
            self.display_history(option_index)
        elif option_index == 3:
            self.display_history(option_index)
        self.is_history_menu = False 
        self.running = False




##################################### RUNNING LOOP #####################################
    
while True:
    Menu().run() #run main menu/program class