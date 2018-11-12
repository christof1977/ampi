#!/bin/bash

rm -rf /etc/systemd/system/lircampi.service
rm -rf /etc/systemd/system/ampi.service

ln -s /opt/ampi/systemd/lircampi.service /etc/systemd/system/lircampi.service
ln -s /opt/ampi/systemd/ampi.service /etc/systemd/system/ampi.service

systemctl enable lircampi.service
systemctl enable ampi.service
