#!/usr/bin/python3
import os
import requests
import json
import settings
import argparse
import time

#delay after each API call per i2 request when set up in /5min cron.
delay = 1

parser = argparse.ArgumentParser()
parser.add_argument("--console","-c", help="Returns results to console even if filename set", dest='console', action='store_true')
parser.add_argument("--bearer","-b", help="Print Bearer Token and exit", dest='bearer', action='store_true')

args = parser.parse_args()
console = args.console
bearer  = args.bearer

#If settings.filename set to filename, use it, unless console set.
if hasattr(settings, 'filename'):
  filename = settings.filename
else:
  filename = ""

if console:
  delay = 0
  filename = ""

apikey = settings.apikey
server = settings.server

baseurl = "https://" + server

getrefresh  = '/v1/sessions/access'
getbearer   = '/v1/sessions/refresh'
getspaces   = '/v1/virtualnetworks/spaces'
getvrouters = '/v1/virtualnetworks/routers'
getl3conns  = '/v1/virtualnetworks/l3connections'
getcloud    = '/v1/footprint/cloudconnect'
getmyint    = '/v1/footprint/myinterfaces'

class APIAuth(requests.auth.AuthBase):
  def __init__(self, token):
    self.token = token
  def __call__(self, r):
    r.headers['x-api-key'] = self.token
    return r

# Use API ket to get a Refresh token
s = requests.post(baseurl + getrefresh, auth=APIAuth(apikey))

# Use Refresh token (in cookie) to get Bearer token
s = requests.get(baseurl + getbearer, cookies=s.cookies)
bearertoken = s.headers.get("authorization")
bearerheader = {"Authorization": bearertoken}

if bearer:
  print("BearerToken:" + bearertoken)
  exit(0)

# Get Internet2 Cloud Connection interface ids
s = requests.get(baseurl + getcloud, headers=bearerheader) 
cloudconnect = json.loads(s.content.decode("utf-8"))
time.sleep(delay)

# Get My Interface ids
s = requests.get(baseurl + getmyint, headers=bearerheader)
myinterfaces = json.loads(s.content.decode("utf-8"))
time.sleep(delay)

# Use Bearer token to get Spaces to find virtual routers
s = requests.get(baseurl + getspaces, headers=bearerheader)
spaces = json.loads(s.content.decode("utf-8"))
time.sleep(delay)

vrouterid = json.dumps(spaces['spaces'][0]['virtualRouterIds'][0])
vrouterid = vrouterid.replace('"','') 
#Print virtualrouterid
#print(vrouterid)

# Get vrouterid's l3connectionsids
s = requests.get(baseurl + getvrouters + '/' + vrouterid , headers=bearerheader)
vrouter = json.loads(s.content.decode("utf-8"))
time.sleep(delay)

l3connections = vrouter['virtualL3ConnectionIds']

#Print the dict of connections and their count
#print(l3connections)
#print(len(l3connections))

# Cycle through vrouter's l3connections to collect details
# Match up interface id with interface id from myinterfaces and cloudconnect
output = ""
bgpup  = 0
endpoint = 0
for l3connectionkeys in l3connections:
  s = requests.get(baseurl + getl3conns + '/' + l3connectionkeys , headers=bearerheader)
  details = json.loads(s.content.decode("utf-8"))
  time.sleep(delay)
  output += "Endpoint:" + str(endpoint) + "\n"
  if details['cloudConnectionType'] == "NONCLOUD":
    k = 0
    for myinterfacekeys in myinterfaces:
      if details['interfaceId'] == myinterfaces[k]['id']:
        output += "\t" + "Name: " + myinterfaces[k]['device']['name']
        if (len(myinterfaces[k]['device']['name']) < 10):
          output += "\t"
        output += " \t" + "Interface: " + myinterfaces[k]['name'] + "\n"
        output += "\t" + "RemoteName: " + details['remoteName'] + "\n"
      k += 1
  else:
    k = 0
    for cloudconnectkeys in cloudconnect:
      if details['interfaceId'] == cloudconnect[k]['id']:
        output += "\t" + "Name: " + cloudconnect[k]['device']['name']
        if (len(cloudconnect[k]['device']['name']) < 10):
          output += "\t"
        output += "\t" + "Interface: " + cloudconnect[k]['name'] + "\n"
        output += "\t" + "RemoteName: " + details['remoteName']
        if (len(details['remoteName']) < 8):
          output += "\t"
        output += " \t" + "Cloud: " + details['cloudConnectionType'] + "\n"
      k += 1
  output += "\t" + "BGP: " + details['bgpStatusIPv4'] + "\t\t"
  output += " \t" + "Local IP: " + details['localIPv4'] + "\n"
  output += "\t" + "Peer ASN: " + str(details['remoteASN']) + "\t"
  output += " \t" + "Remote IP: " + details['remoteIPv4'] + "\n"
  if details['maxBandwidth'] == 0:
    output += "\t" + "Bandwidth: Unrestricted\n"
  else:
    output += "\t" + "Bandwidth: " + str(details['maxBandwidth']) + " Mbits \n"

  if details['bgpStatusIPv4'] == "UP":
    bgpup += 1
  endpoint += 1
s.close()

#If filename is empty, due to being unset or due to console being true, then send to console
if filename == "":
  print("Space: " + spaces['spaces'][0]['title'] + " OESS ID: " + str(vrouter['oessNetworkId']))
  if len(l3connections) > bgpup:
    print(str(len(l3connections) - bgpup) + " of " + str(len(l3connections)) + " configured endpoints down!")
    print(output)
  else:
    print(str(bgpup) + " of " + str(len(l3connections)) + " connections up!")
    print(output)

#Else send to (filename)
else:
  if os.path.exists(filename):
    os.remove(filename)
  f = open(filename,"w")
  f.write("Space: " + spaces['spaces'][0]['title'] + " OESS ID: " + str(vrouter['oessNetworkId'] + "\n"))
  if len(l3connections) > bgpup:
    f.write(str(len(l3connections) - bgpup) + " of " + str(len(l3connections)) + " configured endpoints down!\n")
  else:
    f.write(str(bgpup) + " of " + str(len(l3connections)) + " connections up!\n")
  f.write(output)
  f.close()

