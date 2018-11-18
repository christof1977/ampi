#!/bin/bash

INST_PATH=/opt/ampi


rm -rf /etc/systemd/system/lircampi.service
rm -rf /etc/systemd/system/ampi.service

ln -s $INST_PATH/etc/systemd/lircampi.service /etc/systemd/system/lircampi.service
ln -s $INST_PATH/etc/systemd/ampi.service /etc/systemd/system/ampi.service

ln -sf $INST_PATH/etc/lirc/rm-ed031.conf /etc/lirc/lircd.conf
ln -sf $INST_PATH/etc/lirc/lircrc /etc/lirc/lircrc

systemctl enable lircampi.service
systemctl enable ampi.service
