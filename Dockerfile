# Use the slim version of Python 3.11 for faster builds and lower RAM usage
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first to leverage Docker cache (faster redeploys)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code
COPY . .

# In 2026, Railway ignores EXPOSE in favor of its own dynamic networking, 
# but keeping it as a reference doesn't hurt.
EXPOSE 8080

# CRITICAL: Use shell form (no brackets) to ensure $PORT is expanded.
# Railway injects $PORT at runtime. Defaulting to 8080 for local testing.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
