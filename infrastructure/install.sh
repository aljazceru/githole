#!/bin/bash
# install nginx from official repo
sudo apt install curl gnupg2 ca-certificates lsb-release ubuntu-keyring
gpg --dry-run --quiet --no-keyring --import --import-options import-show /usr/share/keyrings/nginx-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
echo -e "Package: *\nPin: origin nginx.org\nPin: release o=nginx\nPin-Priority: 900\n" \
    | sudo tee /etc/apt/preferences.d/99nginx
sudo apt update
sudo apt install nginx

# copy reserved names
sudo mkdir -p /var/lib/ghole
sudo cp reserved_names.txt /var/lib/ghole/reserved_names.txt
mkdir /etc/nginx/dynamic_routes/
cp nginx_template/ghole_main.conf /etc/nginx/sites-available/ghole_main.conf
ln -s /etc/nginx/sites-available/ghole_main.conf /etc/nginx/sites-enabled/ghole_main.conf
sudo systemctl restart nginx