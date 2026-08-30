FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

# 1. Copiar requerimientos e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Instalar los binarios del navegador que coinciden exactamente con la versión instalada de Playwright
RUN playwright install --with-deps chromium

# 3. Copiar el resto del código
COPY . .

# 4. Crear carpetas de almacenamiento
RUN mkdir -p storage/pdfs storage/data

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]