FROM python:3.7

RUN apt-get update \
  && apt-get install --yes --no-install-recommends \
  git \
  less \
  maven \
  moreutils \
  wget

ENV JAVA_HOME /usr/lib/jvm/default-java/
RUN mkdir /root/.gnupg \
 && chmod 600 /root/.gnupg

ADD requirements.txt /code/
RUN pip3 install -r /code/requirements.txt

ADD src/ /code/

ENTRYPOINT ["/usr/local/bin/python3", "/code/main.py"]
