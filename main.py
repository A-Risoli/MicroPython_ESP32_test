import machine, time
from machine import Pin
import dht
import socket, select

from machine import Pin, I2C
import ssd1306
import network
import ssl
import gc
import json

gc.enable()
gc.threshold(9000)
sta_if = network.WLAN(network.STA_IF)

KEY_PATH = 'client.key'
CERT_PATH = 'client.crt'
WIFI_PATH = 'wifi.json'



with open(KEY_PATH, 'rb') as f:
    key = f.read()

with open(CERT_PATH, 'rb') as f:
    cert = f.read()

with open(WIFI_PATH, 'rb') as f:
    wifi_list = f.read()
    
wifi = json.loads(wifi_list)

def do_connect():  
    for item in wifi['list']:
        iteration = 5
        if not sta_if.isconnected():
            print('connecting to network: '+item['ssid'])
            sta_if.active(True)
            sta_if.connect(item['ssid'], item['psw'])
            while not sta_if.isconnected() and iteration > 0:
                iteration -=1
                time.sleep(1)
            if iteration == 0:
                sta_if.active(False)
                print("Not connected")
            else:
                print('network config:', sta_if.ifconfig())
    
class HCSR04:
    """
    Driver to use the untrasonic sensor HC-SR04.
    The sensor range is between 2cm and 4m.
    The timeouts received listening to echo pin are converted to OSError('Out of range')
    """
    # echo_timeout_us is based in chip range limit (400cm)
    def __init__(self, trigger_pin, echo_pin, echo_timeout_us=500*2*30):
        """
        trigger_pin: Output pin to send pulses
        echo_pin: Readonly pin to measure the distance. The pin should be protected with 1k resistor
        echo_timeout_us: Timeout in microseconds to listen to echo pin. 
        By default is based in sensor limit range (4m)
        """
        self.echo_timeout_us = echo_timeout_us
        # Init trigger pin (out)
        self.trigger = Pin(trigger_pin, mode=Pin.OUT, pull=None)
        self.trigger.value(0)

        # Init echo pin (in)
        self.echo = Pin(echo_pin, mode=Pin.IN, pull=None)

    def _send_pulse_and_wait(self):
        """
        Send the pulse to trigger and listen on echo pin.
        We use the method `machine.time_pulse_us()` to get the microseconds until the echo is received.
        """
        self.trigger.value(0) # Stabilize the sensor
        time.sleep_us(5)
        self.trigger.value(1)
        # Send a 10us pulse.
        time.sleep_us(10)
        self.trigger.value(0)
        try:
            pulse_time = machine.time_pulse_us(self.echo, 1, self.echo_timeout_us)
            return pulse_time
        except OSError as ex:
            if ex.args[0] == 110: # 110 = ETIMEDOUT
                raise OSError('Out of range')
            raise ex

    def distance_mm(self):
        """
        Get the distance in milimeters without floating point operations.
        """
        pulse_time = self._send_pulse_and_wait()

        # To calculate the distance we get the pulse_time and divide it by 2 
        # (the pulse walk the distance twice) and by 29.1 becasue
        # the sound speed on air (343.2 m/s), that It's equivalent to
        # 0.34320 mm/us that is 1mm each 2.91us
        # pulse_time // 2 // 2.91 -> pulse_time // 5.82 -> pulse_time * 100 // 582 
        mm = pulse_time * 100 // 582
        return mm

    def distance_cm(self):
        """
        Get the distance in centimeters with floating point operations.
        It returns a float
        """
        pulse_time = self._send_pulse_and_wait()

        # To calculate the distance we get the pulse_time and divide it by 2 
        # (the pulse walk the distance twice) and by 29.1 becasue
        # the sound speed on air (343.2 m/s), that It's equivalent to
        # 0.034320 cm/us that is 1cm each 29.1us
        cms = (pulse_time *10 ) / 582
        return cms



def displayTask() :
    
    do_connect()
    
    h = HCSR04(25,26)
    sensor = dht.DHT11(Pin(27))
    sensorP = Pin(14,Pin.IN)

    tr = False
    iteration = 0
    t=0
    u=0
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET,  socket.SO_REUSEADDR, 1)
    s.bind(('', 443))
    s.listen(5)
    last_t = 0
    last_u = 0
    
    ip = sta_if.ifconfig()[0].split('.')
    
    i = 0
    for x in ip :
        display.text(x+".", 0, i*8, 1)
        i+=1
    display.show()
        
    time.sleep(3)
    display.fill(0)
    
    while 1 :
    
    
        v = sensorP.value()

        sensor.measure()
        if v == 1 and tr is False:
            tr = True
            cm = h.distance_cm()
            sensor.measure()
            display.text('Moved !', 0, 22, 1)
            display.text("{:.1f}".format(cm)+ " cm", 0, 32, 1)
            display.show()
            #print("Hey Stop! you are at "+str(cm)+"cm ! "+str(sensor.temperature())+" °C "+str(sensor.humidity())+ " %")
        elif v == 1 and tr is True:
            cm = h.distance_cm()
            sensor.measure() 
            #print("                     "+str(cm)+"cm ! ")
        elif v == 0:
            tr = False
            display.text('              ', 0, 22, 1)
            display.text('              ', 0, 32, 1)
            display.show()
        
        
        t+=sensor.temperature()
        u+=sensor.humidity()
        if iteration+1 == max_iteration:
            last_t = t//max_iteration
            last_u = u//max_iteration
            display.fill(0)
            display.text('T '+str(last_t)+" C ",+ 0, 0, 1)
            display.text('H '+str(last_u)+ " %", 0, 10, 1)
            display.show()
            t=0
            u=0
        
        iteration +=1
        iteration %=max_iteration
        
        r, w, err = select.select((s,), (), (), 0)
        if r:
            for readable in r:
                try:
                    
                    conn, addr = s.accept()
                    scl = ssl.wrap_socket(conn, server_side=True, cert=cert, key=key)

                    print('Got a connection from %s' % str(addr))

                    scl.write('HTTP/1.1 200 OK\n')
                    scl.write('Content-Type: text/html\n')
                    scl.write('Connection: close\n\n')
                    
                    test = """
                    <html>
                        <head>
                            <title>Benvenuto</title>
                            <meta charset="UTF-8">
                        </head>
                        <body>
                            <h1><span style="color: #0000ff;">Hello! I'm the <span style="color: #ff0000;">ESP32</span> </span></h1>
                            <h1><span style="color: #0000ff;">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; with <span style="color: #ff0000;">MicroPython</span></span></h1>
                            <p>&nbsp;</p>
                            <p>&nbsp;</p>
                            <p>Currently we have :</p>
                            <ul>
                            <li><span style="color: #ff0000;">Temperature</span>&nbsp;&nbsp;&nbsp; :&nbsp;&nbsp; {0} &deg;C</li>
                            <li><span style="color: #808000;">Humidity</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp&nbsp; :&nbsp;&nbsp; {1}&nbsp; %</li>
                            </ul>
                            <p>&nbsp;</p>
                        </body>
                    </html>
                    """.format(last_t, last_u)
                    scl.write(test)
                    scl.close()
                    print(gc.mem_free())
                except Exception as e:
                    print(str(e))
  

# using default address 0x3C
i2c = I2C(sda=Pin(21), scl=Pin(22))
display = ssd1306.SSD1306_I2C(64, 48, i2c)
        
max_iteration = 30
display.fill(0)
displayTask()
