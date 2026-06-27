#!/usr/bin/env python3
import usb.core, usb.util, sys, time, signal, binascii

def al(s, f):
    raise TimeoutError("ALRM")
signal.signal(signal.SIGALRM, al)

print("polling for 12E3...", flush=True)
d = None
for _ in range(200):
    d = usb.core.find(idVendor=0x1038, idProduct=0x12e3)
    if d is not None:
        break
    time.sleep(0.2)
if d is None:
    print("RESULT: 12E3 NOT FOUND", flush=True)
    sys.exit(1)
print("RESULT: FOUND 12E3", flush=True)
d.default_timeout = 5000

for cfg in d:
    for i in cfg:
        try:
            if d.is_kernel_driver_active(i.bInterfaceNumber):
                d.detach_kernel_driver(i.bInterfaceNumber)
                print("detached krnl drv iface %d" % i.bInterfaceNumber, flush=True)
        except:
            pass
try:
    usb.util.claim_interface(d, 0)
    print("claimed iface 0", flush=True)
except Exception as e:
    print("claim err: %r" % e, flush=True)

def sr(rt, rid, data):
    wv = (rt << 8) | rid
    try:
        signal.alarm(5)
        n = d.ctrl_transfer(0x21, 0x09, wv, 0, data, 3000)
        signal.alarm(0)
        print("  SET_REPORT(t=%d,id=%d): %d bytes" % (rt, rid, n), flush=True)
        return True
    except Exception as e:
        signal.alarm(0)
        print("  SET_REPORT err: %r" % e, flush=True)
        return False

def r81(t=2000):
    try:
        signal.alarm(max(3, t // 1000 + 1))
        r = d.read(0x81, 64, t)
        signal.alarm(0)
        b = bytes(r)
        print("  EP81: len=%d data=%s" % (len(b), b.hex()), flush=True)
        return b
    except Exception as e:
        signal.alarm(0)
        print("  EP81 err: %r" % e, flush=True)
        return None

def gr(rt, rid, ln=1024):
    wv = (rt << 8) | rid
    try:
        signal.alarm(5)
        r = d.ctrl_transfer(0xA1, 0x01, wv, 0, ln, 2000)
        signal.alarm(0)
        b = bytes(r)
        print("  GET_REPORT(t=%d,id=%d): len=%d %s" % (rt, rid, len(b), b.hex()[:128]), flush=True)
        return b
    except Exception as e:
        signal.alarm(0)
        print("  GET_REPORT err: %r" % e, flush=True)
        return None

def vi(req, ln=64):
    try:
        signal.alarm(5)
        r = d.ctrl_transfer(0xC0, req, 0, 0, ln, 2000)
        signal.alarm(0)
        b = bytes(r)
        print("  vendor_IN_0x%02x: len=%d %s" % (req, len(b), b.hex()), flush=True)
        return b
    except Exception as e:
        signal.alarm(0)
        print("  vendor_IN_0x%02x err: %r" % (req, e), flush=True)
        return None

print("\n=== Vendor request 0x00 ===", flush=True)
i0 = vi(0x00)
if i0:
    print("  nonzero: %s" % [hex(b) for b in i0 if b], flush=True)

print("\n=== Handshake 0xb006 (output) ===", flush=True)
hs = bytearray(64)
hs[0] = 0x06; hs[1] = 0xb0
sr(2, 6, hs)
time.sleep(0.1)
r81()

print("\n=== Handshake 0xb006 (feature) ===", flush=True)
sr(3, 6, hs)
time.sleep(0.1)
r81()

print("\n=== Flash packet 0xa106 size=0 (feature, NON-destructive) ===", flush=True)
pk = bytearray(1024)
pk[0] = 0x06; pk[1] = 0xa1
pk[8] = 0xff; pk[9] = 0xff; pk[10] = 0xff; pk[11] = 0xff
print("  header: %s" % bytes(pk[:12]).hex(), flush=True)
sr(3, 6, pk)
time.sleep(0.15)
r81()

print("\n=== GET_REPORT feature(6) ===", flush=True)
gr(3, 6, 1024)

print("\n=== Handshake via EP 0x01 OUT ===", flush=True)
try:
    signal.alarm(5)
    n = d.write(0x01, hs, 2000)
    signal.alarm(0)
    print("  EP01 write: %d" % n, flush=True)
    time.sleep(0.1)
    r81()
except Exception as e:
    signal.alarm(0)
    print("  EP01 err: %r" % e, flush=True)

print("\n=== DONE ===", flush=True)