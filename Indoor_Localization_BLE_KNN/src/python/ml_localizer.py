import serial
import serial.tools.list_ports
import threading
import time
import csv
import os

from sklearn.neighbors import KNeighborsClassifier

# ============================================================
# TRAINING DATA
# ============================================================

data_A = [
    -52,-51,-53,-50,-52,-54,-51,-53,-52,-50,
    -75,-76,-74,-77,-75,-73,-76,-74,-75,-76,
    -63,-64,-62,-65,-63,-61,-64,-62,-63,-64
]

data_B = [
    -76,-75,-77,-74,-76,-78,-75,-77,-76,-74,
    -51,-52,-50,-53,-51,-49,-52,-50,-51,-52,
    -62,-63,-61,-64,-62,-60,-63,-61,-62,-63
]

labels = (
    ["Room101"] * 10 +
    ["Room102"] * 10 +
    ["Corridor"] * 10
)

X = list(zip(data_A, data_B))
y = labels

# ============================================================
# KNN MODEL
# ============================================================

knn = KNeighborsClassifier(n_neighbors=3, metric="euclidean")
knn.fit(X, y)
print("✅ KNN Model Loaded")

# ============================================================
# CSV LOGGER
# ============================================================

LOG_FILE = "localization_log.csv"

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "RSSI_A", "RSSI_B", "Prediction", "Confidence"])

# ============================================================
# MAP POSITIONS
# ============================================================

MAP_POSITIONS = {
    "Room101":  {"left": "10%", "top": "28%"},
    "Room102":  {"left": "31%", "top": "28%"},
    "Corridor": {"left": "44%", "top": "50%"}
}

# ============================================================
# SHARED DASHBOARD DATA — starts in DISCONNECTED state
# ============================================================

latest_data = {
    "beaconA":        None,
    "beaconB":        None,
    "location":       "UNKNOWN",
    "confidence":     0,
    "connection":     "DISCONNECTED",
    "system_state":   "DISCONNECTED",
    "beaconA_status": "LOST",
    "beaconB_status": "LOST",
    "accuracy_label": "No Signal",
    "map_position":   {"left": "44%", "top": "50%"},
    "timestamp":      0,
    "error_message":  "No ESP32 detected. Please connect the device."
}

# ============================================================
# LOCK for thread-safe writes
# ============================================================

data_lock = threading.Lock()

# ============================================================
# HELPER — auto-detect ESP32 COM port
# ============================================================

ESP32_KEYWORDS = [
    "cp210", "ch340", "ch341", "ch343", "htw",
    "uart", "usb serial", "usb-serial", "esp32",
    "silicon labs", "wch"
]

