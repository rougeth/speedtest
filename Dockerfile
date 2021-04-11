FROM ubuntu

ARG INSTALL_KEY=379CE192D401AB61
ARG DEB_DISTRO=bionic

RUN apt-get update \
	&& apt-get install -y gnupg1 apt-transport-https dirmngr \
	&& apt-key adv --keyserver keyserver.ubuntu.com --recv-keys $INSTALL_KEY \
	&& echo "deb https://ookla.bintray.com/debian ${DEB_DISTRO} main" | tee  /etc/apt/sources.list.d/speedtest.list \
	&& apt-get update \
	&& apt-get install -y speedtest python3-dev python3-pip

WORKDIR /usr/src/app
COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt
COPY speed.py .
ENTRYPOINT ["python3", "speed.py"]
