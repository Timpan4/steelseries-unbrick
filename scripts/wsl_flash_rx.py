#!/usr/bin/env python3
"""Flash SteelSeries Arctis Nova Pro Wireless RX MCU firmware via 12E3 bootloader.
Protocol decoded from SSEdevice.dll FlashFirmwareArctisNovaProWirelessMCU:
  1. Handshake 0xb006 = [06, b0]  (PrepareDevice)
  2. Flash packet 0xa106 = [06, a1, addr(4 BE), size(2 BE), crc32(4 BE), data(<=1012)]
     CRC32 = zlib.crc32(data) (standard reflected, poly 0xedb88320, init 0xffffffff, final ~)
  3. Ack on EP 0x81: ack[0]==0x06 success
  4. Reset 0xbb06 = [06, bb]
Transport: SET_REPORT feature (report ID 6, 1024-byte buffer = 1 reportID + 1023 data)
"""
import usb.core, usb.util, sys, time, signal, zlib

FIRMWARE = "/mnt/c/Users/timpa/Desktop/steelseries_firmware_backup/272110306/firmware_arctis_nova_pro_wireless_rx_mcu_v1.22.11.hex"
CHUNK = 1012

def al(s, f):
    raise TimeoutError("ALRM")
signal.signal(signal.SIGALRM, al)

def parse_hex(path):
    segs = []
    ela = 0
    cur_a = None
    cur_d = bytearray()
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith(":"):
                continue
            raw = bytes.fromhex(line[1:])
            bc = raw[0]
            addr = (raw[1] << 8) | raw[2]
            rt = raw[3]
            data = raw[4:4+bc]
            if rt == 0x00:
                fa = (ela << 16) | addr
                if cur_a is not None and fa == cur_a + len(cur_d):
                    cur_d.extend(data)
                else:
                    if cur_d:
                        segs.append((cur_a, bytes(cur_d)))
                    cur_a = fa
                    cur_d = bytearray(data)
            elif rt == 0x01:
                break
            elif rt == 0x04:
                if cur_d:
                    segs.append((cur_a, bytes(cur_d)))
                    cur_d = bytearray()
                    cur_a = None
                ela = (data[0] << 8) | data[1]
            elif rt == 0x02:
                if cur_d:
                    segs.append((cur_a, bytes(cur_d)))
                    cur_d = bytearray()
                    cur_a = None
                ela = ((data[0] << 8) | data[1]) >> 4
    if cur_d:
        segs.append((cur_a, bytes(cur_d)))
    return segs

print("parsing firmware...", flush=True)
segs = parse_hex(FIRMWARE)
total = sum(len(d) for _, d in segs)
print("RESULT: %d segments, %d bytes total" % (len(segs), total), flush=True)
for i, (a, d) in enumerate(segs):
    print("  seg %d: addr=0x%06x len=%d" % (i, a, len(d)), flush=True)

