import json
import threading
import pika
import mysql.connector
from Enums import Packets
from WSMessage import WSMessage
import redis
from datetime import datetime
from pymongo import MongoClient


def getCurrentTime():
    return int(datetime.now().timestamp() * 1e3)


class DatabaseIO(threading.Thread):
    def __init__(self, gameStateHandler, config, wsStream):
        super().__init__()
        self.gameStateHandler = gameStateHandler
        self.wsStream = wsStream
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=config['rabbitmq']['host'],virtual_host=config['rabbitmq']['vhost'],credentials=pika.credentials.PlainCredentials(username=config['rabbitmq']['user'],password=config['rabbitmq']['password']), heartbeat=5))
        self.redisClient = redis.Redis(host=config['redis']['host'], port=config['redis']['port'], db=config['redis']['db'],
                                       password=config['redis']['password'],
                                       decode_responses=True)
        self.channel = self.connection.channel()
        self.channel2 = self.connection.channel()
        self.channel2.queue_declare('userNofiyQueue', durable=True)

        self.channel.queue_declare(queue='crash_order', durable=True)
        self.running = True

    def setRunning(self, _running):
        self.running = _running
        if not _running:
            try:
                self.channel.close()
                self.channel2.close()
            except Exception as e:
                pass


    def getCursor(self):
        try:
            self.mysqlClient.ping(reconnect=True, attempts=3, delay=5)
        except mysql.connector.Error as err:
            raise err
        return self.mysqlClient.cursor(dictionary=True)

    def sendBetPacket(self, betInfo):
        betMsg = WSMessage(Packets.BET)

        closedOut = 0

        if betInfo['status'] == 'CASHOUT':
            closedOut = 1

        betMsg.put(closedOut)  # closedOut
        betMsg.put(len(str(betInfo['userid'])))
        betMsg.putString(str(betInfo['userid']))

        self.redisClient.delete(f"cache:wallets:{betInfo['userid']}")
        self.channel2.basic_publish(exchange='',
                                    routing_key='userNofiyQueue',
                                    body=json.dumps({
                                        "type": "wallet",
                                        "userid": betInfo['userid']
                                    }))

        if closedOut == 0:
            betMsg.put(len(str(betInfo['id'])))
            betMsg.putString(str(betInfo['id']))

            betMsg.put(len(betInfo['balanceType']))
            betMsg.putString(betInfo['balanceType'])

            betMsg.put(len(betInfo['balanceName']))
            betMsg.putString(betInfo['balanceName'])

            betMsg.putFloat(betInfo["betAmount"])
            betMsg.putFloat(betInfo["betAmountUSD"])

            betMsg.put(0)  # incognito

            betMsg.put(len(betInfo['username']))
            betMsg.putString(betInfo['username'])
        else:
            betMsg.putInt32(int(float(betInfo['cashoutCrashPoint']) * 100))
            betMsg.putFloat(float(betInfo['payoutValue']))
            betMsg.putFloat(float(betInfo['payoutValueUSD']))

            self.gameStateHandler.setCashout(betInfo['id'])

        self.wsStream.sendAll(betMsg)

    def on_message(self, ch, method, properties, body):
        print(" [x] Received %r" % body.decode())
        betInfo = json.loads(body.decode())

        #   self.redisIOQueue.put([6,betInfo])
        self.sendBetPacket(betInfo)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(" [x] Done", betInfo)

    def run(self):
        try:
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(queue='crash_order', on_message_callback=self.on_message)
            self.channel.start_consuming()
        except Exception as e:
            print("Exception DatabaseIO",e)

