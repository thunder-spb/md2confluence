FROM python:3.13-alpine

WORKDIR /app

COPY requirements.txt md2confluence.py confluence.py /app

RUN python3 -m pip install --no-cache-dir -r requirements.txt

WORKDIR /docs

VOLUME /docs

CMD ["python3", "md2confluence.py"]
