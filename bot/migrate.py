import json
import pymongo
import bson

try:
    import mysql.connector
except ImportError:
    exit("You need to install mysql-connector-python pip package to migrate")

with open('config.json', 'r') as f:
    config = json.load(f)

credentials = config['authentication']['database']

client = pymongo.MongoClient(credentials["connection string"])
mongo_db = client.get_database('Pidroid')

# Login to newly created DB
db = mysql.connector.connect(
    host=credentials['host'],
    user=credentials['user'],
    password=credentials['password'],
    database='pidroid'
)

cursor = db.cursor()

# Migrate punishments
cursor.execute("SELECT * FROM Punishments")
collection = mongo_db.get_collection('Punishments')
print("Migrating Punishments")
for i in cursor.fetchall():
    d = {
        "id": str(i[0]),
        "type": i[7],
        "guild_id": bson.Int64(i[1]),
        "user_id": bson.Int64(i[2]),
        "moderator_id": bson.Int64(i[4]),
        "date_issued": i[6],
        "date_expires": i[9],
        "visible": i[-1] == 0
    }
    if i[3]:
        d["user_name"] = i[3]
    if i[5]:
        d["user_name"] = i[5]
    if i[8]:
        d["reason"] = i[8]
    collection.insert_one(d)

# Migrate guild configurations
cursor.execute("SELECT * FROM `Guild configurations`")
collection = mongo_db.get_collection('Guild_configurations')
print("Migrating guild configurations")
for i in cursor.fetchall():
    d = {
        "guild_id": bson.Int64(i[1]),
    }
    if i[2]:
        d["jail_channel"] = bson.Int64(i[2])
    if i[3]:
        d["jail_role"] = bson.Int64(i[3])
    if i[4]:
        d["mute_role"] = bson.Int64(i[4])
    collection.insert_one(d)

# Migrate frequently asked questions
cursor.execute("SELECT * FROM `Frequently_asked_questions`")
collection = mongo_db.get_collection('FAQ')
print("Migrating FAQs")
for i in cursor.fetchall():
    d = {
        "id": str(i[0]),
        "question": i[1],
        "answer": i[2]
    }
    if i[3] is not None:
        d["tags"] = i[3].split(",")
    collection.insert_one(d)

# Migrate suggestions
cursor.execute("SELECT * FROM `Suggestions`")
collection = mongo_db.get_collection('Suggestions')
print("Migrating suggestions")
for i in cursor.fetchall():
    d = {
        "id": str(i[0]),
        "author": bson.Int64(i[1]),
        "suggestion": i[3],
        "timestamp": bson.Int64(i[6])
    }
    if i[2]:
        d["message_id"] = bson.Int64(i[2])
    if i[4]:
        d["attachment_url"] = i[4]
    if i[5]:
        d["response"] = i[5]
    collection.insert_one(d)

# Migrate shitposts
cursor.execute("SELECT * FROM `Shitposts`")
collection = mongo_db.get_collection('Shitposts')
print("Migrating Shitposts")
for i in cursor.fetchall():
    d = {
        "times_shown": i[1]
    }
    if i[2]:
        d["text"] = i[2]
    if i[3]:
        d["attachment_url"] = i[3]
    collection.insert_one(d)

cursor.close()
db.close()

exit('Database setup has been completed!')
