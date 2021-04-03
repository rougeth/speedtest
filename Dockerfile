FROM python:alpine
WORKDIR /usr/src/app
COPY . .
RUN
RUN pip install loguru schedule speedtest-cli
CMD python main.py
