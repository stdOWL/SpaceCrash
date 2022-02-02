import enum
import math
import threading
import time

import redis
from GameState import GameState, State
from datetime import datetime
from pymongo import MongoClient
from DatabaseIO import DatabaseIO
from struct import *
import mysql.connector
import json
from queue import Queue
from WebsocketIO import WebsocketIO
from WSMessage import WSMessage
from Enums import Packets

CrashSpeed = 0.00006
OverWaitTime = 5


def getCurrentTime():
    return int(datetime.now().timestamp() * 1e3)


class GameStateHandler(threading.Thread):
    def __init__(self, config):
        super().__init__()
        self.running = True
        self.config = config

        self.tickTime = 0
        self.gameState = GameState(self, config)
        self.stream = WebsocketIO(self, config)
        self.redis_stream = DatabaseIO(self, config, self.stream)

        # t.daemon = True
        self.stream.start()
        self.redis_stream.start()
        self.sessionsFinishedSuccessfully = False

    def setRunning(self, _running):
        if not _running:
            self.sessionsFinishedSuccessfully = False
            print(f"[.] Current game state : {self.gameState.getState()}")
        self.running = _running


    def sendTick(self):

        elapsedTime = self.gameState.getElapsedTime()
        msg = WSMessage(Packets.TICK)
        msg.putInt32(elapsedTime)
        self.stream.sendAll(msg)

    def setCashout(self, betid):
        self.gameState.setCashout(betid)

    def sendStateToAll(self):
        msg = WSMessage(Packets.GAME_STATE)

        msg.put(len(str(self.gameState.sessionId)))
        msg.putString(str(self.gameState.sessionId))

        msg.put(self.gameState.getiState())
        msg.putInt32(self.gameState.getBettingEndTime())
        msg.putInt32(self.gameState.getRunningStartTime())

        if self.gameState.getState() == State.Over:
            gameHash = self.gameState.getHash()
            msg.put(len(gameHash))
            msg.putString(gameHash)
            msg.putInt32(int(self.gameState.getFinalMultiplier() * 100))
        self.stream.sendAll(msg)

    def checkState(self):
        self.gameState.keepConnectionsAlive()
        currentState = self.gameState.getState()
        if currentState == State.NotStarted:
            self.gameState.setState(State.TakingBets)
            self.gameState.saveRedis()
            self.gameState.updateDatabase()
            self.sendStateToAll()
        elif currentState == State.TakingBets:
            if self.gameState.getRunningStartTime() <= 0:
                self.gameState.setState(State.Running)
                self.sendStateToAll()
                self.gameState.saveRedis()
                self.gameState.updateDatabase()
                self.gameState.loadSessionBets()

        elif currentState == State.Running:
            # print("Running", self.gameState.getCurrentPoint(), self.gameState.getFinalMultiplier())
            if self.gameState.isBlowed():
                self.gameState.checkAutoCashout()
                self.gameState.runningOverTime = getCurrentTime()
                self.gameState.setState(State.Over)
                self.sendStateToAll()
                self.gameState.saveRedis()
                self.gameState.updateDatabase()
                self.gameState.insertHistory()

            elif getCurrentTime() - self.tickTime >= 100:
                self.gameState.checkAutoCashout()
                self.tickTime = getCurrentTime()
                self.sendTick()
                # self.gameState.save()

        elif currentState == State.Over:
            if getCurrentTime() - self.gameState.runningOverTime > self.config["game"]["OverSessionWaitTime"] * 1e3:
                if self.running == False and self.sessionsFinishedSuccessfully == False:
                    self.sessionsFinishedSuccessfully = True
                    print(f"[.] Current game state : Over")
                    return

                self.gameState.createNewGame()
                self.gameState.saveRedis()

    def run(self) -> None:
        self.gameState.createNewGame()
        while self.running or self.sessionsFinishedSuccessfully == False:
            self.checkState()
            time.sleep(0.01)

        print("[X] GameStateHandler killed!")
        self.redis_stream.setRunning(False)
        self.redis_stream.join()
        print("[X] DatabaseIO killed!")
        self.stream.setRunning(False)

        self.stream.join()
        print("[X] WebsocketIO killed!")
