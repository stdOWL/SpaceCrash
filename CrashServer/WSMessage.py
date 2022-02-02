import struct


class WSMessage():
    def __init__(self, packetId):
        self.packetId = packetId
        self.array = [packetId]

    def put(self, n):
        self.array.append(n)

    def putInt16(self, n):
        n = int(n)
        self.array.append((n >> 8) & 0xff)
        self.array.append(n & 0xff)

    def putInt24(self, n):
        n = int(n)
        self.array.append((n >> 8) & 0xff)
        self.array.append(n & 0xff)

    def putInt32(self, n):
        n = int(n)
        self.array.append((n >> 24) & 0xff)
        self.array.append((n >> 16) & 0xff)
        self.array.append((n >> 8) & 0xff)
        self.array.append(n & 0xff)


    def putFloat(self, s):
        n = bytearray(struct.pack("f", float(s)))
        for x in n:
            self.array.append(x)
        if len(n) < 4:
            for i in range( 4 - len(n) ):
                self.array.append(0x00)



    def putString(self, s):
        length = len(s)
        for i in range(length):
            self.put(ord(s[i]))

    def getBuffer(self):
        return bytearray(self.array)
