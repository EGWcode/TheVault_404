FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn 
COPY . . 
EXPOSE 5000
CMD ["gunicorn", "--pythonpath", "backend", "-b", "0.0.0.0:5000", "--worker-class", "gthread", "--threads", "4", "--timeout", "120","app:app"]

