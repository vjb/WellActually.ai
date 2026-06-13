import os

art_dir = r"C:\Users\vjbel\.gemini\antigravity\brain\c72e6410-a1e3-46ef-8bd6-0d759205f567"
p = "/Users/vjbel/.gemini/antigravity/brain/c72e6410-a1e3-46ef-8bd6-0d759205f567/triage_approval_pending_ui.png"
abs_p = os.path.abspath(p)

print(f"abs_p: {abs_p}")
print(f"art_dir: {art_dir}")
print(f"abs_p.startswith(art_dir): {abs_p.startswith(art_dir)}")
print(f"abs_p.lower().startswith(art_dir.lower()): {abs_p.lower().startswith(art_dir.lower())}")
