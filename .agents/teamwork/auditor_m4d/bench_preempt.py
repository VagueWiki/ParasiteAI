import time
import threading
import subprocess

def test_breakdown():
    token = threading.Event()
    t_signal = [0.0]

    proc = subprocess.Popen(
        ["python", "-c", "import time; time.sleep(10.0)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=0x08000000,
    )

    def trigger():
        time.sleep(0.05)
        t_signal[0] = time.perf_counter()
        token.set()

    th = threading.Thread(target=trigger)
    th.start()

    t_detect = 0.0
    t_kill = 0.0
    t_taskkill = 0.0

    while True:
        if token.is_set():
            t_detect = time.perf_counter()
            proc.kill()
            t_kill = time.perf_counter()
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, creationflags=0x08000000)
            t_taskkill = time.perf_counter()
            break
        time.sleep(0.010)

    th.join()

    detect_latency_ms = (t_detect - t_signal[0]) * 1000.0
    kill_latency_ms = (t_kill - t_detect) * 1000.0
    taskkill_latency_ms = (t_taskkill - t_kill) * 1000.0
    total_ms = (t_taskkill - t_signal[0]) * 1000.0

    print(f"Detection latency (polling interval): {detect_latency_ms:.2f} ms")
    print(f"proc.kill() latency: {kill_latency_ms:.2f} ms")
    print(f"taskkill subprocess latency: {taskkill_latency_ms:.2f} ms")
    print(f"Total time until function return: {total_ms:.2f} ms")

if __name__ == "__main__":
    for i in range(3):
        test_breakdown()
