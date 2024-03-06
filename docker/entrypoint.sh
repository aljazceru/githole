#!/bin/bash
# if $1 includes an url
# docker run -it -p 80:80 -e REPO_NAME="https://github.com/aljazceru/confidential-dvm" -e USER_NPUB="npub1jvymsvx0eqj03xmnalkzhancgjdujufsyefr4s28vv5crf88l4esunk6mw" ghole
exec > >(tee -a "/tmp/deployment.log") 2>&1

export GIT_PEAR=/srv/repos/pear 
export GIT_PEAR_AUTH="nip98"
export GIT_PEAR_AUTH_NSEC=$USER_NSEC
git pear daemon -s 
# if $1 exists
 if [ -n "$1" ]; then
     REPO_NAME=$1
fi

if [[ $REPO_NAME =~ ^https.* ]]; then
# # FIXME: path seem to be wrong here
   ORIGINAL_NAME=$(basename $REPO_NAME .git)
   mkdir -p /srv/repos/"$ORIGINAL_NAME"
   git clone $REPO_NAME /srv/repos/"$ORIGINAL_NAME"
   cd /srv/repos/"$ORIGINAL_NAME"
   git pear init .
   git pear share . public
   git pear acl -u add $USER_NPUB:admin
 # enter pear repo and expose http
   cd /srv/repos/pear/"$ORIGINAL_NAME"/

   echo "[http]" >> config
   echo "	receivepack = true" >> config
 fi


 if [[ ! $REPO_NAME =~ ^https.* ]]; then
   mkdir -p /srv/repos/"$REPO_NAME"
   cd /srv/repos/"$REPO_NAME"
   git pear init .
   git pear share . public
   git pear acl add $USER_NPUB:admin
   # enter pear repo and expose http
   cd /srv/repos/pear/"$REPO_NAME"/
   echo "[http]" >> config
   echo "	receivepack = true" >> config
   cd /srv/repos/pear/
   ln -s ./"$REPO_NAME"/.git-daemon-export-ok ./
  git config --bool core.bare true
fi
chown -R www-data:www-data /srv/repos/
PEAR_KEY=$(git pear key)
PEAR_REPO=$(git pear list -s)
PEAR_SEED=$(xxd /srv/repos/pear/.seed)
# send pear key, pear_repo and pear_seed to frontend http://localhost/user_notification
curl -X POST -H "Content-Type: application/json" \
  -d '{"pear_key":"'"$PEAR_KEY"'", "pear_repo":"'"$PEAR_REPO"'", "pear_seed":"'"$PEAR_SEED"'", "repo_name":"'"$REPO_NAME"'", "user_npub":"'"$USER_NPUB"'"}' \
     https://ghole.xyz/user_notification
echo "REPO_NAME: $REPO_NAME" >> /tmp/debug.log
echo "ORIGINAL_NAME: $ORIGINAL_NAME" >> /tmp/debug.log
echo "GIT_PEAR: $GIT_PEAR" >> /tmp/debug.log
echo "PEAR_KEY: $PEAR_KEY" >> /tmp/debug.log
echo "PEAR_REPO: $PEAR_REPO" >> /tmp/debug.log

/etc/init.d/fcgiwrap start
nohup node /app/auth/index.js >> /tmp/auth.log &

chmod 766 /var/run/fcgiwrap.socket
nginx -g "daemon off;"
