# Use official Microsoft Playwright image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway uses the PORT variable; CMD ensures it's passed to Uvicorn
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
