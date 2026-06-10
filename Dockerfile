FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Initialize the trained machine learning configuration weights before booting the system
RUN python ML/train_model.py

EXPOSE 5000

ENV FLASK_APP=Backend/app.py
ENV FLASK_ENV=production

CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5000", "--timeout", "120", "Backend.app:app"]