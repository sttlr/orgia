FROM python:3.12-alpine
LABEL maintainer="sttlr"

RUN adduser -h /app -g app -D app

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt .

RUN chown -R app:app /app
USER app

ENTRYPOINT ["orgia"]
CMD ["--help"]
