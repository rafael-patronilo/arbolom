FROM python:alpine
RUN pip install clingo pandas natsort
WORKDIR /workspace
COPY . .