#!/bin/bash

git clone https://rigslab.com/Rambo/backup-api.git temp
cp -R temp/* .
rm -R -f temp
