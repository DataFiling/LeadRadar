# Use the slim version of Python 3.11 for faster builds and lower RAM usage
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy your requirements and main.py into the container
# By copying requirements first, Railway can cache your layers (faster redeploys)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code (your fused main.py)
COPY . .

# Railway uses port 8080 by default for many services
EXPOSE 8080

# The command to start your app
# We use 0.0.0.0 so it is accessible from the outside world
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