total_chunks = sum((len(d) + CHUNK - 1) // CHUNK for _, d in segs)
print("total chunks: %d" % total_chunks, flush=True)

print("polling for 12E3...", flush=True)
dev = None
for _ in range(200):
    dev = usb.core.find(idVendor=0x1038, idProduct=0x12e3)
    if dev is not None:
        break
    time.sleep(0.2)
if dev is None:
    print("FAIL: 12E3 NOT FOUND", flush=True)
    sys.exit(1)
print("RESULT: FOUND 12E3", flush=True)
dev.default_timeout = 5000

for cfg in dev:
    for i in cfg:
        try:
            if dev.is_kernel_driver_active(i.bInterfaceNumber):
                dev.detach_kernel_driver(i.bInterfaceNumber)
        except:
            pass
try:
    usb.util.claim_interface(dev, 0)
    print("claimed iface 0", flush=True)
except Exception as e:
    print("FAIL: claim %r" % e, flush=True)
    sys.exit(1)

def send_feat(data):
    wv = (3 << 8) | 6
    try:
        signal.alarm(10)
        n = dev.ctrl_transfer(0x21, 0x09, wv, 0, data, 5000)
        signal.alarm(0)
        return True
    except Exception as e:
        signal.alarm(0)
        print("  SEND ERR: %r" % e, flush=True)
        return False

def read_ack(timeout=5000):
    try:
        signal.alarm(max(6, timeout // 1000 + 1))
        r = dev.read(0x81, 64, timeout)
        signal.alarm(0)
        return bytes(r)
    except Exception as e:
        signal.alarm(0)
        return None

# 1. Handshake
print("\n=== HANDSHAKE 0xb006 ===", flush=True)
hs = bytearray(64)
hs[0] = 0x06; hs[1] = 0xb0
if not send_feat(hs):
    print("FAIL: handshake send", flush=True); sys.exit(1)
time.sleep(0.1)
ack = read_ack()
if not ack or ack[0] != 0x06:
    print("FAIL: handshake ack=%s" % (ack.hex()[:16] if ack else "None"), flush=True)
    sys.exit(1)
print("handshake OK: %s" % ack.hex()[:16], flush=True)

# 2. Flash
print("\n=== FLASHING %d chunks ===" % total_chunks, flush=True)
written = 0
cn = 0
fail_count = 0
t0 = time.time()

for si, (base, data) in enumerate(segs):
    off = 0
    while off < len(data):
        size = min(CHUNK, len(data) - off)
        addr = base + off
        cdata = data[off:off+size]
        crc = zlib.crc32(cdata) & 0xffffffff

        pkt = bytearray(1024)
        pkt[0] = 0x06; pkt[1] = 0xa1
        pkt[2] = (addr >> 24) & 0xff
        pkt[3] = (addr >> 16) & 0xff
        pkt[4] = (addr >> 8) & 0xff
        pkt[5] = addr & 0xff
        pkt[6] = (size >> 8) & 0xff
        pkt[7] = size & 0xff
        pkt[8] = (crc >> 24) & 0xff
        pkt[9] = (crc >> 16) & 0xff
        pkt[10] = (crc >> 8) & 0xff
        pkt[11] = crc & 0xff
        pkt[12:12+size] = cdata

        ok = False
        for attempt in range(3):
            if not send_feat(pkt):
                continue
            ack = read_ack()
            if ack and ack[0] == 0x06:
                ok = True
                break
            elif ack:
                print("  retry %d chunk %d ack=%s" % (attempt+1, cn, ack.hex()[:16]), flush=True)
            time.sleep(0.05)

        if not ok:
            fail_count += 1
            print("FAIL: chunk %d/%d addr=0x%06x size=%d" % (cn, total_chunks, addr, size), flush=True)
            if ack:
                print("  ack=%s" % ack.hex()[:32], flush=True)
            print("ABORTING - sending reset", flush=True)
            rs = bytearray(64)
            rs[0] = 0x06; rs[1] = 0xbb
            send_feat(rs)
            time.sleep(0.2)
            read_ack()
            sys.exit(1)

        cn += 1
        written += size
        off += size
        if cn % 20 == 0 or cn == total_chunks:
            elapsed = time.time() - t0
            pct = written * 100 // total
            rate = written / elapsed if elapsed > 0 else 0
            eta = (total - written) / rate if rate > 0 else 0
            print("  %d/%d (%d%%) addr=0x%06x %d/%dB %.0fB/s ETA=%.0fs" %
                  (cn, total_chunks, pct, addr, written, total, rate, eta), flush=True)

# 3. Reset
print("\n=== RESET 0xbb06 ===", flush=True)
rs = bytearray(64)
rs[0] = 0x06; rs[1] = 0xbb
send_feat(rs)
time.sleep(0.2)
ack = read_ack()
print("reset ack: %s" % (ack.hex()[:16] if ack else "None"), flush=True)

elapsed = time.time() - t0
print("\n=== FLASH COMPLETE ===" , flush=True)
print("chunks: %d/%d  bytes: %d/%d  time: %.1fs  fails: %d" %
      (cn, total_chunks, written, total, elapsed, fail_count), flush=True)
