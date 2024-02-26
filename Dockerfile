# Use the official Node.js image as the base image
FROM node:latest

# install nginx
RUN apt-get update && apt-get install -y nginx git fcgiwrap spawn-fcgi python3-requests python3-flask python3-pip gunicorn
RUN pip install --no-cache-dir jsonify --break-system-packages
ENV GIT_PEAR=/srv/repos/pear
EXPOSE 80
STOPSIGNAL SIGTERM


RUN mkdir -p /app/auth
WORKDIR /app/auth
COPY auth/simple-auth.py .
COPY auth/check.sh .

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


