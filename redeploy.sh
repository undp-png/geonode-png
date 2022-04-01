#!/usr/bin/bash

# remove any static files created during backup
git stash && git pull

if [ "$MACHINE" = "development" ]; then
docker-compose restart geonode django
elif [ "$MACHINE" = "production" ]; then
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart geonode django
else
docker-compose restart geonode django
fi