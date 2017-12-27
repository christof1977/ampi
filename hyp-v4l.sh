#!/bin/bash

/usr/bin/hyperion-v4l2 -d /dev/video0 --input 0 -v PAL --width 240 --height 192 --frame-decimator 2 --size-decimator 4 --red-threshold 0.1 --green-threshold 0.1 --blue-threshold 0.1

