# Usamos una versión específica para estabilidad (puedes usar :latest si prefieres)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# 1. Instalar dependencias
# Se hace antes de copiar el código para aprovechar la caché de Docker
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copiar el código fuente
COPY . /app

# 3. Exponer el puerto (Documentación solamente, Cloud Run lo ignora pero es buena práctica)
EXPOSE 8080

# 4. Comando de arranque OPTIMIZADO
# - Usa 'exec' para que las señales de apagado (SIGTERM) lleguen a la app.
# - Escucha en 0.0.0.0 (OBLIGATORIO).
# - Usa la variable de entorno $PORT inyectada por Google, o 8080 por defecto.
# - 'app:app' busca el objeto 'app' dentro del archivo 'app.py'.
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers