import os

fix = '''import os
import logging

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(h)
    return logger
'''

files = [
    "api/routers/cities.py",
    "api/routers/states.py",
    "api/routers/districts.py",
    "api/routers/compare.py",
    "api/routers/health.py",
    "api/main.py",
    "scripts/download_data.py",
    "scripts/clean_transform.py",
    "scripts/geospatial_join.py",
    "scripts/load_postgres.py",
    "scripts/load_neo4j.py",
    "analytics/development_index.py",
    "analytics/visualisation.py",
]

bad_imports = [
    "from config.config_loader import get_config, get_logger, get_postgres_url",
    "from config.config_loader import get_logger",
    "from config.config_loader import get_config, get_logger",
    "from config.config_loader import data_path, get_config, get_logger",
    "from config.config_loader import get_config, get_logger, get_neo4j_config",
    "from config.config_loader import data_path, get_config, get_logger, get_logger",
]

for filepath in files:
    if not os.path.exists(filepath):
        print("SKIP (not found): " + filepath)
        continue
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()
    changed = False
    for bad in bad_imports:
        if bad in code:
            code = code.replace(bad, fix)
            changed = True
    if "from config.config_loader import" in code:
        lines = code.split("\n")
        new_lines = []
        inserted = False
        for line in lines:
            if "from config.config_loader import" in line:
                if not inserted:
                    new_lines.append(fix)
                    inserted = True
            else:
                new_lines.append(line)
        code = "\n".join(new_lines)
        changed = True
    if changed:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        print("FIXED: " + filepath)
    else:
        print("OK (no change needed): " + filepath)

print("\nAll done. Now run:")
print("uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")