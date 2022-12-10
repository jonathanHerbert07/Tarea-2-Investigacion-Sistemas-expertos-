#!/usr/bin/env python3
#
# Copyright (c) 2019 LG Electronics, Inc.
#
# This software contains code licensed as described in LICENSE.
#

# This scenario recreates a situation described by an OpenScenario specification.
# In this situation, an NPC overtakes the EGO on the highway.
# For this scenario, the NPC uses the lane following system.
# This is because the distance traveled by the vehicles could vary and the NPC changes lanes at specific distances from the EGO.
# The scenario specification is available online from OpenScenario and is called "Overtaker"
# http://www.openscenario.org/download.html

# A command line argument is required when running this scenario to select the type of NPC vehicle to create.
# SIMULATOR_HOST and BRIDGE_HOST environment variables need to be set. The default for both is localhost.
# The scenario assumes that the EGO's destination is ahead in the same lane

import os
import lgsvl
import sys
import time
import math

if len(sys.argv) < 2:
    print("Insufficient arguments")
    sys.exit()

if sys.argv[1] not in ["Sedan", "SUV", "Jeep", "HatchBack", "SchoolBus", "DeliveryTruck"]:
    print("npc name not in list: Sedan , SUV , Jeep , HatchBack , SchoolBus , DeliveryTruck")
    sys.exit()

sim = lgsvl.Simulator(os.environ.get("SIMULATOR_HOST", "127.0.0.1"), 8181)
if sim.current_scene == "SanFrancisco":
    sim.reset()
else:
    sim.load("SanFrancisco")

# spawn EGO in the 2nd to right lane
egoState = lgsvl.AgentState()
# A point close to the desired lane was found in Editor. This method returns the position and orientation of the closest lane to the point.
egoState.transform = sim.map_point_on_lane(lgsvl.Vector(1699.6, 88.38, -601.9))
egoX = egoState.position.x
egoY = egoState.position.y
egoZ = egoState.position.z
egoOrient = egoState.rotation.y
ego = sim.add_agent("XE_Rigged-apollo_3_5", lgsvl.AgentType.EGO, egoState)

# enable sensors required for Apollo 3.5
sensors = ego.get_sensors()
for s in sensors:
    if s.name in ['velodyne', 'Main Camera', 'Telephoto Camera', 'GPS', 'IMU']:
        s.enabled = True

# spawn NPC 50m behind the EGO in the same lane
npcState = lgsvl.AgentState()
# NPC starts 50m behind the EGO
# The math functions in the Vector allow you to give a distance relative to the EGO (e.g. 50m behind the EGO) and get the appropriate world coordinate
npcState.transform = sim.map_point_on_lane(lgsvl.Vector(math.sin(math.radians(egoOrient))*-50+egoX, egoY, math.cos(math.radians(egoOrient))*-50+egoZ))
npc = sim.add_agent(sys.argv[1], lgsvl.AgentType.NPC, npcState)

print("Connecting to bridge")
# Wait for bridge to connect before running simulator
ego.connect_bridge(os.environ.get("BRIDGE_HOST", "127.0.0.1"), 9090)
while not ego.bridge_connected:
    time.sleep(1)
print("Bridge connected")

# EGO starts at 10m/s
egoState.velocity = lgsvl.Vector(math.sin(math.radians(egoOrient))*10, 0, math.cos(math.radians(egoOrient))*10)
ego.state = egoState

# Collect 1 second of data to initialize AD modules
sim.run(1)

npcState.velocity = lgsvl.Vector(math.sin(math.radians(npcState.rotation.y))*11.55, 0, math.cos(math.radians(npcState.rotation.y))*11.55)
npc.state = npcState

# NPC is specified to drive at 41.666 km/h which is 11.55m/s. The float here only sets the maximum speed for the NPC
npc.follow_closest_lane(True, 11.55, False) 

input("Press enter to run simulation")

laneChanged = False
egoControl = lgsvl.VehicleControl()
egoControl.braking = 0.2

while True:
    npcState = npc.state
    egoState = ego.state
    vehicleSeparationX = npcState.position.x - egoState.position.x
    vehicleSeparationY = npcState.position.y - egoState.position.y
    vehicleSeparationZ = npcState.position.z - egoState.position.z
    vehicleDistance = math.sqrt(vehicleSeparationX*vehicleSeparationX + vehicleSeparationY*vehicleSeparationY + vehicleSeparationZ*vehicleSeparationZ)
    # If the NPC is closer than 20m, is behind the EGO, and has not already changed lanes to the left
    if vehicleDistance <= 20 and vehicleSeparationX > 0 and laneChanged == False:
        laneChanged = True
        npc.change_lane(True)
    # If the NPC is further than 15m and is in front of the EGO
    if vehicleDistance >= 15 and vehicleSeparationX < 0:
        npc.change_lane(False)
        break # Scenario is over after the NPC changes lanes to the right

    if egoState.speed > 10: #EGO vehicle is specified to drive at 36.111 km/h which is 10m/s. Ideally this would be controlled by the AD stack
        ego.apply_control(egoControl, False)

    # Keep NPC traveling at 41.66 km/h
    npcState.velocity = lgsvl.Vector(math.sin(math.radians(npcState.rotation.y))*11.55, 0, math.cos(math.radians(npcState.rotation.y))*11.55)
    npc.state = npcState
    sim.run(0.5)

npcState.velocity = lgsvl.Vector(math.sin(math.radians(npcState.rotation.y))*11.55, 0, math.cos(math.radians(npcState.rotation.y))*11.55)
npc.state = npcState
# Allow the simulation to run for 10 more seconds
sim.run(10)