FROM python:3.13.3
RUN pip install clingo pandas natsort
WORKDIR /workspace
COPY . .