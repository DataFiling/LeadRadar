# Use the official Microsoft Playwright image with Python and Browsers pre-installed
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set the working directory inside the container
WORKDIR /app

# Copy requirements and install
# Ensure your requirements.txt contains: fastapi, uvicorn, playwright
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Railway uses the PORT variable. We use a shell command to ensure it is picked up.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
