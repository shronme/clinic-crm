FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/clinic_crm

# Set work directory
WORKDIR /clinic_crm

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY . .
RUN pip install --no-cache-dir -r requirements.txt


# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]