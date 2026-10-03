FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
# tkcalendar solo hace falta en la versión de escritorio
RUN grep -v tkcalendar requirements.txt > req-web.txt && pip install --no-cache-dir -r req-web.txt
COPY . .
ENV DENTAL_DATA_DIR=/data MPLBACKEND=Agg PORT=8000
VOLUME /data
EXPOSE 8000
CMD ["sh", "-c", "gunicorn -w 2 -k gthread --threads 4 -b 0.0.0.0:${PORT} web.app:app"]
