import os
import threading
import time
import pickle
import psutil
import ctypes
import tkinter as tk
from tkinter import scrolledtext, messagebox

# ========== Configuration & Constants ==========

GAMES = ["MarvelRivalsClient.exe", "valorant.exe", "cs2.exe"]
ACTIONS = ["high_priority", "normal_priority", "power_high", "power_balanced", "apply_boost"]
QTABLE_FILE = "nd_qtable.pkl"

# ========== Utilities ==========

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def find_game_process():
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if name and name.lower() in (g.lower() for g in GAMES):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def set_process_priority(proc, priority):
    try:
        proc.nice(priority)
        return True, f"Set process {proc.pid} priority to {priority}"
    except Exception as e:
        return False, f"Failed to set priority: {e}"

def set_power_plan_high():
    os.system('powercfg -setactive SCHEME_MIN')
    return "Power Plan set to HIGH PERFORMANCE"

def set_power_plan_balanced():
    os.system('powercfg -setactive SCHEME_BALANCED')
    return "Power Plan set to BALANCED"

def apply_max_boost():
    """Apply a set of system tweaks for boost. Many require administrative rights."""
    logs = []
    # Disable SysMain
    os.system('sc stop "SysMain"')
    os.system('sc config "SysMain" start=disabled')
    logs.append("SysMain stopped & disabled")
    # Disable GameDVR etc.
    os.system('reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\GameDVR" /v "AppCaptureEnabled" /t REG_DWORD /d 0 /f')
    os.system('reg add "HKCU\\System\\GameConfigStore" /v "GameDVR_Enabled" /t REG_DWORD /d 0 /f')
    logs.append("GameDVR disabled")
    # (other tweaks can be added here)
    return "\n".join(logs)

def revert_boost():
    """Revert some changes made in apply_max_boost. Many require matching state knowledge."""
    logs = []
    # Re-enable SysMain
    os.system('sc config "SysMain" start=auto')
    os.system('sc start "SysMain"')
    logs.append("SysMain enabled & started")
    # Re-enable GameDVR (basic revert)
    os.system('reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\GameDVR" /v "AppCaptureEnabled" /t REG_DWORD /d 1 /f')
    os.system('reg add "HKCU\\System\\GameConfigStore" /v "GameDVR_Enabled" /t REG_DWORD /d 1 /f')
    logs.append("GameDVR re-enabled")
    return "\n".join(logs)

# ========== RL Agent ==========

