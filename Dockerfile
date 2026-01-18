# Use the official Microsoft image which has all Linux dependencies pre-installed
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway uses the PORT variable
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
