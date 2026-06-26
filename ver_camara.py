import cv2

cap = cv2.VideoCapture('/dev/video17')

if not cap.isOpened():
    print("ERROR: no se pudo abrir /dev/video17")
    exit(1)

print("Presiona 'q' para cerrar")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Fallo al leer frame")
        break
    cv2.imshow('Camara - q para salir', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()