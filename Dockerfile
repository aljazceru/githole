# Use the official Node.js image as the base image
FROM node:latest

# install nginx repos 
RUN apt-get update && apt-get install curl gnupg2 ca-certificates lsb-release debian-archive-keyring -y
RUN curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor | tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null
RUN gpg --dry-run --quiet --no-keyring --import --import-options import-show /usr/share/keyrings/nginx-archive-keyring.gpg    
RUN echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] http://nginx.org/packages/debian `lsb_release -cs` nginx" | tee /etc/apt/sources.list.d/nginx.list
COPY docker/99nginx /etc/apt/preferences.d/99nginx
# install nginx
RUN apt-get update && apt-get install -y nginx git fcgiwrap spawn-fcgi nginx-module-njs
# install python3 and pip
#RUN apt-get install python3-requests python3-flask python3-pip gunicorn
RUN sed -i '1iload_module modules/ngx_http_js_module.so;' /etc/nginx/nginx.conf 
RUN sed -i '1iload_module modules/ngx_stream_js_module.so;' /etc/nginx/nginx.conf 
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx-hello-config /etc/nginx/sites-enabled/hello
COPY auth/http.js /etc/nginx/http.js

#RUN pip install --no-cache-dir jsonify --break-system-packages
ENV GIT_PEAR=/srv/repos/pear
EXPOSE 80
EXPOSE 8000
STOPSIGNAL SIGTERM


RUN mkdir -p /app/auth
WORKDIR /app/auth
#COPY auth/simple-auth.py .
#COPY auth/check.sh .

# Set the working directory inside the container
WORKDIR /app

# Clone the gitpear repository from GitHub
RUN git clone https://github.com/dzdidi/gitpear.git

# Change the working directory to the gitpear directory
WORKDIR /app/gitpear

# Install the dependencies using npm
RUN npm install

# Link the gitpear package globally
RUN npm link

RUN mkdir -p /srv/repos/pear
RUN chown -R www-data:www-data /srv/repos/

COPY docker/nginx-default-config /etc/nginx/sites-enabled/default

WORKDIR /app
COPY docker/entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/bin/bash", "-c", "/app/entrypoint.sh"]