class RLAgent(threading.Thread):
    def __init__(self, log_callback):
        super().__init__()
        self.daemon = True
        self.running = False
        self.qtable = {}
        self.log = log_callback
        self.load_qtable()

    def load_qtable(self):
        if os.path.exists(QTABLE_FILE):
            try:
                with open(QTABLE_FILE, 'rb') as f:
                    self.qtable = pickle.load(f)
                    self.log("Loaded Q-table from disk.")
            except Exception as e:
                self.qtable = {}
                self.log(f"Failed to load Q-table: {e}")
        else:
            self.log("No Q-table file found; starting fresh.")

    def save_qtable(self):
        try:
            with open(QTABLE_FILE, 'wb') as f:
                pickle.dump(self.qtable, f)
                self.log("Q-table saved.")
        except Exception as e:
            self.log(f"Error saving Q-table: {e}")

    def get_state(self):
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        # Binning state
        return (int(cpu // 10), int(ram // 10))

    def choose_action(self, state):
        if state not in self.qtable:
            self.qtable[state] = {a: 0.0 for a in ACTIONS}
        # epsilon-greedy
        epsilon = 0.3
        if (time.time() % 10) < epsilon:  # simple randomness
            action = ACTIONS[int(time.time()) % len(ACTIONS)]
            self.log(f"Exploring action: {action}")
        else:
            action = max(self.qtable[state], key=self.qtable[state].get)
            self.log(f"Exploiting action: {action}")
        return action

    def perform_action(self, action, proc):
        messages = []
        if action == "high_priority" and proc:
            success, msg = set_process_priority(proc, psutil.HIGH_PRIORITY_CLASS)
            messages.append(msg)
        elif action == "normal_priority" and proc:
            success, msg = set_process_priority(proc, psutil.NORMAL_PRIORITY_CLASS)
            messages.append(msg)
        elif action == "power_high":
            msg = set_power_plan_high()
            messages.append(msg)
        elif action == "power_balanced":
            msg = set_power_plan_balanced()
            messages.append(msg)
        elif action == "apply_boost":
            msg = apply_max_boost()
            messages.append(msg)
        else:
            messages.append("No valid action or game process not found.")
        return "\n".join(messages)

    def get_reward(self, prev_cpu, cur_cpu, prev_ram, cur_ram):
        # reward high performance = low cpu & ram usage
        # smaller CPU & RAM usage → more reward
        # Simple: reward = (prev_cpu - cur_cpu) + (prev_ram - cur_ram)
        return max(0, (prev_cpu - cur_cpu)) + max(0, (prev_ram - cur_ram))

    def run(self):
        self.running = True
        prev_state = None
        prev_cpu = None
        prev_ram = None

        while self.running:
            proc = find_game_process()
            if proc:
                state = self.get_state()
                self.log(f"State: CPU_bin={state[0]}, RAM_bin={state[1]}")

                # measure baseline
                prev_cpu = psutil.cpu_percent(interval=1)
                prev_ram = psutil.virtual_memory().percent

                action = self.choose_action(state)
                log_msg = self.perform_action(action, proc)
                self.log(f"Action: {action}\n{log_msg}")

                # wait a bit
                time.sleep(2)

                # measure after action
                cur_cpu = psutil.cpu_percent(interval=1)
                cur_ram = psutil.virtual_memory().percent

                reward = self.get_reward(prev_cpu, cur_cpu, prev_ram, cur_ram)
                self.log(f"Reward: {reward:.2f}")

                # Q-learning update
                if prev_state is not None:
                    old = self.qtable.get(prev_state, {}).get(action, 0.0)
                    # simple Q update
                    lr = 0.1
                    gamma = 0.9
                    # new value
                    new_val = old + lr * (reward + gamma * max(self.qtable.get(state, {}).values(), default=0) - old)
                    self.qtable[prev_state][action] = new_val
                    self.log(f"Q[{prev_state}][{action}] updated to {new_val:.2f}")

                prev_state = state

                self.save_qtable()
            else:
                self.log("No target game running.")
                time.sleep(5)

    def stop(self):
        self.running = False

# ========== GUI ==========

class NeuralDriveGUI:
    def __init__(self, root):
        self.root = root
        root.title("NeuralDrive OS GUI")
        self.agent = RLAgent(self.log)
        self.create_widgets()
        self.update_stats()

    def create_widgets(self):
        self.status_label = tk.Label(self.root, text="Game Running: No", font=("Arial", 12))
        self.status_label.pack(pady=5)

        self.cpu_label = tk.Label(self.root, text="CPU Usage: --%", font=("Arial", 12))
        self.cpu_label.pack(pady=5)

        self.ram_label = tk.Label(self.root, text="RAM Usage: --%", font=("Arial", 12))
        self.ram_label.pack(pady=5)

        frame = tk.Frame(self.root)
        frame.pack(pady=10)

        self.start_button = tk.Button(frame, text="Start Agent", command=self.start_agent, width=15)
        self.start_button.grid(row=0, column=0, padx=5)

        self.stop_button = tk.Button(frame, text="Stop Agent", command=self.stop_agent, width=15)
        self.stop_button.grid(row=0, column=1, padx=5)

        self.boost_button = tk.Button(frame, text="Apply Max Boost", command=self.apply_boost, width=15)
        self.boost_button.grid(row=1, column=0, padx=5, pady=5)

        self.revert_button = tk.Button(frame, text="Revert Boost", command=self.revert_boost, width=15)
        self.revert_button.grid(row=1, column=1, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(self.root, height=20, width=80, state='disabled', font=("Courier", 10))
        self.log_text.pack(pady=10)

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text['state'] = 'normal'
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text['state'] = 'disabled'

    def update_stats(self):
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        self.cpu_label.config(text=f"CPU Usage: {cpu:.1f}%")
        self.ram_label.config(text=f"RAM Usage: {ram:.1f}%")
        proc = find_game_process()
        self.status_label.config(text=f"Game Running: {'Yes' if proc else 'No'}")
        self.root.after(1000, self.update_stats)

    def start_agent(self):
        if not is_admin():
            messagebox.showerror("Error", "Please run this as Administrator.")
            return
        if not self.agent.is_alive():
            self.agent = RLAgent(self.log)
            self.agent.start()
            self.log("RL Agent started.")

    def stop_agent(self):
        self.agent.stop()
        self.log("RL Agent stopped.")

    def apply_boost(self):
        if not is_admin():
            messagebox.showerror("Error", "Please run this as Administrator.")
            return
        logs = apply_max_boost()
        self.log("Manual Boost applied:\n" + logs)

    def revert_boost(self):
        if not is_admin():
            messagebox.showerror("Error", "Please run this as Administrator.")
            return
        logs = revert_boost()
        self.log("Revert applied:\n" + logs)

def main():
    root = tk.Tk()
    gui = NeuralDriveGUI(root)
    root.mainloop()

if __name__ == "__main__":
    if not is_admin():
        # Relaunch as admin
        ctypes.windll.shell32.ShellExecuteW(None, "runas", "python", __file__, None, 1)
    else:
        main()
