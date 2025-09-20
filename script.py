import tkinter as tk
from tkinter import scrolledtext
import psutil, platform, statistics, threading, os, json
from llama_cpp import Llama

# === CONFIG ===
SIGMA_SELF = __file__
MODEL_PATH = "./models/mistral-7b-instruct-v0.1.Q4_K_M.gguf"
MEMORY_PATH = "./symbol_brain.json"
llm = Llama(model_path=MODEL_PATH, n_ctx=2048)

# === MEMORY INIT ===
if not os.path.exists(MEMORY_PATH):
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump({"user_teachings": []}, f)

RML_State = {"usage_samples": [], "fps_boost_history": []}

# >>> BEGIN SIGMA_LOGIC
def compute_boost(cpu_usage):
    return int(60 + cpu_usage * 10)
# <<< END SIGMA_LOGIC

def get_cpu_base_freq():
    freq = psutil.cpu_freq()
    return freq.max if freq else 3600

def update_rml(cpu_usage, fps):
    RML_State["usage_samples"].append(cpu_usage)
    RML_State["fps_boost_history"].append(fps)
    if len(RML_State["fps_boost_history"]) > 100:
        RML_State["usage_samples"].pop(0)
        RML_State["fps_boost_history"].pop(0)

def apply_logic_patch(new_logic):
    try:
        exec(f"def __temp_patch__():\n" + "\n".join("    " + l for l in new_logic.strip().splitlines()), globals())
        patch_func = globals()["__temp_patch__"]
        local_vars = {}
        exec(patch_func.__code__, globals(), local_vars)
        globals().update(local_vars)
        output_txt.insert(tk.END, "✅ Logic patched live.\n")
    except Exception as e:
        output_txt.insert(tk.END, f"❌ Patch failed: {e}\n")

def ask_model(prompt, code):
    user_prompt = f"""Only update compute_boost inside SIGMA_LOGIC.
Respond with updated code block inside ```python ... ```.

User wants: "{prompt}"

```python
{code}
```"""
    out = llm(user_prompt, stop=["```"], temperature=0.2, max_tokens=2048)
    raw = out["choices"][0]["text"]
    if "```python" in raw:
        return raw.split("```python")[1].split("```")[0].strip()
    return raw.strip()

def update_stats():
    base_freq = get_cpu_base_freq()
    while True:
        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq().current
        fps = compute_boost(cpu_usage)
        update_rml(cpu_usage, fps)
        stats_str = (
            f"SYSTEM: {platform.system()} {platform.machine()}\n"
            f"CPU Clock: {cpu_freq:.2f} MHz | Base: {base_freq:.2f} MHz\n"
            f"CPU Usage: {cpu_usage:.2f}%\n"
            f"Boosted FPS: {fps}\n"
            f"RML Avg FPS: {int(statistics.mean(RML_State['fps_boost_history'])) if RML_State['fps_boost_history'] else 'n/a'}\n"
        )
        stats_box.config(state='normal')
        stats_box.delete(1.0, tk.END)
        stats_box.insert(tk.END, stats_str)
        stats_box.config(state='disabled')

def recode_logic():
    prompt = prompt_entry.get().strip()
    if not prompt:
        output_txt.insert(tk.END, "⚠️ Enter a prompt.\n")
        return
    code = open(SIGMA_SELF, "r", encoding="utf-8").read()
    updated_logic = ask_model(prompt, code)
    if updated_logic:
        apply_logic_patch(updated_logic)
    else:
        output_txt.insert(tk.END, "⚠️ No valid logic returned.\n")

def teach_brain():
    text = teach_box.get("1.0", tk.END).strip()
    if text:
        with open(MEMORY_PATH, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("user_teachings", []).append(text)
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
        output_txt.insert(tk.END, "🧠 Teaching recorded.\n")

# === GUI BUILD ===
root = tk.Tk()
root.title("SIGMA_BRAIN vΣ3.0 GUI Live")

# Frame for logic recode
frm_logic = tk.Frame(root, padx=10, pady=10)
frm_logic.pack(fill=tk.X)

tk.Label(frm_logic, text="Recode Logic Prompt:").pack(side=tk.LEFT)
prompt_entry = tk.Entry(frm_logic, width=80)
prompt_entry.pack(side=tk.LEFT, padx=5)
tk.Button(frm_logic, text="🔁 Recode", command=recode_logic).pack(side=tk.LEFT)

# Frame for stats
stats_box = scrolledtext.ScrolledText(root, height=8, width=80, state='disabled', font=("Consolas", 10))
stats_box.pack(padx=10, pady=5)

# Frame for teaching
tk.Label(root, text="Teach SIGMA AI:").pack(padx=10, pady=(10,0))
teach_box = tk.Text(root, height=3, width=80)
teach_box.pack(padx=10, pady=5)
tk.Button(root, text="📥 Submit Teaching", command=teach_brain).pack()

# Output messages
output_txt = scrolledtext.ScrolledText(root, height=5, width=80, font=("Consolas", 10))
output_txt.pack(padx=10, pady=5)

# Start stats updating in background
threading.Thread(target=update_stats, daemon=True).start()

root.mainloop()
