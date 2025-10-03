import json
import wifi
import socketpool
import adafruit_minimqtt.adafruit_minimqtt as MQTT

sensores_conocidos = {}

SSID = ""
PASSWORD = ""
BROKER = ""
PULL_TOPIC = "sensores"
PUSH_TOPIC = "mediciones"
DESCOVERY_TOPIC = "descubrir"

print(f"Intentando conectar a {SSID}...")
try:
    wifi.radio.connect(SSID, PASSWORD)
    print(f"Conectado a {SSID}")
    print(f"Dirección IP: {wifi.radio.ipv4_address}")
except Exception as e:
    print(f"Error al conectar a WiFi: {e}")
    while True:
        pass

pool = socketpool.SocketPool(wifi.radio)


# Conexión y funciones del broker de los sensores
def connect_sensors(client, userdata, flags, rc):
    print("Conectado al broker MQTT en puerto 1883")
    client.subscribe(DESCOVERY_TOPIC)


def subscribe(mqtt_client, userdata, topic, granted_qos):
    print(f"Maestro suscrito a {topic}")


def on_message_sensores(client, topic, msg):
    global sensores_conocidos

    if topic == DESCOVERY_TOPIC:
        try:
            data = json.loads(msg)
            equipo = data.get("equipo")
            magnitudes = data.get("magnitudes", [])

            if equipo not in sensores_conocidos:
                sensores_conocidos[equipo] = magnitudes
                print(
                    f"Nuevo equipo descubierto: {equipo}, magnitudes: {magnitudes}")

                for mag in magnitudes:
                    sensor_topic = f"{PULL_TOPIC}/{equipo}/{mag}"
                    client.subscribe(sensor_topic)
            else:
                pass

        except Exception as e:
            print(f"Error en descubrimiento: {e}")

    elif topic.startswith(PULL_TOPIC):
        try:
            partes = topic.split("/")
            if len(partes) == 3:
                _, equipo, magnitud = partes
                new_topic = f"{PUSH_TOPIC}/{equipo}/{magnitud}"
                print(f"Reenviando: {topic} -> {new_topic} | Valor: {msg}")
                client_nodeRed.publish(new_topic, msg)
        except Exception as e:
            print(f"Error reenviando medición: {e}")


client_sensors = MQTT.MQTT(
    broker=BROKER,
    port=1883,
    socket_pool=pool
)

client_sensors.on_connect = connect_sensors
client_sensors.on_subscribe = subscribe
client_sensors.on_message = on_message_sensores
client_sensors.connect()


# Conexión y funciones del broker de node-red
def connect_nodeRed(client, userdata, flags, rc):
    print("Conectado al broker MQTT en puerto 1884")


client_nodeRed = MQTT.MQTT(
    broker=BROKER,
    port=1884,
    socket_pool=pool
)

client_nodeRed.on_connect = connect_nodeRed

client_nodeRed.connect()

print("Maestro en ejecución...")
while True:
    client_sensors.loop()
