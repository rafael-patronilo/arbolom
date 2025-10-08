FROM python:3.13.8-slim
RUN pip install clingo pandas natsort
WORKDIR /workspace
COPY . .