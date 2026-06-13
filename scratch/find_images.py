import os

def main():
    art_dir = r"C:\Users\vjbel\.gemini\antigravity\brain\c72e6410-a1e3-46ef-8bd6-0d759205f567"
    for f in os.listdir(art_dir):
        if f.endswith(".md"):
            filepath = os.path.join(art_dir, f)
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()
                if "![" in content:
                    print(f"--- Images in {f} ---")
                    for line in content.splitlines():
                        if "![" in line:
                            print(line)

if __name__ == "__main__":
    main()
