FROM ubuntu:latest

WORKDIR /mypy

RUN apt-get update
RUN apt-get install -y python3 python3-pip clang

COPY mypy-requirements.txt .
COPY test-requirements.txt .
COPY build-requirements.txt .

RUN pip3 install -r test-requirements.txt
