# Red de Microcontroladores con MQTT
Laboratorio 1 de Tecnologías para la Automatización, implementación de una red de microcontroladores con protocolo MQTT. 

## MQTT

MQTT (Message Queuing Telemetry Transport) es un protocolo de mensajería ligero, orientado a eventos, diseñado para dispositivos con recursos limitados y redes inestables. Usa el modelo publicador–suscriptor sobre TCP/IP.

En qué consiste:

- Broker: servidor central que recibe y distribuye mensajes.
- Clientes: publican o se suscriben a "temas" (topics).
- QoS (Quality of Service): mecanismo que ofrece tres niveles distintos (0, 1, 2) para garantizar diferentes grados de entrega de mensajes.
    - El nivel 0 proporciona entrega "fire and forget" sin confirmación
    - El nivel 1 garantiza que el mensaje llegue al menos una vez con confirmación
    - El nivel 2 asegura que el mensaje se entregue exactamente una vez mediante handshake

Cómo funciona:

1. Un cliente se conecta al broker.
2. Publica mensajes en un topic, por ejemplo sensores/temperatura.
3. Otros clientes se suscriben a ese topic y reciben los mensajes en tiempo real.

## Implementación

### Arquitectura

<img width="1385" height="600" alt="image" src="https://github.com/user-attachments/assets/6393cfb8-26ec-4d1c-a862-dbf2e831f0b7" />

- **Sensores (12 microcontroladores Pico 2W)**: Cada uno publica sus datos (temperatura, humedad, movimiento, etc.) en un topic MQTT único:
    - `sensores/[nombre de equipo]/[magnitud que mide]`
    - `sensores/relay/temperatura`
