import psycopg2, os
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(host='localhost', port=5432, dbname='india_dev_analytics', user='analyst', password='yash123')
conn.autocommit = True
cur = conn.cursor()

print("Cleaning duplicate data...")

# Delete everything and start fresh
cur.execute("DELETE FROM development_index")
cur.execute("DELETE FROM economic_data")
cur.execute("DELETE FROM demographics")
cur.execute("DELETE FROM cities")
cur.execute("DELETE FROM districts")
cur.execute("DELETE FROM states")

print("All tables cleared")

# Verify
for t in ["states","districts","demographics","economic_data","development_index"]:
    cur.execute("SELECT COUNT(*) FROM " + t)
    print(t + ": " + str(cur.fetchone()[0]) + " rows")

conn.close()
print("Done. Now run: python fix_database.py")