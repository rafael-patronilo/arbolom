FROM python:3.13.8-slim
WORKDIR /workspace
COPY . .
RUN pip install .
