from machine import Pin, SPI
from ili9341 import Display, color565
import time

# Pines según tu cableado
spi = SPI(0, baudrate=40_000_000, sck=Pin(18), mosi=Pin(19))
display = Display(spi, dc=Pin(15), cs=Pin(17), rst=Pin(14))

# Colores
NEGRO  = color565(0, 0, 0)
BLANCO = color565(255, 255, 255)
VERDE  = color565(0, 200, 0)
ROJO   = color565(220, 0, 0)

# Prueba
display.clear(NEGRO)
time.sleep(1)
display.fill_rectangle(0, 0, 240, 80, VERDE)
display.fill_rectangle(0, 80, 240, 80, BLANCO)
display.fill_rectangle(0, 160, 240, 80, ROJO)
print("Pantalla OK")