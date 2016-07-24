# httc

## install
you need the python CEC lib see https://github.com/Pulse-Eight/libcec for isntall intructions.
 
then simply

```
pip install httc
``` 

## usage
start the server

```
httc-server
```
by default it will run on port 3308 on all interfaces

try:

```
curl localhost:3308/ping
curl localhost:3308/devices
curl localhost:3308/0/power
curl -X POST localhost:3308/0/power
curl -X POST localhost:3308/0/activate
curl localhost:3308/buttons
curl -X POST localhost:3308/0/menu/press
curl -X POST localhost:3308/standby
```
