FROM debian:bookworm-slim

# RUN mkdir -p /var/www/Locker
# RUN chown newuser /var/www/Locker
# USER newuser
WORKDIR /var/www/Locker

COPY requirements.txt .

COPY locker locker
COPY static static
COPY templates templates
COPY app.wsgi app.wsgi

ARG DOMAIN=locker.local
ENV DOMAIN=$DOMAIN

ENV TMP_DIR=/var/www/Locker/tmp
ENV REDIS_OM_URL=redis://@redis:6379

RUN mkdir tmp
RUN chown -R www-data:www-data tmp

RUN apt-get update && apt-get -y upgrade
RUN apt-get --yes install apache2 libapache2-mod-wsgi-py3 python3.11 python3-pip
RUN apt clean

RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

ARG PASSWORD
ENV PASSWORD=$PASSWORD
# RUN test -n ${PASSWORD}
# RUN python3 -c "import bcrypt; import os; print(bcrypt.hashpw('${PASSWORD}'.encode(), bcrypt.gensalt()).decode())" > .passwd

COPY Locker.conf /etc/apache2/sites-available/locker.conf

RUN a2enmod wsgi
RUN a2ensite locker
RUN a2dissite 000-default

RUN apachectl -k graceful

EXPOSE 80

CMD /usr/sbin/apache2ctl -D FOREGROUND