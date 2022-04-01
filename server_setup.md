# Pre-deployment

## Install Dependencies

### Install Docker

```bash
 sudo apt-get update

 sudo apt-get install \
    ca-certificates \
    curl \
    gnupg \
    lsb-release
 curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo   "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose
```

### Install Node+Webhooks

```bash
 curl -fsSL https://deb.nodesource.com/setup_17.x | sudo -E bash -
 sudo apt-get install -y nodejs
 sudo apt-get install webhook
 sudo npm install pm2 -g 
 sudo npm install -g npm@8.3.0 
```


## Create swap file [Optional]
This is optional, but recommended for production.

Allocate swap space on the server.
```bash
sudo fallocate -l <24G: Size of swap file should be roughly 1.75 * availble RAM> /swapfile
sudo fallocate -l 24G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
sudo cp /etc/fstab /etc/fstab.bak
# add /swapfile swap swap defaults 0 0 to the file below
sudo vim /etc/fstab
```

## Install and setup app user

```bash
sudo useradd -m -s /bin/bash undp
sudo passwd undp

# Grant sudo
sudo usermod -aG sudo undp

# Grant docker permissions
sudo usermod -aG docker undp

# Grant other users group permissions
sudo usermod -aG undp cam
sudo usermod -aG undp john
sudo usermod -aG undp chol

# Create deploy key 
# https://docs.gitlab.com/ee/user/project/deploy_keys/index.html#project-deploy-keys
sudo su undp
ssh-keygen -t ed25519 -C "Deployment key for project"
eval "$(ssh-agent -s)"

vim ~/.ssh/config
# Add the following to ssh config
#Host gitlab.com
#  PreferredAuthentications publickey
#  IdentityFile ~/.ssh/id_ed25519

ssh-add ~/.ssh/id_ed25519

```

## Install application


```bash
# if not alr
sudo su undp
cd ~
git clone git@gitlab.com:mammoth-geospatial/undp_png.git
sudo mv undp_png /opt/
sudo chown -R undp:undp /opt/undp_png
```

## Create environment and launch docker

```bash
# copy .env file from staging to production
# and configure for new domain
vim .env 

docker-compose build
docker-compose up -d 
```

## Set up backups

Create a preload shell file for the cron job
```bash
cat > /home/undp/preload.sh << EOF
#!/bin/bash

. /etc/profile
. ~/.profile
. ~/.bashrc
EOF
chmod +x /home/undp/preload.sh
```

```bash
crontab -e 
0 0 * * 0  BASH_ENV=/home/undp/preload.sh "$(command -v bash)" -c "cd /opt/undp_png && docker exec  --env-file /opt/undp_png/.env -t django4undp_png bash -c 'SOURCE_URL=https://png-geoportal.org TARGET_URL=https://png-geoportal.org ./undp_png/br/backup.sh /backup_restore'" >> /home/undp/backup_undp.log 2>&1
0 1 * *  0 BASH_ENV=/home/undp/preload.sh && aws s3 sync /mnt/efs/fs1/backup_restore/ s3://undp-geonode-backups
```

TODO: install AWS and check on new backups location.