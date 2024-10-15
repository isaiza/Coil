import cv2
import mediapipe as mp
import math
import pyodbc
from datetime import datetime
import hashlib 

# Inicializar Mediapipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=False, model_complexity=1, enable_segmentation=False, min_detection_confidence=0.5)

# Inicializar el módulo de dibujo de Mediapipe
mp_drawing = mp.solutions.drawing_utils

# Función para calcular ángulos entre tres puntos
def calcular_angulo(p1, p2, p3):
    angulo = math.degrees(math.atan2(p3[1] - p2[1], p3[0] - p2[0]) - 
                          math.atan2(p1[1] - p2[1], p1[0] - p2[0]))
    angulo = abs(angulo)
    if angulo > 180:
        angulo = 360 - angulo
    return angulo

# Conectar a sql

def connect_db():
    try:
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=localhost;'
            'DATABASE=Usuarios;'
            'UID=BD_ISA;'
            'PWD=oracle'
        )
        return conn
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

# Encriptar contraseña
def encrypt_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Función para registrar un nuevo usuario
def register_user(username, password):
    conn = connect_db()
    if conn is None:
        return False

    cursor = conn.cursor()

    # Verificar si el usuario ya existe
    cursor.execute("SELECT * FROM usuarios WHERE Nombre_usuario = ?", (username,))
    if cursor.fetchone():
        print("El usuario ya existe. Intente iniciar sesion.")
        conn.close()
        return False

    # Insertar nuevo usuario
    cursor.execute("INSERT INTO usuarios (Nombre_usuario, Contrasena) VALUES (?, ?)", 
                   (username, encrypt_password(password)))
    conn.commit()
    conn.close()
    print("Usuario registrado exitosamente.")
    return True

# Función para loguear un usuario
def login_user(username, password):
    conn = connect_db()
    if conn is None:
        return False

    cursor = conn.cursor()

    # Verificar credenciales
    cursor.execute("SELECT * FROM usuarios WHERE Nombre_usuario = ? AND Contrasena = ?", 
                   (username, encrypt_password(password)))
    user = cursor.fetchone()

    if user:
        # Actualizar la fecha de conexion
        cursor.execute("UPDATE usuarios SET Fecha_conexion = ? WHERE id_usuario = ?", 
                       (datetime.now(), user[0]))
        conn.commit()
        conn.close()
        print("Login exitoso.")
        return True
    else:
        print("Credenciales incorrectas.")
        conn.close()
        return False

# Verificar si la base de datos esta vacia
def is_db_empty():
    conn = connect_db()
    if conn is None:
        return True

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    count = cursor.fetchone()[0]
    conn.close()
    
    return count == 0

# registro/login antes de iniciar la deteccion
def crear():
    conn = connect_db()
    if conn:
        print("La base de datos esta lista.")
        if is_db_empty():
            print("La base de datos esta vacia, procediendo a registrar el primer usuario.")
            username = input("Ingrese su nombre de usuario: ")
            password = input("Ingrese su contrasena: ")
            success = register_user(username, password)
            if not success:
                print("Error al registrar el usuario. Verifique los datos y intente nuevamente.")
                return 
        else:
            while True:
                action = input("Ya estas registrado (s/n): ").strip().lower()
                if action == 's':
                    username = input("Ingrese su nombre de usuario: ")
                    password = input("Ingrese su contrasena: ")
                    if login_user(username, password):
                        break
                    else:
                        print("No se pudo iniciar sesion. Intentelo nuevamente.")
                elif action == 'n':
                    username = input("Ingrese su nombre de usuario: ")
                    password = input("Ingrese su contrasena: ")
                    register_user(username, password)
                    break
                else:
                    print("utilice 's' o 'n'." "para responder")
    else:
        print("No se pudo establecer la conexion con la base de datos.")
        return 

crear()

# Capturar video desde la cámara
cap = cv2.VideoCapture(1)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("No se pudo capturar el frame.")
        break

    # Convertir el frame a RGB (porque Mediapipe trabaja con imágenes RGB)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Procesar la imagen para detectar los landmarks del cuerpo
    results = pose.process(frame_rgb)

    # Si se detectan landmarks, dibujar las conexiones del cuerpo
    if results.pose_landmarks:
        # Dibujar puntos clave y conexiones del cuerpo
        mp_drawing.draw_landmarks(
            frame, 
            results.pose_landmarks, 
            mp_pose.POSE_CONNECTIONS,
            mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),  # Puntos
            mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=2)   # Conexiones
        )

        # Obtener puntos clave del cuerpo (en coordenadas absolutas)
        landmarks = results.pose_landmarks.landmark
        alto, ancho, _ = frame.shape

        # Extraer coordenadas de hombros, caderas, y rodillas (lado izquierdo y derecho)
        hombro_izq = [int(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x * ancho), 
                      int(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y * alto)]
        cadera_izq = [int(landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x * ancho), 
                      int(landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y * alto)]
        rodilla_izq = [int(landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x * ancho), 
                       int(landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y * alto)]

        hombro_der = [int(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x * ancho), 
                      int(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y * alto)]
        cadera_der = [int(landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x * ancho), 
                      int(landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y * alto)]
        rodilla_der = [int(landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x * ancho), 
                       int(landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y * alto)]

        # Cálculo del ángulo en las rodillas (para agacharse)
        angulo_rodilla_izq = calcular_angulo(cadera_izq, rodilla_izq, [rodilla_izq[0], rodilla_izq[1] + 50])
        angulo_rodilla_der = calcular_angulo(cadera_der, rodilla_der, [rodilla_der[0], rodilla_der[1] + 50])

        # Cálculo del ángulo en los hombros (para levantar los brazos)
        angulo_brazo_izq = calcular_angulo(hombro_izq, cadera_izq, rodilla_izq)
        angulo_brazo_der = calcular_angulo(hombro_der, cadera_der, rodilla_der)

        # Mostrar recomendaciones para postura incorrecta
        if angulo_brazo_izq < 160 or angulo_brazo_der < 160:
            cv2.putText(frame, 'Levanta los brazos!', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        
        if angulo_rodilla_izq < 100 or angulo_rodilla_der < 100:
            cv2.putText(frame, 'Estas agachado!', (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

        # Dibujar líneas adicionales para mostrar la alineación del cuerpo
        cv2.line(frame, tuple(hombro_izq), tuple(cadera_izq), (255, 255, 0), 2)
        cv2.line(frame, tuple(cadera_izq), tuple(rodilla_izq), (255, 255, 0), 2)

        cv2.line(frame, tuple(hombro_der), tuple(cadera_der), (255, 255, 0), 2)
        cv2.line(frame, tuple(cadera_der), tuple(rodilla_der), (255, 255, 0), 2)

    # Mostrar el frame con los landmarks y recomendaciones
    cv2.imshow('Deteccion de Cuerpo Completo y Postura', frame)

    # Salir cuando se presione la tecla 'q'
    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

# Liberar la captura de video y cerrar las ventanas
cap.release()
cv2.destroyAllWindows()