def find_esp32_port():
    """Scan all COM ports and return the one most likely to be ESP32."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = (port.description or "").lower()
        mfr  = (port.manufacturer or "").lower()
        combined = desc + " " + mfr
        if any(kw in combined for kw in ESP32_KEYWORDS):
            print(f"🔍 Auto-detected ESP32 on {port.device} — {port.description}")
            return port.device
    # fallback: if only one port exists, try it
    if len(ports) == 1:
        print(f"🔍 Single port found, trying {ports[0].device}")
        return ports[0].device
    return None

# ============================================================
# HELPER — signal status
# ============================================================

def signal_status(rssi):
    if rssi is None or rssi <= -90: return "LOST"
    elif rssi <= -75: return "WEAK"
    elif rssi <= -65: return "MEDIUM"
    return "STRONG"

# ============================================================
# HELPER — CSV logger
# ============================================================

def log_data(rssi_a, rssi_b, prediction, confidence):
    try:
        with open(LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                time.strftime("%Y-%m-%d %H:%M:%S"),
                rssi_a, rssi_b, prediction, confidence
            ])
    except Exception as e:
        print(f"⚠ Log write error: {e}")

# ============================================================
# HELPER — reset to disconnected state
# ============================================================

def set_disconnected(reason="ESP32 disconnected"):
    with data_lock:
        latest_data.update({
            "beaconA":        None,
            "beaconB":        None,
            "location":       "UNKNOWN",
            "confidence":     0,
            "connection":     "DISCONNECTED",
            "system_state":   "DISCONNECTED",
            "beaconA_status": "LOST",
            "beaconB_status": "LOST",
            "accuracy_label": "No Signal",
            "map_position":   {"left": "44%", "top": "50%"},
            "timestamp":      round(time.time() * 1000),
            "error_message":  reason
        })

# ============================================================
# SERIAL READER THREAD
# ============================================================

BAUD_RATE    = 115200
RETRY_DELAY  = 3      # seconds between reconnect attempts
READ_TIMEOUT = 5      # serial read timeout

def serial_reader():
    while True:
        # ── Discover port ──────────────────────────────────
        port = find_esp32_port()

        if port is None:
            set_disconnected("No ESP32 detected. Please connect the device.")
            print(f"⏳ No ESP32 found. Retrying in {RETRY_DELAY}s…")
            time.sleep(RETRY_DELAY)
            continue

        # ── Try connecting ─────────────────────────────────
        try:
            print(f"🔌 Connecting to {port} at {BAUD_RATE} baud…")
            ser = serial.Serial(port, BAUD_RATE, timeout=READ_TIMEOUT)
            time.sleep(2)   # let ESP32 boot / settle

            print(f"✅ ESP32 Connected on {port}")
            with data_lock:
                latest_data["connection"]   = "ONLINE"
                latest_data["system_state"] = "WAITING"
                latest_data["error_message"] = ""

            consecutive_empty = 0

            # ── Read loop ──────────────────────────────────
            while True:
                try:
                    raw = ser.readline()
                except Exception:
                    raise   # bubble up to outer except

                line = raw.decode("utf-8", errors="ignore").strip()

                # ── Detect silence / timeout ───────────────
                if not line:
                    consecutive_empty += 1
                    if consecutive_empty >= 10:
                        # No data for ~10 read-timeouts → treat as IDLE
                        with data_lock:
                            latest_data["connection"]   = "IDLE"
                            latest_data["system_state"] = "IDLE"
                    continue
                else:
                    consecutive_empty = 0

                if not line.startswith("CSV:"):
                    continue

                # ── Parse CSV line ─────────────────────────
                try:
                    values = line.replace("CSV:", "").split(",")
                    rssi_a = int(values[0])
                    rssi_b = int(values[1])
                except Exception:
                    continue

                # ── KNN Predict ───────────────────────────
                prediction   = knn.predict([[rssi_a, rssi_b]])[0]
                probabilities = knn.predict_proba([[rssi_a, rssi_b]])[0]
                confidence   = round(max(probabilities) * 100, 1)

                log_data(rssi_a, rssi_b, prediction, confidence)

                # ── Update shared data ────────────────────
                with data_lock:
                    latest_data.update({
                        "beaconA":        rssi_a,
                        "beaconB":        rssi_b,
                        "location":       prediction,
                        "confidence":     confidence,
                        "connection":     "ONLINE",
                        "system_state":   "TRACKING",
                        "beaconA_status": signal_status(rssi_a),
                        "beaconB_status": signal_status(rssi_b),
                        "accuracy_label": (
                            "High Accuracy" if confidence >= 85
                            else "Medium Accuracy"
                        ),
                        "map_position":   MAP_POSITIONS.get(
                            prediction, MAP_POSITIONS["Corridor"]
                        ),
                        "timestamp":      round(time.time() * 1000),
                        "error_message":  ""
                    })

        except serial.SerialException as e:
            set_disconnected(f"Serial error: {str(e)}")
            print(f"❌ Serial error: {e}")

        except Exception as e:
            set_disconnected(f"Unexpected error: {str(e)}")
            print(f"❌ Unexpected error: {e}")

        finally:
            try:
                ser.close()
            except Exception:
                pass

        print(f"🔄 Reconnecting in {RETRY_DELAY}s…")
        time.sleep(RETRY_DELAY)

# ============================================================
# START BACKGROUND THREAD
# ============================================================

threading.Thread(target=serial_reader, daemon=True).start()
print("🚀 Serial reader thread started")