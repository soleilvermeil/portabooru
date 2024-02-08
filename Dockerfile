FROM python:3.11-alpine3.19
LABEL maintainer="SoleilVermeil"
ENV PYTHONUNBUFFERED=1
ENV RUNNING_IN_DOCKER=1

COPY ./requirements.txt /requirements.txt
RUN pip install -r requirements.txt

COPY ./app /app
WORKDIR /app

VOLUME /inputs
VOLUME /outputs

CMD python portabooru.py