- **Controlador Maestro (1 microcontrolador Pico 2W extra)**: Se suscribe a todos los sensores y centraliza la información en un solo topic (`/mediciones/`).
- **Broker MQTT**: Usamos un broker local, por lo que [instalamos mosquitto](https://mosquitto.org/download/) en nuestra PC. Mosquitto corre automaticamente en el puerto 1883, sin embargo, necesitamos dos brokers para implementar nuestra arquitectura, podemos crear otra instancia del servicio para que corra en el puerto 1884
    - Buscamos la ubicación donde instalamos mosquitto e identificamos el archivo generico de configuraciones mosquitto.conf. Tendremos que abrir este archivo como administrador par moder modificarlo. Hay que hacer una pequeña modificación, colocamos al principio las siguientes lineas:
        
        ```markdown
        listener 1883
        allow_anonymous true
        ```
        
        Luego guardamos, cambiamos su nombre a `mosquitto_a.conf` , lo clonamos y guardamos la copia como `mosquitto_b.conf` . Dentro de este otro archivo colocamos:
        
        ```markdown
        listener 1884
        allow_anonymous true
        ```
        
        Tenemos listo dos archivos de configuraciones para crear dos instancias del broker. 
        
        Para simplificar la ejecución de estas instancias recomiendo crear un archivo `mosquitto_run.bat` :
        
        ```markdown
        @echo off
        cd "C:\Program Files\mosquitto"
        
        start "" mosquitto -c "C:\Program Files\mosquitto\mosquitto_a.conf"
        start "" mosquitto -c "C:\Program Files\mosquitto\mosquitto_b.conf"
        
        exit
        ```
        
        Para verificar que efectivamente estan corriendo estas instancias ejecutamos en consola:
        
        ```markdown
        netstat -ano | findstr "1883 1884”
        ```
        
        Deberias ver que para ambos puertos el estado es “LISTENING”.
        
- **Node-RED (en la PC)**: Se conecta al broker MQTT, escucha el tema (`mediciones/#`) y muestra cada valor en gráficos, indicadores, contadores, etc. según corresponda.
    - Lo instalamos https://nodered.org/docs/getting-started/windows, y ejecutamos el comando `node-red` , luego podremos abrir el servidor donde esta corriendo.
    - Debemos instalar la extensión `@flowfuse/node-red-dashboard` para tener acceso a distintos tipos de graficos.

### Librerías

Vamos a necesitar incorporar librerías que no vienen por defecto. En https://circuitpython.org/libraries se puede descargar un zip con todas las librerías. Luego las copias en la carpeta `/lib` en el microcontrolador.

Las librerías son:

- `/lib/adafruit_minimqtt`: Copiar la carpeta completa.
- `/lib/adafruit_ticks.mpy`: Módulo que necesita minimqtt.
- `/lib/adafruit_connection_manager.mpy`: Módulo que necesita minimqtt.
- `/lib/adafruit_esp32spi_socketpool.mpy`: Módulo para conectarnos a la red.

### Descubrimiento automático de sensores

Cuando un sensor se conecta a la red, además de comenzar a publicar sus datos periódicamente, envía un mensaje de anuncio al tema especial `/descubrir/`.

El mensaje contiene la información mínima necesaria para que el maestro lo identifique, por ejemplo en formato JSON:

```json
{
  "equipo": "relay",
  "magnitudes": ["temperatura", "humedad"]
}

```

El maestro está suscripto al tema `/descubrir/`. Cada vez que se publica en el, lo interpreta como un sensor recientemente conectado y lo agrega a una lista de sensores conocidos. Luego, se suscribe dinámicamente al **tema** de ese sensor para empezar a recibir sus datos en tiempo real.

### Node-red

El maestro centraliza toda la información que recibe y la publica en el tema `/mediciones/#/#/` , a traves del puerto 1884.

Por ejemplo:

- `/mediciones/[equipo]/[magnitud]`
- `/mediciones/relay/temperatura`

> Notece que el maestro no publica en sensores sino en mediciones.
> 

De esta forma, Node-RED solo necesita escuchar `/mediciones/#` para recibir en tiempo real toda la información de la red de sensores.

### Configuración de los microcontroladores

```python
import time
import wifi
import socketpool
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# Configuración de RED
SSID = "Tu wifi"
PASSWORD = "Contraseña de tu wifi"
BROKER = "La IPv4 de la pc donde corre mosquitto. Win: ipconfig o Linux: ip addr"  
NOMBRE_EQUIPO = "relay"
DESCOVERY_TOPIC = "descubrir"
TOPIC = f"sensores/{NOMBRE_EQUIPO}"

print(f"Intentando conectar a {SSID}...")
try:
    wifi.radio.connect(SSID, PASSWORD)
    print(f"Conectado a {SSID}")
    print(f"Dirección IP: {wifi.radio.ipv4_address}")
except Exception as e:
    print(f"Error al conectar a WiFi: {e}")
    while True:
        pass 

# Configuración MQTT 
pool = socketpool.SocketPool(wifi.radio)

def connect(client, userdata, flags, rc):
    print("Conectado al broker MQTT")
    client.publish(DESCOVERY_TOPIC, json.dumps({"equipo":NOMBRE_EQUIPO,"magnitudes": ["temperatura", "humedad"]}))

mqtt_client = MQTT.MQTT(
    broker=BROKER,
    port=1883,
    socket_pool=pool
)

mqtt_client.on_connect = connect
mqtt_client.connect()

# Usamos estas varaibles globales para controlar cada cuanto publicamos
last_pub = 0
PUB_INTERVAL = 5  
def publish():
    global last_pub
    now = time.monotonic()
   
    if now - last_pub >= PUB_INTERVAL:
        try:
            temp_topic = f"{TOPIC}/[una_magnitud]" 
            mqtt_client.publish(temp_topic, str([var_de_una_magnitud]))
            
            hum_topic = f"{TOPIC}/[otra magnitud]" 
            mqtt_client.publish(hum_topic, str([var_de_otra_magnitud]))
            
            last_pub = now
          
        except Exception as e:
            print(f"Error publicando MQTT: {e}")

```
