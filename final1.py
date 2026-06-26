import customtkinter as ctk
import cv2
import numpy as np
import tensorflow as tf
from PIL import Image, ImageTk
import random
import json
import os
import serial            # comunicación con la Pico
from datetime import datetime

# Configuración inicial de apariencia
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SistemaEducativoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- CARGA DEL MODELO DE IA (Formato TFLite) ---
        print("Cargando modelo TFLite...")
        self.ruta_modelo = '/home/rpiuser/A_final/mejor_modelo_numeros.tflite'
        self.clases = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'Fondo']

        try:
            self.interpreter = tf.lite.Interpreter(model_path=self.ruta_modelo)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            print("Modelo TFLite cargado con éxito.")
        except Exception as e:
            print(f"ADVERTENCIA: No se encontró el modelo. Error: {e}")

        # --- CONEXIÓN CON LA PICO (por USB) ---
        self.pico = None
        try:
            self.pico = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
            print("Pico conectada en /dev/ttyACM0")
        except Exception as e:
            print(f"ADVERTENCIA: No se pudo conectar la Pico. Error: {e}")

        # Variables de cámara y lógica de juego
        self.camara_activa = False
        self.modo_actual = 0

        # --- CÁMARA vía bridge v4l2loopback (/dev/video17) ---
        self.picam2 = None
        try:
            self.picam2 = cv2.VideoCapture('/dev/video17', cv2.CAP_V4L2)
            if not self.picam2.isOpened():
                raise RuntimeError("No se pudo abrir /dev/video17")
            print("Cámara lista (bridge /dev/video17).")
        except Exception as e:
            print(f"ADVERTENCIA: No se pudo iniciar la cámara CSI. Error: {e}")
            self.picam2 = None

        # --- Optimización Visual ---
        self.frame_count = 0
        self.memoria_visual = []
        self.ultimo_numero_leido = ""

        # --- BASE DE DATOS PERMANENTE (JSON) ---
        self.archivo_bd = "registro_estudiantes.json"
        self.cargar_base_datos()
        self.nombre_estudiante = "Invitado"

        # Variables de sesión activa
        self.ejercicio_actual_str = ""
        self.respuesta_correcta = -1
        self.ejercicio_activo = False
        self.tiempo_restante = 0

        # Contadores en memoria
        self.aciertos = self.base_datos_estudiantes["Invitado"]["aciertos"]
        self.errores = self.base_datos_estudiantes["Invitado"]["errores"]
        self.puntaje = self.base_datos_estudiantes["Invitado"]["puntaje"]
        self.historial_ejercicios = self.base_datos_estudiantes["Invitado"]["historial"]

        self.fondo_tk = None
        self.obj_tk = None

        # Configuración de la ventana principal (PANTALLA COMPLETA)
        self.title("Sistema Educativo Inteligente - Final SE II")
        self.attributes("-fullscreen", True)
        self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))
        self.bind("<F11>", lambda e: self.attributes("-fullscreen", not self.attributes("-fullscreen")))
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ==================== MENÚ LATERAL ====================
        self.frame_menu = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.frame_menu.grid(row=0, column=0, sticky="nsew")
        self.frame_menu.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(self.frame_menu, text="Menú Principal", font=ctk.CTkFont(family="Comic Sans MS", size=23, weight="bold")).grid(row=0, column=0, padx=20, pady=20)
        ctk.CTkButton(self.frame_menu, text="📝 Registro", font=ctk.CTkFont(family="Comic Sans MS", size=17), command=self.mostrar_registro).grid(row=1, column=0, padx=20, pady=10)
        ctk.CTkButton(self.frame_menu, text="🖍️ Modo 1: Pizarra", font=ctk.CTkFont(family="Comic Sans MS", size=17), command=self.mostrar_modo1).grid(row=2, column=0, padx=20, pady=10)
        ctk.CTkButton(self.frame_menu, text="🐶 Modo 2: Conteo", font=ctk.CTkFont(family="Comic Sans MS", size=17), command=self.mostrar_modo2).grid(row=3, column=0, padx=20, pady=10)
        ctk.CTkButton(self.frame_menu, text="🏆 Ver Resultados", font=ctk.CTkFont(family="Comic Sans MS", size=17, weight="bold"), command=self.mostrar_resultados, fg_color="green").grid(row=4, column=0, padx=20, pady=10)
        ctk.CTkButton(self.frame_menu, text="❌ Salir", font=ctk.CTkFont(family="Comic Sans MS", size=15), command=self.destroy, fg_color="#d32f2f", hover_color="#b71c1c").grid(row=6, column=0, padx=20, pady=10)

        # ==================== VISTAS (FRAMES) ====================
        self.frame_registro = ctk.CTkFrame(self, corner_radius=10)
        self.frame_modo1 = ctk.CTkFrame(self, corner_radius=10)
        self.frame_modo2 = ctk.CTkFrame(self, corner_radius=10)
        self.frame_resultados = ctk.CTkFrame(self, corner_radius=10)

        self.crear_vistas()
        self.mostrar_registro()

        self.enviar_a_pico(f"IDLE:{self.puntaje}")

    def cargar_base_datos(self):
        if os.path.exists(self.archivo_bd):
            try:
                with open(self.archivo_bd, 'r', encoding='utf-8') as f:
                    self.base_datos_estudiantes = json.load(f)
            except Exception as e:
                print(f"Error al leer la base de datos: {e}")
                self.inicializar_bd_vacia()
        else:
            self.inicializar_bd_vacia()

    def inicializar_bd_vacia(self):
        self.base_datos_estudiantes = {"Invitado": {"aciertos": 0, "errores": 0, "puntaje": 0, "historial": []}}
        self.guardar_base_datos()

    def guardar_base_datos(self):
        try:
            with open(self.archivo_bd, 'w', encoding='utf-8') as f:
                json.dump(self.base_datos_estudiantes, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error al guardar la base de datos: {e}")

    # --- ENVÍO DE ÓRDENES A LA PICO ---
    def enviar_a_pico(self, comando):
        if self.pico is not None:
            try:
                self.pico.write((comando + "\n").encode())
            except Exception as e:
                print(f"Error enviando a Pico: {e}")

    # --- CREACIÓN DE LA INTERFAZ ---
    def crear_vistas(self):
        # --- Vista Registro ---
        ctk.CTkLabel(self.frame_registro, text="Registro de Estudiante", font=ctk.CTkFont(family="Comic Sans MS", size=31, weight="bold")).pack(pady=40)
        self.entry_nombre = ctk.CTkEntry(self.frame_registro, placeholder_text="Escribe tu nombre aquí", width=300, font=ctk.CTkFont(family="Comic Sans MS", size=21))
        self.entry_nombre.pack(pady=20)
        self.btn_registrar = ctk.CTkButton(self.frame_registro, text="Iniciar Sesión", command=self.registrar_estudiante, font=ctk.CTkFont(family="Comic Sans MS", size=21))
        self.btn_registrar.pack(pady=20)
        self.label_bienvenida = ctk.CTkLabel(self.frame_registro, text="", font=ctk.CTkFont(family="Comic Sans MS", size=23), text_color="green")
        self.label_bienvenida.pack(pady=20)

        # --- Vista Modo 1 (Pizarra) ---
        ctk.CTkLabel(self.frame_modo1, text="Modo 1: Análisis de Pizarra", font=ctk.CTkFont(family="Comic Sans MS", size=23, weight="bold")).pack(pady=5)
        self.frame_controles = ctk.CTkFrame(self.frame_modo1, fg_color="transparent")
        self.frame_controles.pack(pady=5)

        ctk.CTkLabel(self.frame_controles, text="Tiempo límite:", font=ctk.CTkFont(family="Comic Sans MS", size=17)).grid(row=0, column=0, padx=10)
        self.opcion_tiempo = ctk.CTkOptionMenu(self.frame_controles, values=["10 segundos", "15 segundos", "20 segundos", "30 segundos", "40 segundos"], font=ctk.CTkFont(family="Comic Sans MS", size=17), dropdown_font=ctk.CTkFont(family="Comic Sans MS", size=15))
        self.opcion_tiempo.set("15 segundos")
        self.opcion_tiempo.grid(row=0, column=1, padx=10)

        self.btn_generar = ctk.CTkButton(self.frame_controles, text="Generar Ejercicio", font=ctk.CTkFont(family="Comic Sans MS", size=17), command=self.generar_ejercicio, fg_color="blue")
        self.btn_generar.grid(row=0, column=2, padx=10)

        self.btn_salir_m1 = ctk.CTkButton(self.frame_controles, text="SALIR DEL JUEGO", font=ctk.CTkFont(family="Comic Sans MS", size=17, weight="bold"), command=self.salir_al_menu, fg_color="#d32f2f", hover_color="#b71c1c")
        self.btn_salir_m1.grid(row=0, column=3, padx=10)

        self.label_temporizador = ctk.CTkLabel(self.frame_modo1, text="Tiempo: --", font=ctk.CTkFont(family="Comic Sans MS", size=27, weight="bold"), text_color="orange")
        self.label_temporizador.pack(pady=5)
        self.label_ejercicio = ctk.CTkLabel(self.frame_modo1, text="Presiona 'Generar' para empezar", font=ctk.CTkFont(family="Comic Sans MS", size=39, weight="bold"), text_color="cyan")
        self.label_ejercicio.pack(pady=5)
        self.label_video = ctk.CTkLabel(self.frame_modo1, text="")
        self.label_video.pack(pady=5)
        self.label_resultado_ia = ctk.CTkLabel(self.frame_modo1, text="Esperando...", font=ctk.CTkFont(family="Comic Sans MS", size=27, weight="bold"), text_color="yellow")
        self.label_resultado_ia.pack(pady=5)

        # --- Vista Modo 2 (Conteo) ---
        ctk.CTkLabel(self.frame_modo2, text="Modo 2: Conteo en la Naturaleza", font=ctk.CTkFont(family="Comic Sans MS", size=27, weight="bold")).pack(pady=5)
        self.label_instruccion_m2 = ctk.CTkLabel(self.frame_modo2, text="Presiona 'Generar Escena' para empezar", font=ctk.CTkFont(family="Comic Sans MS", size=23), text_color="cyan")
        self.label_instruccion_m2.pack(pady=2)

        self.canvas_modo2 = ctk.CTkCanvas(self.frame_modo2, width=700, height=500, bg="#2b2b2b", highlightthickness=0)
        self.canvas_modo2.pack(pady=5)

        self.frame_controles_m2 = ctk.CTkFrame(self.frame_modo2, fg_color="transparent")
        self.frame_controles_m2.pack(pady=5)

        ctk.CTkLabel(self.frame_controles_m2, text="Nivel:", font=ctk.CTkFont(family="Comic Sans MS", size=17)).grid(row=0, column=0, padx=5)
        self.opcion_dificultad = ctk.CTkOptionMenu(self.frame_controles_m2, values=["Fácil (1-4)", "Medio (5-8)", "Difícil (8-15)"], font=ctk.CTkFont(family="Comic Sans MS", size=17), dropdown_font=ctk.CTkFont(family="Comic Sans MS", size=15))
        self.opcion_dificultad.set("Fácil (1-4)")
        self.opcion_dificultad.grid(row=0, column=1, padx=5)

        self.btn_generar_m2 = ctk.CTkButton(self.frame_controles_m2, text="Generar Escena", font=ctk.CTkFont(family="Comic Sans MS", size=17), command=self.generar_escena_modo2, fg_color="blue")
        self.btn_generar_m2.grid(row=0, column=2, padx=10)

        self.label_temporizador_m2 = ctk.CTkLabel(self.frame_controles_m2, text="Tiempo: --", font=ctk.CTkFont(family="Comic Sans MS", size=23, weight="bold"), text_color="orange")
        self.label_temporizador_m2.grid(row=0, column=3, padx=10)

        self.btn_salir_m2 = ctk.CTkButton(self.frame_controles_m2, text="SALIR DEL JUEGO", font=ctk.CTkFont(family="Comic Sans MS", size=17, weight="bold"), command=self.salir_al_menu, fg_color="#d32f2f", hover_color="#b71c1c")
        self.btn_salir_m2.grid(row=0, column=4, padx=10)

        self.label_resultado_ia_m2 = ctk.CTkLabel(self.frame_modo2, text="Esperando...", font=ctk.CTkFont(family="Comic Sans MS", size=23, weight="bold"), text_color="yellow")
        self.label_resultado_ia_m2.pack(pady=2)
        self.label_video_m2 = ctk.CTkLabel(self.frame_modo2, text="")
        self.label_video_m2.pack(pady=2)

        # --- Vista Resultados ---
        ctk.CTkLabel(self.frame_resultados, text="Panel de Estadísticas", font=ctk.CTkFont(family="Comic Sans MS", size=31, weight="bold")).pack(pady=20)
        self.frame_selector_res = ctk.CTkFrame(self.frame_resultados, fg_color="transparent")
        self.frame_selector_res.pack(pady=10)

        ctk.CTkLabel(self.frame_selector_res, text="Ver resultados de:", font=ctk.CTkFont(family="Comic Sans MS", size=19)).grid(row=0, column=0, padx=10)
        self.opcion_estudiante_res = ctk.CTkOptionMenu(self.frame_selector_res, values=list(self.base_datos_estudiantes.keys()), font=ctk.CTkFont(family="Comic Sans MS", size=17), dropdown_font=ctk.CTkFont(family="Comic Sans MS", size=15), command=self.cambiar_vista_resultados)
        self.opcion_estudiante_res.grid(row=0, column=1, padx=10)

        self.label_resumen = ctk.CTkLabel(self.frame_resultados, text="Aciertos: 0  |  Errores: 0  |  Puntaje: 0", font=ctk.CTkFont(family="Comic Sans MS", size=23, weight="bold"), text_color="cyan")
        self.label_resumen.pack(pady=10)

        self.textbox_historial = ctk.CTkTextbox(self.frame_resultados, width=700, height=400, font=ctk.CTkFont(family="Comic Sans MS", size=17))
        self.textbox_historial.pack(pady=10)
        self.textbox_historial.insert("0.0", "Aún no hay ejercicios registrados.\n")
        self.textbox_historial.configure(state="disabled")

    # --- LÓGICA DE REGISTRO Y NAVEGACIÓN ---
    def registrar_estudiante(self):
        nombre = self.entry_nombre.get().strip()
        if nombre != "":
            self.nombre_estudiante = nombre
            if nombre not in self.base_datos_estudiantes:
                self.base_datos_estudiantes[nombre] = {"aciertos": 0, "errores": 0, "puntaje": 0, "historial": []}
                self.guardar_base_datos()
                self.label_bienvenida.configure(text=f"¡Bienvenido/a al sistema, {nombre}!", text_color="green")
            else:
                self.label_bienvenida.configure(text=f"¡Qué bueno verte de nuevo, {nombre}! \nHistorial cargado.", text_color="cyan")

            datos = self.base_datos_estudiantes[nombre]
            self.aciertos = datos["aciertos"]
            self.errores = datos["errores"]
            self.puntaje = datos.get("puntaje", 0)
            self.historial_ejercicios = datos["historial"]
            nombres_actualizados = list(self.base_datos_estudiantes.keys())
            self.opcion_estudiante_res.configure(values=nombres_actualizados)
            self.opcion_estudiante_res.set(nombre)
            self.enviar_a_pico(f"IDLE:{self.puntaje}")
        else:
            self.label_bienvenida.configure(text="Por favor, escribe un nombre válido.", text_color="red")

    def apagar_camara(self):
        self.camara_activa = False
        self.modo_actual = 0

    def ocultar_todo(self):
        self.apagar_camara()
        self.frame_registro.grid_forget()
        self.frame_modo1.grid_forget()
        self.frame_modo2.grid_forget()
        self.frame_resultados.grid_forget()

    def salir_al_menu(self):
        self.ejercicio_activo = False
        self.tiempo_restante = 0
        self.ocultar_todo()
        self.mostrar_registro()
        self.enviar_a_pico(f"IDLE:{self.puntaje}")

    def mostrar_registro(self):
        self.ocultar_todo()
        self.frame_registro.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

    def mostrar_modo1(self):
        self.ocultar_todo()
        self.modo_actual = 1
        self.frame_modo1.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.camara_activa = True
        self.memoria_visual = []
        self.procesar_video()

    def mostrar_modo2(self):
        self.ocultar_todo()
        self.modo_actual = 2
        self.frame_modo2.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.camara_activa = True
        self.memoria_visual = []
        self.procesar_video()

    def mostrar_resultados(self):
        self.ocultar_todo()
        self.frame_resultados.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.cambiar_vista_resultados(self.opcion_estudiante_res.get())

    def cambiar_vista_resultados(self, nombre_seleccionado):
        datos = self.base_datos_estudiantes.get(nombre_seleccionado, {"aciertos": 0, "errores": 0, "puntaje": 0, "historial": []})
        puntaje_actual = datos.get("puntaje", 0)
        self.label_resumen.configure(text=f"Aciertos: {datos['aciertos']}   |   Errores: {datos['errores']}   |   PUNTAJE FINAL: {puntaje_actual}")
        self.textbox_historial.configure(state="normal")
        self.textbox_historial.delete("0.0", "end")
        if len(datos["historial"]) == 0:
            self.textbox_historial.insert("0.0", f"Aún no hay ejercicios resueltos para {nombre_seleccionado}.\n")
        else:
            for log in reversed(datos["historial"]):
                self.textbox_historial.insert("end", log + "\n")
        self.textbox_historial.configure(state="disabled")

    # --- LÓGICA DE JUEGOS ---
    def obtener_tiempo_seleccionado(self):
        return int(self.opcion_tiempo.get().split(" ")[0])

    def generar_ejercicio(self):
        if self.ejercicio_activo: return
        operacion = random.choice(['+', '-', '*', '/'])
        if operacion == '+':
            num1, num2 = random.randint(1, 9), random.randint(1, 9)
            self.respuesta_correcta = num1 + num2
            simbolo = '+'
        elif operacion == '-':
            num1, num2 = random.randint(1, 9), random.randint(1, 9)
            if num1 < num2: num1, num2 = num2, num1
            self.respuesta_correcta = num1 - num2
            simbolo = '-'
        elif operacion == '*':
            num1, num2 = random.randint(1, 9), random.randint(1, 9)
            self.respuesta_correcta = num1 * num2
            simbolo = 'x'
        elif operacion == '/':
            res_secreto, num2 = random.randint(1, 9), random.randint(1, 9)
            num1 = res_secreto * num2
            self.respuesta_correcta = res_secreto
            simbolo = '÷'

        self.ejercicio_actual_str = f"{num1} {simbolo} {num2}"
        self.label_ejercicio.configure(text=f"¿Cuánto es {self.ejercicio_actual_str} ?")
        self.label_resultado_ia.configure(text="¡Muestra tu respuesta a la cámara!", text_color="yellow")
        self.tiempo_restante = self.obtener_tiempo_seleccionado()
        self.ejercicio_activo = True
        self.actualizar_temporizador()

    def generar_escena_modo2(self):
        if self.ejercicio_activo: return
        carpeta_fondos = os.path.join("recursos", "fondos")
        carpeta_objetos = os.path.join("recursos", "objetos")
        try:
            fondos = [f for f in os.listdir(carpeta_fondos) if f.endswith(('.png', '.jpg'))]
            objetos = [f for f in os.listdir(carpeta_objetos) if f.endswith('.png')]
            if not fondos or not objetos:
                self.label_resultado_ia_m2.configure(text="Error: Faltan imágenes.", text_color="red")
                return

            fondo_elegido = random.choice(fondos)
            objeto_elegido = random.choice(objetos)
            ruta_fondo = os.path.join(carpeta_fondos, fondo_elegido)
            img_fondo = Image.open(ruta_fondo).resize((700, 500))
            self.fondo_tk = ImageTk.PhotoImage(img_fondo)
            self.canvas_modo2.delete("all")
            self.canvas_modo2.create_image(0, 0, image=self.fondo_tk, anchor="nw")

            dificultad = self.opcion_dificultad.get()
            if "Fácil" in dificultad:
                cantidad = random.randint(1, 4)
            elif "Medio" in dificultad:
                cantidad = random.randint(5, 8)
            else:
                cantidad = random.randint(8, 15)

            self.respuesta_correcta = cantidad
            nombre_animal = objeto_elegido.split('.')[0].upper()
            self.ejercicio_actual_str = f"Conteo de {cantidad} {nombre_animal}"

            ruta_objeto = os.path.join(carpeta_objetos, objeto_elegido)
            img_obj = Image.open(ruta_objeto).resize((100, 100))
            self.obj_tk = ImageTk.PhotoImage(img_obj)

            for _ in range(cantidad):
                x = random.randint(10, 590)
                y = random.randint(10, 390)
                self.canvas_modo2.create_image(x, y, image=self.obj_tk, anchor="nw")

            self.label_instruccion_m2.configure(text=f"¿Cuántos '{nombre_animal}' ves en la escena?")
            self.label_resultado_ia_m2.configure(text="¡Escribe el número y muéstralo a la cámara!", text_color="yellow")
            self.tiempo_restante = self.obtener_tiempo_seleccionado()
            self.ejercicio_activo = True
            self.actualizar_temporizador()
        except Exception as e:
            self.label_resultado_ia_m2.configure(text=f"Error al cargar imagen: {e}", text_color="red")

    def actualizar_temporizador(self):
        if not self.ejercicio_activo: return
        if self.tiempo_restante > 0:
            if self.modo_actual == 1:
                self.label_temporizador.configure(text=f"Tiempo: {self.tiempo_restante}s", text_color="orange")
            else:
                self.label_temporizador_m2.configure(text=f"Tiempo: {self.tiempo_restante}s", text_color="orange")
            self.tiempo_restante -= 1
            self.after(1000, self.actualizar_temporizador)
        else:
            if self.modo_actual == 1:
                self.label_temporizador.configure(text="Tiempo: 0s", text_color="red")
            else:
                self.label_temporizador_m2.configure(text="Tiempo: 0s", text_color="red")
            self.registrar_resultado(False, "Tiempo Agotado")

    def registrar_resultado(self, es_correcto, leido_por_ia=""):
        self.ejercicio_activo = False
        tiempo_inicial = self.obtener_tiempo_seleccionado()
        fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if es_correcto:
            self.aciertos += 1
            self.puntaje += 10
            tiempo_usado = tiempo_inicial - self.tiempo_restante
            texto_estado = f"¡CORRECTO! ({self.respuesta_correcta})"
            estado_txt = f"✅ Correcto (En {tiempo_usado}s) [+10 pts]"
            color = "green"
            self.enviar_a_pico(f"OK:{self.puntaje}")
        else:
            self.errores += 1
            self.puntaje = max(0, self.puntaje - 5)
            texto_estado = f"¡TIEMPO AGOTADO! La respuesta era {self.respuesta_correcta}"
            estado_txt = f"❌ Error (Leyó: {leido_por_ia}) [-5 pts]"
            color = "red"
            self.enviar_a_pico(f"FAIL:{self.puntaje}")

        if self.modo_actual == 1:
            self.label_resultado_ia.configure(text=texto_estado, text_color=color)
        elif self.modo_actual == 2:
            self.label_resultado_ia_m2.configure(text=texto_estado, text_color=color)

        registro = f"[{fecha_hora}] Reto: {self.ejercicio_actual_str} | Esperado: {self.respuesta_correcta} | {estado_txt}\n"
        self.historial_ejercicios.append(registro)
        self.base_datos_estudiantes[self.nombre_estudiante]["aciertos"] = self.aciertos
        self.base_datos_estudiantes[self.nombre_estudiante]["errores"] = self.errores
        self.base_datos_estudiantes[self.nombre_estudiante]["puntaje"] = self.puntaje
        self.base_datos_estudiantes[self.nombre_estudiante]["historial"] = self.historial_ejercicios
        self.guardar_base_datos()

    def preprocesar_numero(self, roi):
        h, w = roi.shape
        size = max(h, w) + 20
        lienzo = np.zeros((size, size), dtype=np.uint8)
        x_offset = (size - w) // 2
        y_offset = (size - h) // 2
        lienzo[y_offset:y_offset+h, x_offset:x_offset+w] = roi
        img_final = cv2.resize(lienzo, (48, 48))
        img_final = cv2.bitwise_not(img_final)
        return img_final

    # --- LÓGICA DE VISIÓN COMPUTACIONAL OPTIMIZADA (CON TFLITE) ---
    def procesar_video(self):
        if self.camara_activa and self.picam2 is not None:
            ret, frame = self.picam2.read()
            if ret and frame is not None:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frame_count += 1

                if self.frame_count % 3 == 0:
                    self.memoria_visual = []
                    numero_completo_temp = ""

                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
                    contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                    cajas = []
                    for c in contornos:
                        x, y, w, h = cv2.boundingRect(c)
                        if 30 < w < 400 and 60 < h < 400:
                            cajas.append((x, y, w, h))

                    cajas.sort(key=lambda b: b[0])

                    for (x, y, w, h) in cajas:
                        roi = thresh[y:y+h, x:x+w]
                        area_total = w * h
                        densidad = cv2.countNonZero(roi) / area_total

                        if 0.08 <= densidad <= 0.45:
                            img_procesada = self.preprocesar_numero(roi)
                            input_data = img_procesada.astype('float32') / 255.0
                            input_data = np.expand_dims(np.expand_dims(input_data, axis=0), axis=-1)

                            try:
                                self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
                                self.interpreter.invoke()
                                pred = self.interpreter.get_tensor(self.output_details[0]['index'])

                                clase = self.clases[np.argmax(pred)]
                                conf = np.max(pred) * 100

                                if conf > 70:
                                    numero_completo_temp += clase
                                    self.memoria_visual.append((x, y, w, h, clase, conf))
                            except Exception as e:
                                pass

                    self.ultimo_numero_leido = numero_completo_temp

                for (x, y, w, h, clase, conf) in self.memoria_visual:
                    cv2.rectangle(frame_rgb, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    cv2.putText(frame_rgb, f"{clase} ({conf:.0f}%)", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                if self.ejercicio_activo and self.ultimo_numero_leido != "":
                    try:
                        respuesta_nino = int(self.ultimo_numero_leido)
                        if respuesta_nino == self.respuesta_correcta:
                            tiempo_inicial = self.obtener_tiempo_seleccionado()
                            tiempo_tardado = tiempo_inicial - self.tiempo_restante
                            if self.modo_actual == 1:
                                self.label_temporizador.configure(text=f"¡Logrado en {tiempo_tardado} seg!", text_color="green")
                            else:
                                self.label_temporizador_m2.configure(text=f"¡Logrado en {tiempo_tardado} seg!", text_color="green")
                            self.registrar_resultado(True, self.ultimo_numero_leido)
                            self.ultimo_numero_leido = ""
                    except ValueError:
                        pass

                img_pil = Image.fromarray(frame_rgb)
                if self.modo_actual == 1:
                    img_ctk = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(640, 480))
                    self.label_video.configure(image=img_ctk)
                    self.label_video.image = img_ctk
                elif self.modo_actual == 2:
                    img_ctk = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(320, 240))
                    self.label_video_m2.configure(image=img_ctk)
                    self.label_video_m2.image = img_ctk

            self.after(15, self.procesar_video)

if __name__ == "__main__":
    app = SistemaEducativoApp()
    app.mainloop()