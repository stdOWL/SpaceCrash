import asyncio
import websockets
import threading
import time
import threading
import janus
from WSMessage import WSMessage
from Enums import Packets
from datetime import datetime


class WebsocketIO(threading.Thread):
    def __init__(self, gameStateHandler, config):
        super().__init__()

        self.clientsSetLock = threading.Lock()

        self.config = config
        self.CLIENTS = set()
        self.gameStateHandler = gameStateHandler
        self.queue = None
        self.running = True

    def setRunning(self, _running):
        self.running = _running
        if not _running:
            try:
                self.eventLoop.call_soon_threadsafe(self.start_server.ws_server.close)
                # self.eventLoop.call_soon_threadsafe(self.eventLoop.stop)
                # self.eventLoop.call_soon_threadsafe(self.eventLoop.close)

            except Exception as e:
                pass

    async def on_connection(self, websocket, path):
        with self.clientsSetLock:
            websocket.last_ping_time = datetime.now()
            self.CLIENTS.add(websocket)

        await self.sendVersion(websocket)
        try:
            async for msg in websocket:
                if msg[0] == 50:
                    await self.sendPong(websocket)
                    websocket.last_ping_time = datetime.now()

                # print("receive msg",msg)
        except Exception as e:
            print("Exception", e)
        finally:
            with self.clientsSetLock:
                self.CLIENTS.remove(websocket)

    async def sendVersion(self, websocket):
        try:
            msg = WSMessage(Packets.VERSION)
            msg.put(1)
            await websocket.send(bytes(msg.getBuffer()))
        except Exception as e:
            pass

    async def sendPong(self, websocket):
        try:
            msg = WSMessage(Packets.PING)
            await websocket.send(bytes(msg.getBuffer()))
        except Exception as e:
            pass

    async def sendAllSockets(self, msg):
        self.clientsSetLock.acquire()
        clients = self.CLIENTS.copy()
        self.clientsSetLock.release()

        for ws in clients:
            try:
                await ws.send(bytes(msg))
            except Exception as e:
                pass

    async def pingAll(self):
        msg = WSMessage(Packets.PING)
        pingBuff = bytes(msg.getBuffer())
        while self.running:
            await asyncio.sleep(2)
            self.clientsSetLock.acquire()
            clients = self.CLIENTS.copy()
            self.clientsSetLock.release()

            for ws in clients:
                try:
                    if (datetime.now() - ws.last_ping_time).seconds > 10:
                        await ws.close()
                    else:
                        await ws.send(pingBuff)
                except Exception as e:
                    print("[e] pingAll(WebsocketIO):", e)

        print("[r] pingAll(WebsocketIO) finished")

    async def check_mq(self):
        if self.queue is None:
            self.queue = janus.Queue()
        while self.running:
            # print("check mq")

            msg = await self.queue.async_q.get()
            await self.sendAllSockets(msg)
            self.queue.async_q.task_done()
        print("[r] check_mq(WebsocketIO) finished")

    def sendAll(self, msg):
        if self.queue:
            self.queue.sync_q.put(msg.getBuffer())

    def run(self):
        self.eventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.eventLoop)

        try:
            self.start_server = websockets.serve(self.on_connection, self.config['game']['ip'],
                                                 self.config['game']['port'])
            print(f"Websocket Listens : ws://{self.config['game']['ip']}:{self.config['game']['port']}")
            # self.eventLoop.run_until_complete(self.start_server)
            # self.eventLoop.run_until_complete(self.check_mq)
            # self.eventLoop.run_until_complete(self.pingAll)
            # self.eventLoop.run_forever()
            self.eventLoop.run_until_complete(asyncio.gather(
                self.start_server,
                self.check_mq(),
                self.pingAll()
            ))
            print("[d] WebsocketIO Event Loop Finished!")


        except Exception as e:
            pass
