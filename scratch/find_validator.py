import os

def search_dir(directory):
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.endswith(".py") or f.endswith(".js") or f.endswith(".json"):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as file:
                        content = file.read()
                        if "must be within artifact directory" in content:
                            print(f"Found in: {filepath}")
                except Exception:
                    pass

search_dir(r"C:\Users\vjbel\.gemini")
