# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import sys

import yaml
from BotHandler import BotHandler
import signal
import time
from Bot import Bot

BotHandlerThread: BotHandler = None


def signal_handler(sig, frame):
    global BotHandlerThread
    print("[X] Call SIGINT - Exiting!")
    print("[X] Please Wait Until Session Ends!")
    if BotHandlerThread:
        BotHandlerThread.setRunning(False)
        BotHandlerThread.join()
    print("[X] Done")
    sys.exit(0)


def main():
    global BotHandlerThread
    signal.signal(signal.SIGINT, signal_handler)
    with open('config.yaml', 'r') as configFile:
        config = yaml.safe_load(configFile)
        BotHandlerThread = BotHandler(config)
        BotHandlerThread.start()


        # GameStateHandlerThread.join()

    while True:
        time.sleep(1)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
