FROM python:3.7-alpine

RUN mkdir -p /opt/certificate-expiry-checker

WORKDIR /opt/certificate-expiry-checker

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY requirements.txt .
COPY src/ src/
COPY test/ test/

ENV PYTHONPATH "${PYTHONPATH}:/opt/certificate-expiry-checker/src"

RUN apk update && apk add gcc libc-dev make git libffi-dev openssl-dev python3-dev libxml2-dev libxslt-dev 
RUN pip3 install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt \
    && python -m unittest

EXPOSE 8000

ENTRYPOINT ["gunicorn", "-b", "0.0.0.0:8000", "--chdir", "src", "main:app", "--timeout", "300", "--log-level", "info"]